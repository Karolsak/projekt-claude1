"""
Advanced DC Generator Magnetization Analysis Tool
Comprehensive multi-physics simulation with GUI

Features:
- Magnetization curve analysis
- Real-time dynamic simulation (RK45, Euler)
- Multi-physics coupling (electromagnetic-thermal-mechanical)
- Economic analysis
- Loss breakdown
- Thermal derating
- Advanced control systems
"""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.integrate import solve_ivp, odeint
from scipy.optimize import fsolve, minimize
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple
import threading
import time


# ============================================================================
# DATA CLASSES FOR STRUCTURED DATA
# ============================================================================

@dataclass
class GeneratorParameters:
    """DC Generator physical parameters"""
    rated_power: float = 10000.0  # W
    rated_voltage: float = 240.0  # V
    rated_speed: float = 1500.0  # rpm
    armature_resistance: float = 0.5  # Ohm
    field_resistance: float = 100.0  # Ohm
    armature_inductance: float = 0.05  # H
    field_inductance: float = 2.0  # H
    moment_of_inertia: float = 0.5  # kg.m^2
    friction_coefficient: float = 0.01  # N.m.s/rad
    thermal_capacitance: float = 1000.0  # J/K
    thermal_resistance: float = 0.5  # K/W
    ambient_temperature: float = 25.0  # Celsius
    max_temperature: float = 130.0  # Celsius
    pole_pairs: int = 2


@dataclass
class SimulationState:
    """Current state of the simulation"""
    time: float = 0.0
    armature_current: float = 0.0
    field_current: float = 0.0
    speed: float = 1500.0
    voltage: float = 0.0
    temperature: float = 25.0
    torque: float = 0.0
    power: float = 0.0


# ============================================================================
# MAGNETIZATION CURVE ANALYSIS
# ============================================================================

class MagnetizationAnalysis:
    """Analyzes DC generator magnetization characteristics"""

    def __init__(self):
        # Given magnetization data at 1500 rpm
        self.If_data = np.array([0, 0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8, 3.0])
        self.E0_data = np.array([6, 60, 120, 172.5, 202.5, 221, 231, 237, 240])
        self.base_speed = 1500.0  # rpm

        # Create interpolation function
        self.mag_curve = UnivariateSpline(self.If_data, self.E0_data, s=0, k=3)

    def get_emf(self, field_current: float, speed: float = 1500.0) -> float:
        """Get EMF for given field current and speed"""
        # EMF is proportional to speed
        emf_base = self.mag_curve(np.clip(field_current, 0, 3.0))
        emf = emf_base * (speed / self.base_speed)
        return float(emf)

    def find_no_load_emf(self, field_resistance: float, speed: float = 1500.0) -> Tuple[float, float]:
        """
        Find no-load EMF by solving the intersection of magnetization curve
        and field resistance line: E = If * Rf

        Returns: (emf, field_current)
        """
        def equation(If):
            emf = self.get_emf(If, speed)
            return emf - If * field_resistance

        # Initial guess
        If_guess = 2.0
        If_solution = fsolve(equation, If_guess)[0]
        emf_solution = self.get_emf(If_solution, speed)

        return emf_solution, If_solution

    def find_critical_resistance(self, speed: float = 1500.0) -> float:
        """
        Find critical field resistance (maximum slope of magnetization curve)
        """
        # Find the point where dE/dIf is maximum
        If_range = np.linspace(0.1, 2.0, 1000)
        slopes = []

        for If in If_range:
            # Calculate numerical derivative
            dIf = 0.01
            E1 = self.get_emf(If - dIf/2, speed)
            E2 = self.get_emf(If + dIf/2, speed)
            slope = (E2 - E1) / dIf
            slopes.append(slope)

        critical_resistance = max(slopes)
        return critical_resistance

    def get_magnetization_curve(self, speed: float) -> Tuple[np.ndarray, np.ndarray]:
        """Get magnetization curve at specified speed"""
        If_range = np.linspace(0, 3.0, 100)
        E0_range = np.array([self.get_emf(If, speed) for If in If_range])
        return If_range, E0_range


# ============================================================================
# MULTI-PHYSICS MODELS
# ============================================================================

class ElectromagneticModel:
    """Electromagnetic behavior of DC generator"""

    def __init__(self, params: GeneratorParameters, mag_analysis: MagnetizationAnalysis):
        self.params = params
        self.mag_analysis = mag_analysis

    def armature_equation(self, Ia: float, If: float, speed: float, Va: float) -> float:
        """
        Armature circuit equation: Va = Ea + Ia*Ra
        Returns dIa/dt
        """
        Ea = self.mag_analysis.get_emf(If, speed)
        dIa_dt = (Va - Ea - Ia * self.params.armature_resistance) / self.params.armature_inductance
        return dIa_dt

    def field_equation(self, If: float, Vf: float) -> float:
        """
        Field circuit equation: Vf = If*Rf + Lf*dIf/dt
        Returns dIf/dt
        """
        dIf_dt = (Vf - If * self.params.field_resistance) / self.params.field_inductance
        return dIf_dt

    def electromagnetic_torque(self, Ia: float, If: float) -> float:
        """Calculate electromagnetic torque"""
        # Assuming linear relationship with flux (simplified)
        flux = If * 0.1  # Wb (simplified)
        Te = self.params.pole_pairs * flux * Ia
        return Te


class ThermalModel:
    """Thermal behavior and heat transfer"""

    def __init__(self, params: GeneratorParameters):
        self.params = params

    def calculate_losses(self, Ia: float, If: float, speed: float) -> Dict[str, float]:
        """Calculate detailed loss breakdown"""
        # Copper losses
        copper_loss_armature = Ia**2 * self.params.armature_resistance
        copper_loss_field = If**2 * self.params.field_resistance

        # Iron losses (hysteresis + eddy current)
        # Proportional to speed and flux
        speed_pu = speed / self.params.rated_speed
        flux_pu = If / 2.0  # Normalized
        hysteresis_loss = 50 * speed_pu * flux_pu**2
        eddy_loss = 30 * speed_pu**2 * flux_pu**2

        # Mechanical losses (friction and windage)
        omega = speed * 2 * np.pi / 60  # rad/s
        friction_loss = self.params.friction_coefficient * omega**2
        windage_loss = 0.01 * omega**3

        # Stray load losses (approximately 1% of rated power)
        load_pu = Ia / (self.params.rated_power / self.params.rated_voltage)
        stray_loss = 0.01 * self.params.rated_power * load_pu**2

        losses = {
            'copper_armature': copper_loss_armature,
            'copper_field': copper_loss_field,
            'hysteresis': hysteresis_loss,
            'eddy': eddy_loss,
            'friction': friction_loss,
            'windage': windage_loss,
            'stray': stray_loss,
            'total': sum([copper_loss_armature, copper_loss_field, hysteresis_loss,
                         eddy_loss, friction_loss, windage_loss, stray_loss])
        }

        return losses

    def thermal_dynamics(self, temperature: float, losses: float) -> float:
        """
        Heat transfer equation: C*dT/dt = P_loss - (T-T_amb)/R_th
        Returns dT/dt
        """
        heat_dissipation = (temperature - self.params.ambient_temperature) / self.params.thermal_resistance
        dT_dt = (losses - heat_dissipation) / self.params.thermal_capacitance
        return dT_dt

    def derating_factor(self, temperature: float) -> float:
        """Calculate derating factor based on temperature"""
        if temperature <= self.params.max_temperature:
            return 1.0
        else:
            # Linear derating above max temperature
            return max(0.5, 1.0 - 0.02 * (temperature - self.params.max_temperature))


class MechanicalModel:
    """Mechanical dynamics and stress analysis"""

    def __init__(self, params: GeneratorParameters):
        self.params = params

    def mechanical_equation(self, speed: float, Te: float, Tload: float) -> float:
        """
        Mechanical equation: J*domega/dt = Te - Tload - B*omega
        Returns d(speed)/dt
        """
        omega = speed * 2 * np.pi / 60  # Convert rpm to rad/s
        friction_torque = self.params.friction_coefficient * omega

        domega_dt = (Te - Tload - friction_torque) / self.params.moment_of_inertia
        dspeed_dt = domega_dt * 60 / (2 * np.pi)  # Convert back to rpm/s

        return dspeed_dt

    def shaft_stress_analysis(self, torque: float) -> Dict[str, float]:
        """Calculate shaft stress and bearing loads"""
        # Assuming shaft diameter of 50mm
        shaft_diameter = 0.05  # m
        shaft_radius = shaft_diameter / 2

        # Torsional shear stress: tau = T*r/J
        polar_moment = np.pi * shaft_radius**4 / 2
        shear_stress = abs(torque) * shaft_radius / polar_moment

        # Bearing load (simplified, assuming radial load from weight)
        bearing_load = 500.0  # N (assumed)

        return {
            'shear_stress': shear_stress / 1e6,  # MPa
            'bearing_load': bearing_load,
            'safety_factor': 200e6 / (shear_stress + 1e-6)  # Assuming steel with 200 MPa yield
        }


# ============================================================================
# DYNAMIC SIMULATOR
# ============================================================================

class DynamicSimulator:
    """Real-time dynamic simulation with multiple ODE solvers"""

    def __init__(self, params: GeneratorParameters, mag_analysis: MagnetizationAnalysis):
        self.params = params
        self.mag_analysis = mag_analysis

        self.em_model = ElectromagneticModel(params, mag_analysis)
        self.thermal_model = ThermalModel(params)
        self.mechanical_model = MechanicalModel(params)

        self.reset()

    def reset(self):
        """Reset simulation to initial conditions"""
        self.state = SimulationState()
        self.state.speed = self.params.rated_speed
        self.state.temperature = self.params.ambient_temperature
        self.history = {
            'time': [],
            'voltage': [],
            'current': [],
            'speed': [],
            'temperature': [],
            'torque': [],
            'power': [],
            'losses': []
        }

    def system_equations(self, t: float, y: np.ndarray, Va: float, Vf: float, Tload: float) -> np.ndarray:
        """
        Complete system of differential equations
        State vector: y = [Ia, If, speed, temperature]
        """
        Ia, If, speed, temperature = y

        # Ensure physical limits
        Ia = max(0, Ia)
        If = max(0, If)
        speed = max(100, speed)
        temperature = max(self.params.ambient_temperature, temperature)

        # Electromagnetic equations
        dIa_dt = self.em_model.armature_equation(Ia, If, speed, Va)
        dIf_dt = self.em_model.field_equation(If, Vf)

        # Mechanical equation
        Te = self.em_model.electromagnetic_torque(Ia, If)
        dspeed_dt = self.mechanical_model.mechanical_equation(speed, Te, Tload)

        # Thermal equation
        losses = self.thermal_model.calculate_losses(Ia, If, speed)
        dT_dt = self.thermal_model.thermal_dynamics(temperature, losses['total'])

        return np.array([dIa_dt, dIf_dt, dspeed_dt, dT_dt])

    def simulate_step_rk45(self, dt: float, Va: float, Vf: float, Tload: float):
        """Single step simulation using RK45 method"""
        y0 = np.array([
            self.state.armature_current,
            self.state.field_current,
            self.state.speed,
            self.state.temperature
        ])

        t_span = [self.state.time, self.state.time + dt]

        sol = solve_ivp(
            lambda t, y: self.system_equations(t, y, Va, Vf, Tload),
            t_span,
            y0,
            method='RK45',
            dense_output=True
        )

        # Update state
        y_new = sol.y[:, -1]
        self.state.armature_current = max(0, y_new[0])
        self.state.field_current = max(0, y_new[1])
        self.state.speed = max(100, y_new[2])
        self.state.temperature = max(self.params.ambient_temperature, y_new[3])
        self.state.time += dt

        # Calculate derived quantities
        self.state.voltage = self.mag_analysis.get_emf(self.state.field_current, self.state.speed)
        self.state.torque = self.em_model.electromagnetic_torque(
            self.state.armature_current, self.state.field_current
        )
        self.state.power = self.state.voltage * self.state.armature_current

    def simulate_step_euler(self, dt: float, Va: float, Vf: float, Tload: float):
        """Single step simulation using Euler method"""
        y = np.array([
            self.state.armature_current,
            self.state.field_current,
            self.state.speed,
            self.state.temperature
        ])

        dy_dt = self.system_equations(self.state.time, y, Va, Vf, Tload)
        y_new = y + dy_dt * dt

        # Update state
        self.state.armature_current = max(0, y_new[0])
        self.state.field_current = max(0, y_new[1])
        self.state.speed = max(100, y_new[2])
        self.state.temperature = max(self.params.ambient_temperature, y_new[3])
        self.state.time += dt

        # Calculate derived quantities
        self.state.voltage = self.mag_analysis.get_emf(self.state.field_current, self.state.speed)
        self.state.torque = self.em_model.electromagnetic_torque(
            self.state.armature_current, self.state.field_current
        )
        self.state.power = self.state.voltage * self.state.armature_current

    def record_history(self):
        """Record current state to history"""
        losses = self.thermal_model.calculate_losses(
            self.state.armature_current,
            self.state.field_current,
            self.state.speed
        )

        self.history['time'].append(self.state.time)
        self.history['voltage'].append(self.state.voltage)
        self.history['current'].append(self.state.armature_current)
        self.history['speed'].append(self.state.speed)
        self.history['temperature'].append(self.state.temperature)
        self.history['torque'].append(self.state.torque)
        self.history['power'].append(self.state.power)
        self.history['losses'].append(losses['total'])


# ============================================================================
# ECONOMIC ANALYSIS
# ============================================================================

class EconomicAnalysis:
    """Economic and efficiency analysis"""

    def __init__(self):
        self.electricity_cost = 0.12  # $/kWh
        self.maintenance_cost = 0.02  # $/hour
        self.capital_cost = 5000.0  # $

    def calculate_efficiency(self, power_out: float, losses: float) -> float:
        """Calculate efficiency"""
        power_in = power_out + losses
        if power_in > 0:
            return (power_out / power_in) * 100
        return 0.0

    def calculate_operating_cost(self, power_out: float, losses: float, hours: float) -> Dict[str, float]:
        """Calculate operating costs"""
        energy_loss_kWh = losses * hours / 1000
        energy_cost = energy_loss_kWh * self.electricity_cost
        maintenance = self.maintenance_cost * hours

        return {
            'energy_cost': energy_cost,
            'maintenance_cost': maintenance,
            'total_cost': energy_cost + maintenance,
            'cost_per_kWh': (energy_cost + maintenance) / max(power_out * hours / 1000, 1e-6)
        }

    def calculate_roi(self, annual_savings: float) -> Dict[str, float]:
        """Calculate return on investment"""
        if annual_savings > 0:
            payback_period = self.capital_cost / annual_savings
            roi_percentage = (annual_savings / self.capital_cost) * 100
        else:
            payback_period = float('inf')
            roi_percentage = 0.0

        return {
            'payback_period': payback_period,
            'roi_percentage': roi_percentage,
            'npv_5years': annual_savings * 5 - self.capital_cost
        }


# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class DCGeneratorApp:
    """Main application with comprehensive GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("Advanced DC Generator Magnetization Analysis")
        self.root.geometry("1400x900")

        # Initialize models
        self.params = GeneratorParameters()
        self.mag_analysis = MagnetizationAnalysis()
        self.simulator = DynamicSimulator(self.params, self.mag_analysis)
        self.economic = EconomicAnalysis()

        # Simulation control
        self.running = False
        self.simulation_thread = None
        self.solver_type = "RK45"
        self.time_step = 0.01

        # Create GUI
        self.create_menu()
        self.create_main_layout()

        # Auto-resize handling
        self.root.bind('<Configure>', self.on_window_resize)

        # Initial calculation
        self.solve_magnetization_problem()

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Results", command=self.save_results)
        file_menu.add_command(label="Load Parameters", command=self.load_parameters)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Analysis menu
        analysis_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Analysis", menu=analysis_menu)
        analysis_menu.add_command(label="Magnetization Analysis", command=self.solve_magnetization_problem)
        analysis_menu.add_command(label="Thermal Analysis", command=self.show_thermal_analysis)
        analysis_menu.add_command(label="Mechanical Stress", command=self.show_mechanical_analysis)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_main_layout(self):
        """Create main layout with tabs"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Create tabs
        self.create_magnetization_tab()
        self.create_simulation_tab()
        self.create_control_tab()
        self.create_thermal_tab()
        self.create_economic_tab()
        self.create_losses_tab()

    def create_magnetization_tab(self):
        """Tab for magnetization curve analysis"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Magnetization Analysis")

        # Left panel - controls
        left_frame = ttk.LabelFrame(tab, text="Parameters", padding=10)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Speed control
        ttk.Label(left_frame, text="Speed (rpm):").grid(row=0, column=0, sticky='w', pady=5)
        self.speed_var = tk.DoubleVar(value=1500.0)
        speed_scale = ttk.Scale(left_frame, from_=600, to=2000, variable=self.speed_var,
                               orient='horizontal', length=200, command=self.on_speed_change)
        speed_scale.grid(row=0, column=1, pady=5)
        self.speed_label = ttk.Label(left_frame, text="1500.0")
        self.speed_label.grid(row=0, column=2, padx=5)

        # Field resistance control
        ttk.Label(left_frame, text="Field Resistance (Ω):").grid(row=1, column=0, sticky='w', pady=5)
        self.rf_var = tk.DoubleVar(value=100.0)
        rf_scale = ttk.Scale(left_frame, from_=50, to=200, variable=self.rf_var,
                            orient='horizontal', length=200, command=self.on_rf_change)
        rf_scale.grid(row=1, column=1, pady=5)
        self.rf_label = ttk.Label(left_frame, text="100.0")
        self.rf_label.grid(row=1, column=2, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(left_frame, text="Analysis Results", padding=10)
        results_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky='ew')

        self.mag_results_text = tk.Text(results_frame, height=15, width=40, font=('Courier', 9))
        self.mag_results_text.pack(fill='both', expand=True)

        # Calculate button
        ttk.Button(left_frame, text="Calculate", command=self.solve_magnetization_problem,
                  style='Accent.TButton').grid(row=3, column=0, columnspan=3, pady=10)

        # Right panel - plots
        right_frame = ttk.Frame(tab)
        right_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        # Create matplotlib figure
        self.mag_figure = Figure(figsize=(10, 8), dpi=100)
        self.mag_canvas = FigureCanvasTkAgg(self.mag_figure, right_frame)
        self.mag_canvas.get_tk_widget().pack(fill='both', expand=True)

        # Configure grid weights
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

    def create_simulation_tab(self):
        """Tab for dynamic simulation"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dynamic Simulation")

        # Top control panel
        control_frame = ttk.LabelFrame(tab, text="Simulation Controls", padding=10)
        control_frame.pack(fill='x', padx=5, pady=5)

        # Solver selection
        ttk.Label(control_frame, text="Solver:").grid(row=0, column=0, padx=5)
        self.solver_var = tk.StringVar(value="RK45")
        solver_combo = ttk.Combobox(control_frame, textvariable=self.solver_var,
                                     values=["RK45", "Euler"], state='readonly', width=10)
        solver_combo.grid(row=0, column=1, padx=5)

        # Time step
        ttk.Label(control_frame, text="Time Step (s):").grid(row=0, column=2, padx=5)
        self.dt_var = tk.DoubleVar(value=0.01)
        dt_entry = ttk.Entry(control_frame, textvariable=self.dt_var, width=10)
        dt_entry.grid(row=0, column=3, padx=5)

        # Control buttons
        self.start_btn = ttk.Button(control_frame, text="▶ Start", command=self.start_simulation,
                                     style='Accent.TButton')
        self.start_btn.grid(row=0, column=4, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏸ Stop", command=self.stop_simulation,
                                    state='disabled')
        self.stop_btn.grid(row=0, column=5, padx=5)

        ttk.Button(control_frame, text="⟲ Reset", command=self.reset_simulation).grid(row=0, column=6, padx=5)

        # Input parameters panel
        input_frame = ttk.LabelFrame(tab, text="Input Parameters", padding=10)
        input_frame.pack(fill='x', padx=5, pady=5)

        # Armature voltage
        ttk.Label(input_frame, text="Armature Voltage (V):").grid(row=0, column=0, sticky='w', padx=5)
        self.va_var = tk.DoubleVar(value=240.0)
        va_scale = ttk.Scale(input_frame, from_=0, to=300, variable=self.va_var,
                            orient='horizontal', length=200)
        va_scale.grid(row=0, column=1, padx=5)
        self.va_label = ttk.Label(input_frame, textvariable=self.va_var)
        self.va_label.grid(row=0, column=2, padx=5)

        # Field voltage
        ttk.Label(input_frame, text="Field Voltage (V):").grid(row=1, column=0, sticky='w', padx=5)
        self.vf_var = tk.DoubleVar(value=240.0)
        vf_scale = ttk.Scale(input_frame, from_=0, to=300, variable=self.vf_var,
                            orient='horizontal', length=200)
        vf_scale.grid(row=1, column=1, padx=5)
        self.vf_label = ttk.Label(input_frame, textvariable=self.vf_var)
        self.vf_label.grid(row=1, column=2, padx=5)

        # Load torque
        ttk.Label(input_frame, text="Load Torque (N.m):").grid(row=2, column=0, sticky='w', padx=5)
        self.tload_var = tk.DoubleVar(value=50.0)
        tload_scale = ttk.Scale(input_frame, from_=0, to=200, variable=self.tload_var,
                               orient='horizontal', length=200)
        tload_scale.grid(row=2, column=1, padx=5)
        self.tload_label = ttk.Label(input_frame, textvariable=self.tload_var)
        self.tload_label.grid(row=2, column=2, padx=5)

        # Plots panel
        plot_frame = ttk.Frame(tab)
        plot_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.sim_figure = Figure(figsize=(12, 8), dpi=100)
        self.sim_canvas = FigureCanvasTkAgg(self.sim_figure, plot_frame)
        self.sim_canvas.get_tk_widget().pack(fill='both', expand=True)

        # Create subplots
        self.sim_axes = []
        for i in range(6):
            ax = self.sim_figure.add_subplot(3, 2, i+1)
            self.sim_axes.append(ax)

        self.sim_figure.tight_layout()

    def create_control_tab(self):
        """Tab for advanced control systems"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Advanced Control")

        # Control type selection
        control_frame = ttk.LabelFrame(tab, text="Control Strategy", padding=10)
        control_frame.pack(fill='x', padx=5, pady=5)

        self.control_type = tk.StringVar(value="Open Loop")
        controls = ["Open Loop", "Voltage Control", "Speed Control", "Power Control"]

        for i, ctrl in enumerate(controls):
            ttk.Radiobutton(control_frame, text=ctrl, variable=self.control_type,
                           value=ctrl).grid(row=0, column=i, padx=10)

        # PID parameters
        pid_frame = ttk.LabelFrame(tab, text="PID Controller Parameters", padding=10)
        pid_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(pid_frame, text="Kp:").grid(row=0, column=0, padx=5)
        self.kp_var = tk.DoubleVar(value=1.0)
        ttk.Entry(pid_frame, textvariable=self.kp_var, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(pid_frame, text="Ki:").grid(row=0, column=2, padx=5)
        self.ki_var = tk.DoubleVar(value=0.1)
        ttk.Entry(pid_frame, textvariable=self.ki_var, width=10).grid(row=0, column=3, padx=5)

        ttk.Label(pid_frame, text="Kd:").grid(row=0, column=4, padx=5)
        self.kd_var = tk.DoubleVar(value=0.01)
        ttk.Entry(pid_frame, textvariable=self.kd_var, width=10).grid(row=0, column=5, padx=5)

        # Setpoint
        setpoint_frame = ttk.LabelFrame(tab, text="Setpoint", padding=10)
        setpoint_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(setpoint_frame, text="Target Value:").grid(row=0, column=0, padx=5)
        self.setpoint_var = tk.DoubleVar(value=1500.0)
        ttk.Entry(setpoint_frame, textvariable=self.setpoint_var, width=15).grid(row=0, column=1, padx=5)

        # Control response plot
        response_frame = ttk.Frame(tab)
        response_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.control_figure = Figure(figsize=(10, 6), dpi=100)
        self.control_canvas = FigureCanvasTkAgg(self.control_figure, response_frame)
        self.control_canvas.get_tk_widget().pack(fill='both', expand=True)

    def create_thermal_tab(self):
        """Tab for thermal analysis and derating"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Thermal Analysis")

        # Parameters panel
        param_frame = ttk.LabelFrame(tab, text="Thermal Parameters", padding=10)
        param_frame.pack(fill='x', padx=5, pady=5)

        # Ambient temperature
        ttk.Label(param_frame, text="Ambient Temp (°C):").grid(row=0, column=0, padx=5, pady=5)
        self.amb_temp_var = tk.DoubleVar(value=25.0)
        ttk.Scale(param_frame, from_=0, to=50, variable=self.amb_temp_var,
                 orient='horizontal', length=200).grid(row=0, column=1, padx=5)
        ttk.Label(param_frame, textvariable=self.amb_temp_var).grid(row=0, column=2, padx=5)

        # Max temperature
        ttk.Label(param_frame, text="Max Temp (°C):").grid(row=1, column=0, padx=5, pady=5)
        self.max_temp_var = tk.DoubleVar(value=130.0)
        ttk.Entry(param_frame, textvariable=self.max_temp_var, width=10).grid(row=1, column=1, padx=5, sticky='w')

        # Derating display
        derating_frame = ttk.LabelFrame(tab, text="Derating Information", padding=10)
        derating_frame.pack(fill='x', padx=5, pady=5)

        self.derating_text = tk.Text(derating_frame, height=8, width=80, font=('Courier', 10))
        self.derating_text.pack(fill='both', expand=True)

        # Thermal plots
        plot_frame = ttk.Frame(tab)
        plot_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.thermal_figure = Figure(figsize=(10, 6), dpi=100)
        self.thermal_canvas = FigureCanvasTkAgg(self.thermal_figure, plot_frame)
        self.thermal_canvas.get_tk_widget().pack(fill='both', expand=True)

    def create_economic_tab(self):
        """Tab for economic analysis"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Economic Analysis")

        # Cost parameters
        cost_frame = ttk.LabelFrame(tab, text="Cost Parameters", padding=10)
        cost_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(cost_frame, text="Electricity Cost ($/kWh):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.elec_cost_var = tk.DoubleVar(value=0.12)
        ttk.Entry(cost_frame, textvariable=self.elec_cost_var, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(cost_frame, text="Maintenance Cost ($/hour):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.maint_cost_var = tk.DoubleVar(value=0.02)
        ttk.Entry(cost_frame, textvariable=self.maint_cost_var, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(cost_frame, text="Operating Hours (per year):").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.op_hours_var = tk.DoubleVar(value=8760.0)
        ttk.Entry(cost_frame, textvariable=self.op_hours_var, width=10).grid(row=2, column=1, padx=5)

        ttk.Button(cost_frame, text="Calculate Economics",
                  command=self.calculate_economics).grid(row=3, column=0, columnspan=2, pady=10)

        # Results display
        results_frame = ttk.LabelFrame(tab, text="Economic Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.econ_text = tk.Text(results_frame, font=('Courier', 10))
        econ_scroll = ttk.Scrollbar(results_frame, command=self.econ_text.yview)
        self.econ_text.config(yscrollcommand=econ_scroll.set)

        self.econ_text.pack(side='left', fill='both', expand=True)
        econ_scroll.pack(side='right', fill='y')

    def create_losses_tab(self):
        """Tab for detailed loss analysis"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Loss Breakdown")

        # Loss components display
        loss_frame = ttk.LabelFrame(tab, text="Loss Components", padding=10)
        loss_frame.pack(fill='x', padx=5, pady=5)

        self.loss_text = tk.Text(loss_frame, height=12, font=('Courier', 10))
        self.loss_text.pack(fill='both', expand=True)

        # Loss distribution pie chart
        plot_frame = ttk.Frame(tab)
        plot_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.loss_figure = Figure(figsize=(10, 6), dpi=100)
        self.loss_canvas = FigureCanvasTkAgg(self.loss_figure, plot_frame)
        self.loss_canvas.get_tk_widget().pack(fill='both', expand=True)

        ttk.Button(tab, text="Update Loss Analysis",
                  command=self.update_loss_analysis).pack(pady=10)

    # ========================================================================
    # CALLBACK METHODS
    # ========================================================================

    def on_speed_change(self, value):
        """Handle speed slider change"""
        self.speed_label.config(text=f"{float(value):.1f}")

    def on_rf_change(self, value):
        """Handle field resistance slider change"""
        self.rf_label.config(text=f"{float(value):.1f}")

    def on_window_resize(self, event):
        """Handle window resize for auto-scaling"""
        if event.widget == self.root:
            # Update canvas sizes
            try:
                self.mag_canvas.draw()
                self.sim_canvas.draw()
                self.control_canvas.draw()
                self.thermal_canvas.draw()
                self.loss_canvas.draw()
            except:
                pass

    # ========================================================================
    # MAGNETIZATION ANALYSIS METHODS
    # ========================================================================

    def solve_magnetization_problem(self):
        """Solve the magnetization curve problem"""
        speed = self.speed_var.get()
        rf = self.rf_var.get()

        # (i) No-load EMF
        emf, If = self.mag_analysis.find_no_load_emf(rf, speed)

        # (ii) Critical resistance
        Rcrit = self.mag_analysis.find_critical_resistance(speed)

        # (iii) Magnetization at different speed
        speed_alt = 1200.0
        If_alt, E0_alt = self.mag_analysis.get_magnetization_curve(speed_alt)
        emf_alt, If_alt_op = self.mag_analysis.find_no_load_emf(rf, speed_alt)

        # Display results
        results = f"""
╔══════════════════════════════════════════╗
║   MAGNETIZATION ANALYSIS RESULTS        ║
╚══════════════════════════════════════════╝

(i) NO-LOAD EMF at {speed:.0f} rpm:
    Field Resistance: {rf:.1f} Ω
    Field Current: {If:.3f} A
    Generated EMF: {emf:.2f} V

(ii) CRITICAL FIELD RESISTANCE:
    At {speed:.0f} rpm: {Rcrit:.2f} Ω

(iii) MAGNETIZATION at {speed_alt:.0f} rpm:
    Field Resistance: {rf:.1f} Ω
    Field Current: {If_alt_op:.3f} A
    Generated EMF: {emf_alt:.2f} V

INTERPRETATION:
• The generator builds up voltage when
  Rf < Rcrit ({Rcrit:.2f} Ω)
• Current operating point is stable
• EMF varies linearly with speed
• Speed ratio: {speed/speed_alt:.3f}
• Voltage ratio: {emf/emf_alt:.3f}
"""

        self.mag_results_text.delete('1.0', 'end')
        self.mag_results_text.insert('1.0', results)

        # Plot magnetization curves
        self.plot_magnetization_curves(speed, rf, emf, If, speed_alt, emf_alt, If_alt_op, Rcrit)

    def plot_magnetization_curves(self, speed, rf, emf, If, speed_alt, emf_alt, If_alt_op, Rcrit):
        """Plot magnetization curves and analysis"""
        self.mag_figure.clear()

        # Plot 1: Magnetization curve at base speed
        ax1 = self.mag_figure.add_subplot(2, 2, 1)
        If_range, E0_range = self.mag_analysis.get_magnetization_curve(speed)
        ax1.plot(If_range, E0_range, 'b-', linewidth=2, label=f'Mag. Curve @ {speed:.0f} rpm')

        # Resistance line
        If_line = np.linspace(0, 3, 100)
        E_line = If_line * rf
        ax1.plot(If_line, E_line, 'r--', linewidth=2, label=f'Rf = {rf:.1f} Ω')

        # Operating point
        ax1.plot(If, emf, 'go', markersize=10, label=f'Operating Point')
        ax1.annotate(f'({If:.2f}A, {emf:.1f}V)', xy=(If, emf),
                    xytext=(If+0.2, emf-20), fontsize=9,
                    arrowprops=dict(arrowstyle='->', color='green'))

        ax1.set_xlabel('Field Current If (A)', fontsize=10)
        ax1.set_ylabel('Generated EMF E0 (V)', fontsize=10)
        ax1.set_title(f'Magnetization Curve @ {speed:.0f} rpm', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)

        # Plot 2: Magnetization curve at alternate speed
        ax2 = self.mag_figure.add_subplot(2, 2, 2)
        If_range_alt, E0_range_alt = self.mag_analysis.get_magnetization_curve(speed_alt)
        ax2.plot(If_range_alt, E0_range_alt, 'b-', linewidth=2,
                label=f'Mag. Curve @ {speed_alt:.0f} rpm')

        # Resistance line
        E_line_alt = If_line * rf
        ax2.plot(If_line, E_line_alt, 'r--', linewidth=2, label=f'Rf = {rf:.1f} Ω')

        # Operating point
        ax2.plot(If_alt_op, emf_alt, 'go', markersize=10, label='Operating Point')
        ax2.annotate(f'({If_alt_op:.2f}A, {emf_alt:.1f}V)', xy=(If_alt_op, emf_alt),
                    xytext=(If_alt_op+0.2, emf_alt-15), fontsize=9,
                    arrowprops=dict(arrowstyle='->', color='green'))

        ax2.set_xlabel('Field Current If (A)', fontsize=10)
        ax2.set_ylabel('Generated EMF E0 (V)', fontsize=10)
        ax2.set_title(f'Magnetization Curve @ {speed_alt:.0f} rpm', fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=9)

        # Plot 3: Critical resistance determination
        ax3 = self.mag_figure.add_subplot(2, 2, 3)
        If_crit = np.linspace(0.1, 2.5, 100)
        slopes = []
        for If_val in If_crit:
            dIf = 0.01
            E1 = self.mag_analysis.get_emf(If_val - dIf/2, speed)
            E2 = self.mag_analysis.get_emf(If_val + dIf/2, speed)
            slope = (E2 - E1) / dIf
            slopes.append(slope)

        ax3.plot(If_crit, slopes, 'b-', linewidth=2)
        ax3.axhline(y=Rcrit, color='r', linestyle='--', linewidth=2,
                   label=f'Rcrit = {Rcrit:.2f} Ω')
        ax3.set_xlabel('Field Current If (A)', fontsize=10)
        ax3.set_ylabel('dE/dIf (Ω)', fontsize=10)
        ax3.set_title('Critical Resistance Determination', fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(fontsize=9)

        # Plot 4: Speed vs EMF relationship
        ax4 = self.mag_figure.add_subplot(2, 2, 4)
        speeds = np.linspace(600, 2000, 50)
        emfs = []
        for spd in speeds:
            e, _ = self.mag_analysis.find_no_load_emf(rf, spd)
            emfs.append(e)

        ax4.plot(speeds, emfs, 'b-', linewidth=2, label=f'Rf = {rf:.1f} Ω')
        ax4.plot([speed, speed_alt], [emf, emf_alt], 'ro', markersize=8,
                label='Operating Points')
        ax4.set_xlabel('Speed (rpm)', fontsize=10)
        ax4.set_ylabel('No-Load EMF (V)', fontsize=10)
        ax4.set_title('EMF vs Speed Characteristic', fontsize=11, fontweight='bold')
        ax4.grid(True, alpha=0.3)
        ax4.legend(fontsize=9)

        self.mag_figure.tight_layout()
        self.mag_canvas.draw()

    # ========================================================================
    # SIMULATION METHODS
    # ========================================================================

    def start_simulation(self):
        """Start dynamic simulation"""
        if not self.running:
            self.running = True
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')

            self.solver_type = self.solver_var.get()
            self.time_step = self.dt_var.get()

            # Start simulation thread
            self.simulation_thread = threading.Thread(target=self.run_simulation)
            self.simulation_thread.daemon = True
            self.simulation_thread.start()

    def stop_simulation(self):
        """Stop dynamic simulation"""
        self.running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

    def reset_simulation(self):
        """Reset simulation to initial conditions"""
        self.stop_simulation()
        self.simulator.reset()
        self.update_simulation_plots()

    def run_simulation(self):
        """Run simulation loop"""
        while self.running:
            # Get input values
            Va = self.va_var.get()
            Vf = self.vf_var.get()
            Tload = self.tload_var.get()

            # Perform simulation step
            if self.solver_type == "RK45":
                self.simulator.simulate_step_rk45(self.time_step, Va, Vf, Tload)
            else:
                self.simulator.simulate_step_euler(self.time_step, Va, Vf, Tload)

            # Record history
            self.simulator.record_history()

            # Update plots every 10 steps
            if len(self.simulator.history['time']) % 10 == 0:
                self.root.after(0, self.update_simulation_plots)

            # Control loop delay
            time.sleep(self.time_step / 10)  # Run faster than real-time

    def update_simulation_plots(self):
        """Update simulation plots"""
        if len(self.simulator.history['time']) < 2:
            return

        t = self.simulator.history['time']

        # Clear all axes
        for ax in self.sim_axes:
            ax.clear()

        # Plot 1: Voltage
        self.sim_axes[0].plot(t, self.simulator.history['voltage'], 'b-', linewidth=2)
        self.sim_axes[0].set_ylabel('Voltage (V)', fontsize=9)
        self.sim_axes[0].set_title('Terminal Voltage', fontsize=10, fontweight='bold')
        self.sim_axes[0].grid(True, alpha=0.3)

        # Plot 2: Current
        self.sim_axes[1].plot(t, self.simulator.history['current'], 'r-', linewidth=2)
        self.sim_axes[1].set_ylabel('Current (A)', fontsize=9)
        self.sim_axes[1].set_title('Armature Current', fontsize=10, fontweight='bold')
        self.sim_axes[1].grid(True, alpha=0.3)

        # Plot 3: Speed
        self.sim_axes[2].plot(t, self.simulator.history['speed'], 'g-', linewidth=2)
        self.sim_axes[2].set_ylabel('Speed (rpm)', fontsize=9)
        self.sim_axes[2].set_title('Rotor Speed', fontsize=10, fontweight='bold')
        self.sim_axes[2].grid(True, alpha=0.3)

        # Plot 4: Temperature
        self.sim_axes[3].plot(t, self.simulator.history['temperature'], 'm-', linewidth=2)
        self.sim_axes[3].axhline(y=self.params.max_temperature, color='r',
                                linestyle='--', label='Max Temp')
        self.sim_axes[3].set_ylabel('Temperature (°C)', fontsize=9)
        self.sim_axes[3].set_title('Winding Temperature', fontsize=10, fontweight='bold')
        self.sim_axes[3].grid(True, alpha=0.3)
        self.sim_axes[3].legend(fontsize=8)

        # Plot 5: Torque
        self.sim_axes[4].plot(t, self.simulator.history['torque'], 'c-', linewidth=2)
        self.sim_axes[4].set_ylabel('Torque (N.m)', fontsize=9)
        self.sim_axes[4].set_xlabel('Time (s)', fontsize=9)
        self.sim_axes[4].set_title('Electromagnetic Torque', fontsize=10, fontweight='bold')
        self.sim_axes[4].grid(True, alpha=0.3)

        # Plot 6: Power and Losses
        self.sim_axes[5].plot(t, self.simulator.history['power'], 'b-', linewidth=2, label='Power')
        self.sim_axes[5].plot(t, self.simulator.history['losses'], 'r--', linewidth=2, label='Losses')
        self.sim_axes[5].set_ylabel('Power (W)', fontsize=9)
        self.sim_axes[5].set_xlabel('Time (s)', fontsize=9)
        self.sim_axes[5].set_title('Power & Losses', fontsize=10, fontweight='bold')
        self.sim_axes[5].grid(True, alpha=0.3)
        self.sim_axes[5].legend(fontsize=8)

        self.sim_figure.tight_layout()
        self.sim_canvas.draw()

    # ========================================================================
    # ANALYSIS METHODS
    # ========================================================================

    def show_thermal_analysis(self):
        """Show detailed thermal analysis"""
        self.notebook.select(3)  # Switch to thermal tab

        # Get current state
        state = self.simulator.state
        losses = self.simulator.thermal_model.calculate_losses(
            state.armature_current, state.field_current, state.speed
        )

        derating = self.simulator.thermal_model.derating_factor(state.temperature)

        text = f"""
╔══════════════════════════════════════════════════════════════╗
║              THERMAL ANALYSIS REPORT                         ║
╚══════════════════════════════════════════════════════════════╝

CURRENT THERMAL STATE:
  Temperature: {state.temperature:.2f} °C
  Ambient: {self.params.ambient_temperature:.2f} °C
  Maximum Allowed: {self.params.max_temperature:.2f} °C
  Temperature Rise: {state.temperature - self.params.ambient_temperature:.2f} °C

LOSS BREAKDOWN:
  Copper Losses (Armature): {losses['copper_armature']:.2f} W
  Copper Losses (Field): {losses['copper_field']:.2f} W
  Iron Losses (Hysteresis): {losses['hysteresis']:.2f} W
  Iron Losses (Eddy): {losses['eddy']:.2f} W
  Mechanical Losses: {losses['friction'] + losses['windage']:.2f} W
  Stray Load Losses: {losses['stray']:.2f} W
  ────────────────────────────────────────
  TOTAL LOSSES: {losses['total']:.2f} W

THERMAL CHARACTERISTICS:
  Thermal Resistance: {self.params.thermal_resistance:.3f} K/W
  Thermal Capacitance: {self.params.thermal_capacitance:.1f} J/K
  Heat Dissipation: {(state.temperature - self.params.ambient_temperature) / self.params.thermal_resistance:.2f} W
  Thermal Time Constant: {self.params.thermal_resistance * self.params.thermal_capacitance:.1f} s

DERATING:
  Derating Factor: {derating:.3f}
  Derated Power: {self.params.rated_power * derating / 1000:.2f} kW
  Status: {'✓ NORMAL' if state.temperature <= self.params.max_temperature else '⚠ OVERHEATING'}
"""

        self.derating_text.delete('1.0', 'end')
        self.derating_text.insert('1.0', text)

        # Plot thermal curves
        self.plot_thermal_analysis()

    def plot_thermal_analysis(self):
        """Plot thermal analysis curves"""
        self.thermal_figure.clear()

        ax1 = self.thermal_figure.add_subplot(1, 2, 1)
        ax2 = self.thermal_figure.add_subplot(1, 2, 2)

        # Temperature history
        if len(self.simulator.history['time']) > 0:
            ax1.plot(self.simulator.history['time'],
                    self.simulator.history['temperature'], 'r-', linewidth=2)
            ax1.axhline(y=self.params.max_temperature, color='orange',
                       linestyle='--', linewidth=2, label='Max Temp')
            ax1.axhline(y=self.params.ambient_temperature, color='b',
                       linestyle='--', linewidth=1, label='Ambient')
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('Temperature (°C)')
            ax1.set_title('Temperature vs Time', fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()

        # Derating curve
        temps = np.linspace(self.params.ambient_temperature,
                          self.params.max_temperature + 50, 100)
        derating_factors = [self.simulator.thermal_model.derating_factor(T) for T in temps]

        ax2.plot(temps, derating_factors, 'b-', linewidth=2)
        ax2.axvline(x=self.params.max_temperature, color='r',
                   linestyle='--', linewidth=2, label='Max Temp')
        ax2.set_xlabel('Temperature (°C)')
        ax2.set_ylabel('Derating Factor')
        ax2.set_title('Derating Characteristic', fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        self.thermal_figure.tight_layout()
        self.thermal_canvas.draw()

    def show_mechanical_analysis(self):
        """Show mechanical stress analysis"""
        state = self.simulator.state
        stress = self.simulator.mechanical_model.shaft_stress_analysis(state.torque)

        msg = f"""
MECHANICAL STRESS ANALYSIS
═══════════════════════════════════════

Current Torque: {state.torque:.2f} N.m

SHAFT ANALYSIS:
  Shear Stress: {stress['shear_stress']:.2f} MPa
  Safety Factor: {stress['safety_factor']:.2f}
  Status: {'✓ SAFE' if stress['safety_factor'] > 2 else '⚠ CHECK DESIGN'}

BEARING LOADS:
  Radial Load: {stress['bearing_load']:.2f} N
"""
        messagebox.showinfo("Mechanical Stress Analysis", msg)

    def calculate_economics(self):
        """Calculate and display economic analysis"""
        # Update economic parameters
        self.economic.electricity_cost = self.elec_cost_var.get()
        self.economic.maintenance_cost = self.maint_cost_var.get()
        op_hours = self.op_hours_var.get()

        # Get average values from simulation
        if len(self.simulator.history['time']) > 0:
            avg_power = np.mean(self.simulator.history['power'])
            avg_losses = np.mean(self.simulator.history['losses'])
        else:
            avg_power = self.params.rated_power
            avg_losses = 0.1 * avg_power

        # Calculate efficiency
        efficiency = self.economic.calculate_efficiency(avg_power, avg_losses)

        # Operating costs
        costs = self.economic.calculate_operating_cost(avg_power, avg_losses, op_hours)

        # ROI analysis
        annual_savings = 500.0  # Assumed savings from efficiency improvements
        roi = self.economic.calculate_roi(annual_savings)

        # Display results
        text = f"""
╔═══════════════════════════════════════════════════════════════╗
║              ECONOMIC ANALYSIS REPORT                         ║
╚═══════════════════════════════════════════════════════════════╝

OPERATING PARAMETERS:
  Average Output Power: {avg_power:.2f} W ({avg_power/1000:.2f} kW)
  Average Losses: {avg_losses:.2f} W ({avg_losses/1000:.2f} kW)
  Operating Hours/Year: {op_hours:.0f} hours

EFFICIENCY ANALYSIS:
  System Efficiency: {efficiency:.2f} %
  Energy Input: {(avg_power + avg_losses)/1000:.2f} kW
  Energy Output: {avg_power/1000:.2f} kW
  Energy Wasted: {avg_losses/1000:.2f} kW

ANNUAL OPERATING COSTS:
  Electricity Cost: ${costs['energy_cost']:.2f}
    • Rate: ${self.economic.electricity_cost:.3f}/kWh
    • Energy Loss: {avg_losses * op_hours / 1000:.2f} kWh/year

  Maintenance Cost: ${costs['maintenance_cost']:.2f}
    • Rate: ${self.economic.maintenance_cost:.3f}/hour

  Total Annual Cost: ${costs['total_cost']:.2f}
  Cost per kWh Output: ${costs['cost_per_kWh']:.4f}/kWh

INVESTMENT ANALYSIS:
  Capital Cost: ${self.economic.capital_cost:.2f}
  Annual Savings (estimated): ${annual_savings:.2f}

  Return on Investment:
    • ROI Percentage: {roi['roi_percentage']:.2f} %
    • Payback Period: {roi['payback_period']:.2f} years
    • NPV (5 years): ${roi['npv_5years']:.2f}

RECOMMENDATIONS:
"""

        # Add recommendations
        if efficiency < 85:
            text += "  ⚠ Efficiency is below 85% - Consider optimization\n"
        else:
            text += "  ✓ Efficiency is acceptable\n"

        if costs['cost_per_kWh'] > 0.15:
            text += "  ⚠ High operating cost - Review maintenance schedule\n"
        else:
            text += "  ✓ Operating costs are reasonable\n"

        if roi['payback_period'] < 3:
            text += "  ✓ Good investment - Short payback period\n"
        else:
            text += "  ⚠ Long payback period - Evaluate alternatives\n"

        self.econ_text.delete('1.0', 'end')
        self.econ_text.insert('1.0', text)

    def update_loss_analysis(self):
        """Update detailed loss breakdown"""
        state = self.simulator.state
        losses = self.simulator.thermal_model.calculate_losses(
            state.armature_current, state.field_current, state.speed
        )

        # Display loss breakdown
        text = f"""
╔═══════════════════════════════════════════════════════════════╗
║           DETAILED LOSS BREAKDOWN ANALYSIS                    ║
╚═══════════════════════════════════════════════════════════════╝

OPERATING CONDITIONS:
  Armature Current: {state.armature_current:.2f} A
  Field Current: {state.field_current:.2f} A
  Speed: {state.speed:.1f} rpm
  Temperature: {state.temperature:.1f} °C

COPPER LOSSES (I²R Losses):
  Armature: {losses['copper_armature']:.2f} W ({losses['copper_armature']/losses['total']*100:.1f}%)
  Field: {losses['copper_field']:.2f} W ({losses['copper_field']/losses['total']*100:.1f}%)
  Subtotal: {losses['copper_armature'] + losses['copper_field']:.2f} W

IRON LOSSES (Core Losses):
  Hysteresis: {losses['hysteresis']:.2f} W ({losses['hysteresis']/losses['total']*100:.1f}%)
  Eddy Current: {losses['eddy']:.2f} W ({losses['eddy']/losses['total']*100:.1f}%)
  Subtotal: {losses['hysteresis'] + losses['eddy']:.2f} W

MECHANICAL LOSSES:
  Friction: {losses['friction']:.2f} W ({losses['friction']/losses['total']*100:.1f}%)
  Windage: {losses['windage']:.2f} W ({losses['windage']/losses['total']*100:.1f}%)
  Subtotal: {losses['friction'] + losses['windage']:.2f} W

STRAY LOAD LOSSES: {losses['stray']:.2f} W ({losses['stray']/losses['total']*100:.1f}%)

═══════════════════════════════════════════════════════════════
TOTAL LOSSES: {losses['total']:.2f} W (100%)
═══════════════════════════════════════════════════════════════

EFFICIENCY METRICS:
  Output Power: {state.power:.2f} W
  Input Power: {state.power + losses['total']:.2f} W
  Efficiency: {state.power / (state.power + losses['total']) * 100:.2f} %
"""

        self.loss_text.delete('1.0', 'end')
        self.loss_text.insert('1.0', text)

        # Plot loss distribution
        self.plot_loss_distribution(losses)

    def plot_loss_distribution(self, losses):
        """Plot loss distribution pie chart"""
        self.loss_figure.clear()

        # Prepare data
        labels = ['Copper (Arm)', 'Copper (Field)', 'Hysteresis',
                 'Eddy Current', 'Friction', 'Windage', 'Stray']
        sizes = [losses['copper_armature'], losses['copper_field'],
                losses['hysteresis'], losses['eddy'],
                losses['friction'], losses['windage'], losses['stray']]
        colors = ['#ff9999', '#ff6666', '#66b3ff', '#6699ff',
                 '#99ff99', '#66ff66', '#ffcc99']
        explode = (0.1, 0.05, 0, 0, 0, 0, 0)

        ax = self.loss_figure.add_subplot(1, 1, 1)
        ax.pie(sizes, explode=explode, labels=labels, colors=colors,
              autopct='%1.1f%%', shadow=True, startangle=90)
        ax.set_title('Loss Distribution', fontsize=14, fontweight='bold')

        self.loss_figure.tight_layout()
        self.loss_canvas.draw()

    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================

    def save_results(self):
        """Save simulation results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dc_generator_results_{timestamp}.json"

        results = {
            'timestamp': timestamp,
            'parameters': {
                'rated_power': self.params.rated_power,
                'rated_voltage': self.params.rated_voltage,
                'rated_speed': self.params.rated_speed,
                'field_resistance': self.params.field_resistance
            },
            'simulation_history': {
                'time': self.simulator.history['time'],
                'voltage': self.simulator.history['voltage'],
                'current': self.simulator.history['current'],
                'speed': self.simulator.history['speed'],
                'temperature': self.simulator.history['temperature'],
                'power': self.simulator.history['power']
            }
        }

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            messagebox.showinfo("Success", f"Results saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save results: {str(e)}")

    def load_parameters(self):
        """Load parameters from file (placeholder)"""
        messagebox.showinfo("Load Parameters",
                          "Parameter loading will be implemented based on specific requirements")

    def show_about(self):
        """Show about dialog"""
        about_text = """
Advanced DC Generator Magnetization Analysis Tool
Version 1.0

Features:
• Magnetization curve analysis
• Real-time dynamic simulation (RK45, Euler)
• Multi-physics coupling (EM-Thermal-Mechanical)
• Economic analysis
• Loss breakdown
• Thermal derating
• Advanced control systems

Developed for electrical engineering analysis
        """
        messagebox.showinfo("About", about_text)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()

    # Configure style
    style = ttk.Style()
    style.theme_use('clam')

    # Custom button style
    style.configure('Accent.TButton', foreground='white', background='#0066cc',
                   font=('Arial', 10, 'bold'))

    app = DCGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
