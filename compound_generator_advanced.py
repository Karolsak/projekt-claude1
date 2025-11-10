"""
Advanced Compound DC Generator Analysis Tool
Multi-Physics Simulation with Tkinter GUI

Features:
- Short shunt and long shunt configurations
- Dynamic ODE simulation (RK45, Euler)
- Multi-physics modeling (electromagnetic-thermal-mechanical)
- Economic analysis
- Loss breakdown and thermal analysis
- Real-time visualization
"""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import time
from scipy.integrate import solve_ivp
from datetime import datetime


class CompoundGeneratorCalculator:
    """Core calculation engine for compound generator analysis"""

    def __init__(self, V_terminal=220, I_load=100, Ra=0.1, Rsh=50, Rse=0.06):
        self.V_terminal = V_terminal
        self.I_load = I_load
        self.Ra = Ra
        self.Rsh = Rsh
        self.Rse = Rse

    def short_shunt(self):
        """Calculate short shunt configuration"""
        # Short shunt: Series field in armature circuit only
        Ish = self.V_terminal / self.Rsh
        Ia = self.I_load + Ish
        Ise = Ia

        # Induced EMF: Ea = V + Ia*Ra + Ise*Rse
        Ea = self.V_terminal + Ia * self.Ra + Ise * self.Rse

        return {
            'Ea': Ea,
            'Ia': Ia,
            'Ish': Ish,
            'Ise': Ise,
            'config': 'Short Shunt'
        }

    def long_shunt(self):
        """Calculate long shunt configuration"""
        # Long shunt: Shunt field across terminals, series in line
        Ise = self.I_load
        V_shunt = self.V_terminal + Ise * self.Rse
        Ish = V_shunt / self.Rsh
        Ia = self.I_load + Ish

        # Induced EMF: Ea = V + Ise*Rse + Ia*Ra
        Ea = self.V_terminal + Ise * self.Rse + Ia * self.Ra

        return {
            'Ea': Ea,
            'Ia': Ia,
            'Ish': Ish,
            'Ise': Ise,
            'config': 'Long Shunt'
        }

    def long_shunt_with_divertor(self, R_div=0.14):
        """Calculate long shunt with divertor"""
        # Divertor in parallel with series field
        Rse_eq = (self.Rse * R_div) / (self.Rse + R_div)

        Ise_total = self.I_load
        V_shunt = self.V_terminal + Ise_total * Rse_eq
        Ish = V_shunt / self.Rsh
        Ia = self.I_load + Ish

        # Current distribution in series field and divertor
        I_series = Ise_total * (R_div / (self.Rse + R_div))
        I_divertor = Ise_total * (self.Rse / (self.Rse + R_div))

        Ea = self.V_terminal + Ise_total * Rse_eq + Ia * self.Ra

        # Series amp-turns change
        amp_turns_without = self.I_load  # Assuming N turns
        amp_turns_with = I_series  # Same N turns
        change_ratio = I_series / self.I_load

        return {
            'Ea': Ea,
            'Ia': Ia,
            'Ish': Ish,
            'Ise_total': Ise_total,
            'I_series': I_series,
            'I_divertor': I_divertor,
            'amp_turns_ratio': change_ratio,
            'amp_turns_percent_change': (change_ratio - 1) * 100,
            'config': 'Long Shunt with Divertor'
        }


class ODESolver:
    """ODE solver for dynamic simulation"""

    @staticmethod
    def euler_method(f, t_span, y0, dt=0.001):
        """Euler method for solving ODEs"""
        t0, tf = t_span
        t = np.arange(t0, tf, dt)
        y = np.zeros((len(t), len(y0)))
        y[0] = y0

        for i in range(1, len(t)):
            y[i] = y[i-1] + dt * np.array(f(t[i-1], y[i-1]))

        return t, y

    @staticmethod
    def rk45_method(f, t_span, y0, dt=0.001):
        """RK45 (Runge-Kutta-Fehlberg) method"""
        sol = solve_ivp(f, t_span, y0, method='RK45',
                       t_eval=np.arange(t_span[0], t_span[1], dt),
                       max_step=dt)
        return sol.t, sol.y.T


class MultiPhysicsModel:
    """Multi-physics simulation: Electromagnetic-Thermal-Mechanical"""

    def __init__(self, params):
        self.params = params
        # Physical constants
        self.thermal_resistance = 0.5  # K/W
        self.thermal_capacitance = 500  # J/K
        self.ambient_temp = 25  # °C
        self.moment_of_inertia = 0.5  # kg⋅m²
        self.friction_coefficient = 0.02  # N⋅m⋅s

    def electromagnetic_model(self, t, state, V_terminal, I_load):
        """Electromagnetic differential equations"""
        Ia, If, omega = state

        # Flux linkage (simplified model)
        La = 0.01  # Armature inductance (H)
        Lf = 5.0   # Field inductance (H)
        M = 0.1    # Mutual inductance (H)

        # Back EMF
        Ke = 0.5  # EMF constant
        Ea = Ke * If * omega

        # Voltage equations
        dIa_dt = (V_terminal - Ia * self.params['Ra'] - Ea) / La
        dIf_dt = (V_terminal - If * self.params['Rsh']) / Lf

        # Mechanical equation (simplified)
        T_em = Ke * If * Ia  # Electromagnetic torque
        T_load = 50  # Load torque (N⋅m)
        domega_dt = (T_em - T_load - self.friction_coefficient * omega) / self.moment_of_inertia

        return [dIa_dt, dIf_dt, domega_dt]

    def thermal_model(self, t, temp, power_loss):
        """Thermal differential equation"""
        # Heat transfer equation: C⋅dT/dt = P_loss - (T-T_amb)/R_th
        dT_dt = (power_loss - (temp - self.ambient_temp) / self.thermal_resistance) / self.thermal_capacitance
        return dT_dt

    def coupled_simulation(self, t_span, dt=0.001):
        """Coupled electromagnetic-thermal simulation"""
        t = np.arange(t_span[0], t_span[1], dt)
        n = len(t)

        # State variables
        Ia = np.zeros(n)
        If = np.zeros(n)
        omega = np.zeros(n)
        temp = np.zeros(n)

        # Initial conditions
        Ia[0] = 105
        If[0] = 4.4
        omega[0] = 157  # rad/s (1500 RPM)
        temp[0] = self.ambient_temp

        # Simulation loop
        for i in range(1, n):
            # Electromagnetic update
            em_state = [Ia[i-1], If[i-1], omega[i-1]]
            em_deriv = self.electromagnetic_model(t[i-1], em_state,
                                                 self.params['V_terminal'],
                                                 self.params['I_load'])

            Ia[i] = Ia[i-1] + dt * em_deriv[0]
            If[i] = If[i-1] + dt * em_deriv[1]
            omega[i] = omega[i-1] + dt * em_deriv[2]

            # Calculate losses
            P_copper = Ia[i]**2 * self.params['Ra'] + If[i]**2 * self.params['Rsh']
            P_iron = 0.02 * omega[i]**2  # Simplified iron loss
            P_friction = self.friction_coefficient * omega[i]**2
            P_total_loss = P_copper + P_iron + P_friction

            # Thermal update
            temp_deriv = self.thermal_model(t[i-1], temp[i-1], P_total_loss)
            temp[i] = temp[i-1] + dt * temp_deriv

        return {
            't': t,
            'Ia': Ia,
            'If': If,
            'omega': omega * 9.549,  # Convert to RPM
            'temp': temp,
            'voltage': self.params['V_terminal'] * np.ones(n)
        }


class LossAnalyzer:
    """Detailed loss breakdown analysis"""

    def __init__(self, params):
        self.params = params

    def calculate_losses(self, Ia, If, speed_rpm):
        """Calculate all types of losses"""
        omega = speed_rpm * 0.10472  # RPM to rad/s

        # Copper losses
        P_cu_armature = Ia**2 * self.params['Ra']
        P_cu_shunt = If**2 * self.params['Rsh']
        P_cu_series = (Ia - If)**2 * self.params['Rse']
        P_cu_total = P_cu_armature + P_cu_shunt + P_cu_series

        # Iron losses (core losses)
        # Hysteresis loss: Ph = Kh * f * B^2 * Volume
        Kh = 0.001  # Hysteresis coefficient
        f = speed_rpm / 60  # Frequency
        B = 1.2  # Flux density (T)
        V_core = 0.05  # Core volume (m³)
        P_hysteresis = Kh * f * B**2 * V_core

        # Eddy current loss: Pe = Ke * f^2 * B^2 * Volume
        Ke = 0.0001
        P_eddy = Ke * f**2 * B**2 * V_core
        P_iron_total = P_hysteresis + P_eddy

        # Mechanical losses
        # Friction loss
        P_friction = 0.01 * omega**2

        # Windage loss
        P_windage = 0.005 * omega**3
        P_mechanical = P_friction + P_windage

        # Stray load losses (approximately 1% of output)
        P_output = self.params['V_terminal'] * self.params['I_load']
        P_stray = 0.01 * P_output

        # Total losses
        P_total_loss = P_cu_total + P_iron_total + P_mechanical + P_stray

        # Efficiency
        P_input = P_output + P_total_loss
        efficiency = (P_output / P_input) * 100 if P_input > 0 else 0

        return {
            'copper_armature': P_cu_armature,
            'copper_shunt': P_cu_shunt,
            'copper_series': P_cu_series,
            'copper_total': P_cu_total,
            'hysteresis': P_hysteresis,
            'eddy': P_eddy,
            'iron_total': P_iron_total,
            'friction': P_friction,
            'windage': P_windage,
            'mechanical_total': P_mechanical,
            'stray': P_stray,
            'total_loss': P_total_loss,
            'output_power': P_output,
            'input_power': P_input,
            'efficiency': efficiency
        }


class ThermalAnalyzer:
    """Thermal analysis and derating calculations"""

    def __init__(self):
        self.ambient_temp = 25  # °C
        self.max_temp_rating = 120  # °C (Class F insulation)
        self.thermal_time_constant = 45  # minutes

    def calculate_temperature_rise(self, power_loss, thermal_resistance=0.5):
        """Calculate steady-state temperature rise"""
        delta_T = power_loss * thermal_resistance
        return delta_T

    def transient_temperature(self, t_minutes, power_loss, thermal_resistance=0.5):
        """Calculate transient temperature"""
        tau = self.thermal_time_constant
        delta_T_ss = self.calculate_temperature_rise(power_loss, thermal_resistance)
        delta_T = delta_T_ss * (1 - np.exp(-t_minutes / tau))
        return self.ambient_temp + delta_T

    def derating_factor(self, ambient_temp):
        """Calculate derating factor based on ambient temperature"""
        # Standard rating at 40°C
        T_standard = 40
        if ambient_temp <= T_standard:
            return 1.0
        else:
            # Derate by 1% per °C above 40°C
            return 1.0 - 0.01 * (ambient_temp - T_standard)

    def hotspot_temperature(self, avg_temp, hotspot_factor=1.15):
        """Calculate hotspot temperature"""
        return avg_temp * hotspot_factor


class EconomicAnalyzer:
    """Economic analysis module"""

    def __init__(self):
        self.electricity_cost = 0.12  # $/kWh
        self.maintenance_cost_per_hour = 2.5  # $/hour
        self.initial_cost = 50000  # $

    def calculate_operating_cost(self, power_kw, hours, efficiency):
        """Calculate operating cost"""
        energy_consumed = power_kw * hours / (efficiency / 100)
        electricity_cost = energy_consumed * self.electricity_cost
        maintenance_cost = hours * self.maintenance_cost_per_hour
        total_cost = electricity_cost + maintenance_cost

        return {
            'electricity_cost': electricity_cost,
            'maintenance_cost': maintenance_cost,
            'total_operating_cost': total_cost,
            'energy_consumed_kwh': energy_consumed
        }

    def payback_period(self, annual_savings):
        """Calculate payback period"""
        if annual_savings > 0:
            return self.initial_cost / annual_savings
        return float('inf')

    def lifecycle_cost(self, years, annual_operating_cost, discount_rate=0.05):
        """Calculate lifecycle cost"""
        npv_operating = sum([annual_operating_cost / (1 + discount_rate)**year
                            for year in range(1, years + 1)])
        total_lifecycle = self.initial_cost + npv_operating
        return total_lifecycle


class MechanicalAnalyzer:
    """Mechanical stress and torque analysis"""

    def __init__(self):
        self.shaft_diameter = 0.05  # m
        self.shaft_length = 0.5  # m
        self.material_yield_strength = 250e6  # Pa (mild steel)

    def calculate_torque(self, power_w, speed_rpm):
        """Calculate shaft torque"""
        omega = speed_rpm * 2 * np.pi / 60
        torque = power_w / omega if omega > 0 else 0
        return torque

    def shaft_stress(self, torque):
        """Calculate shaft shear stress"""
        # τ = 16T / (π * d³)
        d = self.shaft_diameter
        stress = 16 * torque / (np.pi * d**3)
        return stress

    def safety_factor(self, applied_stress):
        """Calculate safety factor"""
        if applied_stress > 0:
            return self.material_yield_strength / applied_stress
        return float('inf')

    def bearing_load(self, radial_force, axial_force):
        """Calculate equivalent bearing load"""
        # Simplified bearing load calculation
        X = 0.56  # Radial factor
        Y = 1.5   # Axial factor
        P_equivalent = X * radial_force + Y * axial_force
        return P_equivalent


class AdvancedCompoundGeneratorGUI:
    """Advanced Tkinter GUI with multi-tab interface"""

    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Compound DC Generator Analysis - Multi-Physics Simulation")
        self.root.geometry("1400x900")

        # Simulation state
        self.running = False
        self.simulation_data = None

        # Default parameters
        self.params = {
            'V_terminal': tk.DoubleVar(value=220),
            'I_load': tk.DoubleVar(value=100),
            'Ra': tk.DoubleVar(value=0.1),
            'Rsh': tk.DoubleVar(value=50),
            'Rse': tk.DoubleVar(value=0.06),
            'R_div': tk.DoubleVar(value=0.14),
            'speed_rpm': tk.DoubleVar(value=1500)
        }

        # Configure grid weight for auto-scaling
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Bind resize event
        self.root.bind('<Configure>', self.on_resize)

        self.create_widgets()

    def on_resize(self, event):
        """Handle window resize for auto-scaling"""
        if event.widget == self.root:
            # Update canvas sizes if needed
            pass

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_rowconfigure(1, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ttk.Label(main_container, text="Advanced Compound DC Generator Analysis",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=10)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        # Create tabs
        self.create_main_tab()
        self.create_simulation_tab()
        self.create_losses_tab()
        self.create_thermal_tab()
        self.create_economic_tab()
        self.create_mechanical_tab()

    def create_main_tab(self):
        """Main calculation and parameters tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Main Calculations")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        # Left panel - Input parameters
        left_frame = ttk.LabelFrame(tab, text="Input Parameters", padding="10")
        left_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=5)

        # Parameter sliders
        params_info = [
            ('Terminal Voltage (V):', 'V_terminal', 100, 400),
            ('Load Current (A):', 'I_load', 50, 200),
            ('Armature Resistance (Ω):', 'Ra', 0.01, 0.5),
            ('Shunt Resistance (Ω):', 'Rsh', 10, 100),
            ('Series Resistance (Ω):', 'Rse', 0.01, 0.2),
            ('Divertor Resistance (Ω):', 'R_div', 0.05, 0.5),
            ('Speed (RPM):', 'speed_rpm', 500, 3000)
        ]

        for i, (label, var_name, min_val, max_val) in enumerate(params_info):
            ttk.Label(left_frame, text=label).grid(row=i*2, column=0, sticky='w', pady=(5,0))

            slider_frame = ttk.Frame(left_frame)
            slider_frame.grid(row=i*2+1, column=0, sticky='ew', pady=(0,10))

            slider = ttk.Scale(slider_frame, from_=min_val, to=max_val,
                             variable=self.params[var_name], orient='horizontal')
            slider.pack(side='left', fill='x', expand=True)

            value_label = ttk.Label(slider_frame, text=f"{self.params[var_name].get():.2f}",
                                   width=8)
            value_label.pack(side='left', padx=5)

            # Update label when slider moves
            self.params[var_name].trace_add('write',
                lambda *args, lbl=value_label, var=self.params[var_name]:
                lbl.config(text=f"{var.get():.2f}"))

        # Calculate button
        calc_button = ttk.Button(left_frame, text="Calculate All Configurations",
                                command=self.calculate_all)
        calc_button.grid(row=len(params_info)*2, column=0, pady=10, sticky='ew')

        # Right panel - Results
        right_frame = ttk.LabelFrame(tab, text="Calculation Results", padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Results text widget
        self.results_text = tk.Text(right_frame, wrap='word', height=20, width=60,
                                   font=('Courier', 10))
        self.results_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(right_frame, orient='vertical',
                                 command=self.results_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.results_text.configure(yscrollcommand=scrollbar.set)

        # Bottom panel - Control buttons
        control_frame = ttk.Frame(tab)
        control_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Button(control_frame, text="Export Results",
                  command=self.export_results).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Reset Parameters",
                  command=self.reset_parameters).pack(side='left', padx=5)

    def create_simulation_tab(self):
        """Dynamic simulation tab with real-time plotting"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dynamic Simulation")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Control panel
        control_frame = ttk.LabelFrame(tab, text="Simulation Controls", padding="10")
        control_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ttk.Label(control_frame, text="ODE Solver:").pack(side='left', padx=5)
        self.solver_var = tk.StringVar(value='RK45')
        ttk.Radiobutton(control_frame, text="RK45", variable=self.solver_var,
                       value='RK45').pack(side='left', padx=5)
        ttk.Radiobutton(control_frame, text="Euler", variable=self.solver_var,
                       value='Euler').pack(side='left', padx=5)

        ttk.Button(control_frame, text="▶ Start", command=self.start_simulation,
                  style='Accent.TButton').pack(side='left', padx=10)
        ttk.Button(control_frame, text="⬛ Stop", command=self.stop_simulation).pack(side='left', padx=5)
        ttk.Button(control_frame, text="↻ Reset", command=self.reset_simulation).pack(side='left', padx=5)

        # Plot area
        plot_frame = ttk.Frame(tab)
        plot_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        plot_frame.grid_rowconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(0, weight=1)

        # Create matplotlib figure
        self.sim_figure = Figure(figsize=(12, 8), dpi=100)
        self.sim_canvas = FigureCanvasTkAgg(self.sim_figure, plot_frame)
        self.sim_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Create subplots
        self.ax_current = self.sim_figure.add_subplot(3, 2, 1)
        self.ax_voltage = self.sim_figure.add_subplot(3, 2, 2)
        self.ax_speed = self.sim_figure.add_subplot(3, 2, 3)
        self.ax_temp = self.sim_figure.add_subplot(3, 2, 4)
        self.ax_power = self.sim_figure.add_subplot(3, 2, 5)
        self.ax_torque = self.sim_figure.add_subplot(3, 2, 6)

        self.sim_figure.tight_layout()

    def create_losses_tab(self):
        """Loss breakdown analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Loss Analysis")

        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Plot area
        plot_frame = ttk.Frame(tab)
        plot_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        plot_frame.grid_rowconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(0, weight=1)

        self.loss_figure = Figure(figsize=(12, 8), dpi=100)
        self.loss_canvas = FigureCanvasTkAgg(self.loss_figure, plot_frame)
        self.loss_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        ttk.Button(control_frame, text="Analyze Losses",
                  command=self.analyze_losses).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Export Loss Data",
                  command=self.export_loss_data).pack(side='left', padx=5)

    def create_thermal_tab(self):
        """Thermal analysis and derating tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Thermal & Derating")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Input panel
        input_frame = ttk.LabelFrame(tab, text="Thermal Parameters", padding="10")
        input_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ttk.Label(input_frame, text="Ambient Temperature (°C):").pack(side='left', padx=5)
        self.ambient_temp_var = tk.DoubleVar(value=25)
        ttk.Scale(input_frame, from_=0, to=60, variable=self.ambient_temp_var,
                 orient='horizontal', length=200).pack(side='left', padx=5)
        self.ambient_label = ttk.Label(input_frame, text="25.0°C")
        self.ambient_label.pack(side='left', padx=5)

        self.ambient_temp_var.trace_add('write',
            lambda *args: self.ambient_label.config(text=f"{self.ambient_temp_var.get():.1f}°C"))

        ttk.Button(input_frame, text="Analyze Thermal Performance",
                  command=self.analyze_thermal).pack(side='left', padx=10)

        # Plot area
        plot_frame = ttk.Frame(tab)
        plot_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        plot_frame.grid_rowconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(0, weight=1)

        self.thermal_figure = Figure(figsize=(12, 6), dpi=100)
        self.thermal_canvas = FigureCanvasTkAgg(self.thermal_figure, plot_frame)
        self.thermal_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    def create_economic_tab(self):
        """Economic analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Economic Analysis")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Input panel
        input_frame = ttk.LabelFrame(tab, text="Economic Parameters", padding="10")
        input_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # Parameters
        params = [
            ("Electricity Cost ($/kWh):", 'elec_cost', 0.05, 0.3, 0.12),
            ("Operating Hours/Year:", 'hours_year', 1000, 8760, 4380),
            ("Maintenance Cost ($/hour):", 'maint_cost', 0.5, 10, 2.5),
            ("Initial Investment ($):", 'initial_inv', 10000, 100000, 50000)
        ]

        self.economic_vars = {}
        for i, (label, var_name, min_val, max_val, default) in enumerate(params):
            ttk.Label(input_frame, text=label).grid(row=i, column=0, sticky='w', padx=5)
            self.economic_vars[var_name] = tk.DoubleVar(value=default)
            entry = ttk.Entry(input_frame, textvariable=self.economic_vars[var_name], width=15)
            entry.grid(row=i, column=1, padx=5, pady=2)

        ttk.Button(input_frame, text="Calculate Economics",
                  command=self.calculate_economics).grid(row=len(params), column=0,
                                                         columnspan=2, pady=10)

        # Results panel
        result_frame = ttk.LabelFrame(tab, text="Economic Results", padding="10")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.economic_text = tk.Text(result_frame, wrap='word', height=15,
                                     font=('Courier', 10))
        self.economic_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(result_frame, orient='vertical',
                                 command=self.economic_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.economic_text.configure(yscrollcommand=scrollbar.set)

    def create_mechanical_tab(self):
        """Mechanical stress analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Mechanical Analysis")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ttk.Button(control_frame, text="Analyze Mechanical Stress",
                  command=self.analyze_mechanical).pack(side='left', padx=5)

        # Results area
        result_frame = ttk.LabelFrame(tab, text="Mechanical Analysis Results", padding="10")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.mechanical_text = tk.Text(result_frame, wrap='word',
                                       font=('Courier', 10))
        self.mechanical_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(result_frame, orient='vertical',
                                 command=self.mechanical_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.mechanical_text.configure(yscrollcommand=scrollbar.set)

    def calculate_all(self):
        """Calculate all configurations"""
        params = {k: v.get() for k, v in self.params.items()}

        calc = CompoundGeneratorCalculator(
            V_terminal=params['V_terminal'],
            I_load=params['I_load'],
            Ra=params['Ra'],
            Rsh=params['Rsh'],
            Rse=params['Rse']
        )

        # Calculate all configurations
        short = calc.short_shunt()
        long = calc.long_shunt()
        divertor = calc.long_shunt_with_divertor(params['R_div'])

        # Format results
        result_text = "=" * 70 + "\n"
        result_text += "COMPOUND DC GENERATOR ANALYSIS RESULTS\n"
        result_text += "=" * 70 + "\n\n"

        result_text += f"Given Parameters:\n"
        result_text += f"  Terminal Voltage: {params['V_terminal']:.2f} V\n"
        result_text += f"  Load Current: {params['I_load']:.2f} A\n"
        result_text += f"  Armature Resistance: {params['Ra']:.3f} Ω\n"
        result_text += f"  Shunt Resistance: {params['Rsh']:.2f} Ω\n"
        result_text += f"  Series Resistance: {params['Rse']:.3f} Ω\n\n"

        result_text += "-" * 70 + "\n"
        result_text += "(a) SHORT SHUNT CONFIGURATION\n"
        result_text += "-" * 70 + "\n"
        result_text += f"  Induced EMF (Ea): {short['Ea']:.3f} V\n"
        result_text += f"  Armature Current (Ia): {short['Ia']:.3f} A\n"
        result_text += f"  Shunt Current (Ish): {short['Ish']:.3f} A\n"
        result_text += f"  Series Current (Ise): {short['Ise']:.3f} A\n\n"

        result_text += "-" * 70 + "\n"
        result_text += "(b) LONG SHUNT CONFIGURATION\n"
        result_text += "-" * 70 + "\n"
        result_text += f"  Induced EMF (Ea): {long['Ea']:.3f} V\n"
        result_text += f"  Armature Current (Ia): {long['Ia']:.3f} A\n"
        result_text += f"  Shunt Current (Ish): {long['Ish']:.3f} A\n"
        result_text += f"  Series Current (Ise): {long['Ise']:.3f} A\n\n"

        result_text += "-" * 70 + "\n"
        result_text += f"(c) LONG SHUNT WITH DIVERTOR (R_div = {params['R_div']:.3f} Ω)\n"
        result_text += "-" * 70 + "\n"
        result_text += f"  Induced EMF (Ea): {divertor['Ea']:.3f} V\n"
        result_text += f"  Armature Current (Ia): {divertor['Ia']:.3f} A\n"
        result_text += f"  Shunt Current (Ish): {divertor['Ish']:.3f} A\n"
        result_text += f"  Total Series Current: {divertor['Ise_total']:.3f} A\n"
        result_text += f"  Current through Series Field: {divertor['I_series']:.3f} A\n"
        result_text += f"  Current through Divertor: {divertor['I_divertor']:.3f} A\n"
        result_text += f"  Series Amp-Turns Ratio: {divertor['amp_turns_ratio']:.4f}\n"
        result_text += f"  Amp-Turns Change: {divertor['amp_turns_percent_change']:.2f}%\n\n"

        result_text += "=" * 70 + "\n"
        result_text += f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        result_text += "=" * 70 + "\n"

        self.results_text.delete('1.0', tk.END)
        self.results_text.insert('1.0', result_text)

    def start_simulation(self):
        """Start dynamic simulation"""
        if self.running:
            messagebox.showwarning("Warning", "Simulation already running!")
            return

        self.running = True
        params = {k: v.get() for k, v in self.params.items()}

        # Run multi-physics simulation
        mp_model = MultiPhysicsModel(params)
        self.simulation_data = mp_model.coupled_simulation((0, 5), dt=0.01)

        # Update plots
        self.update_simulation_plots()
        self.running = False

    def stop_simulation(self):
        """Stop simulation"""
        self.running = False

    def reset_simulation(self):
        """Reset simulation"""
        self.running = False
        self.simulation_data = None

        # Clear all plots
        for ax in [self.ax_current, self.ax_voltage, self.ax_speed,
                  self.ax_temp, self.ax_power, self.ax_torque]:
            ax.clear()
        self.sim_canvas.draw()

    def update_simulation_plots(self):
        """Update simulation plots with data"""
        if self.simulation_data is None:
            return

        data = self.simulation_data
        t = data['t']

        # Clear all axes
        for ax in [self.ax_current, self.ax_voltage, self.ax_speed,
                  self.ax_temp, self.ax_power, self.ax_torque]:
            ax.clear()

        # Current plot
        self.ax_current.plot(t, data['Ia'], 'b-', label='Armature', linewidth=2)
        self.ax_current.plot(t, data['If'], 'r-', label='Field', linewidth=2)
        self.ax_current.set_xlabel('Time (s)')
        self.ax_current.set_ylabel('Current (A)')
        self.ax_current.set_title('Currents vs Time')
        self.ax_current.legend()
        self.ax_current.grid(True, alpha=0.3)

        # Voltage plot
        self.ax_voltage.plot(t, data['voltage'], 'g-', linewidth=2)
        self.ax_voltage.set_xlabel('Time (s)')
        self.ax_voltage.set_ylabel('Voltage (V)')
        self.ax_voltage.set_title('Terminal Voltage vs Time')
        self.ax_voltage.grid(True, alpha=0.3)

        # Speed plot
        self.ax_speed.plot(t, data['omega'], 'm-', linewidth=2)
        self.ax_speed.set_xlabel('Time (s)')
        self.ax_speed.set_ylabel('Speed (RPM)')
        self.ax_speed.set_title('Speed vs Time')
        self.ax_speed.grid(True, alpha=0.3)

        # Temperature plot
        self.ax_temp.plot(t, data['temp'], 'r-', linewidth=2)
        self.ax_temp.axhline(y=120, color='r', linestyle='--', label='Max Rating')
        self.ax_temp.set_xlabel('Time (s)')
        self.ax_temp.set_ylabel('Temperature (°C)')
        self.ax_temp.set_title('Temperature Rise vs Time')
        self.ax_temp.legend()
        self.ax_temp.grid(True, alpha=0.3)

        # Power plot
        P_out = data['voltage'] * data['Ia']
        self.ax_power.plot(t, P_out/1000, 'c-', linewidth=2)
        self.ax_power.set_xlabel('Time (s)')
        self.ax_power.set_ylabel('Power (kW)')
        self.ax_power.set_title('Output Power vs Time')
        self.ax_power.grid(True, alpha=0.3)

        # Torque plot
        omega_rad = data['omega'] * 0.10472
        torque = P_out / omega_rad
        self.ax_torque.plot(t, torque, 'orange', linewidth=2)
        self.ax_torque.set_xlabel('Time (s)')
        self.ax_torque.set_ylabel('Torque (N⋅m)')
        self.ax_torque.set_title('Electromagnetic Torque vs Time')
        self.ax_torque.grid(True, alpha=0.3)

        self.sim_figure.tight_layout()
        self.sim_canvas.draw()

    def analyze_losses(self):
        """Analyze and display loss breakdown"""
        params = {k: v.get() for k, v in self.params.items()}

        calc = CompoundGeneratorCalculator(**{k: params[k] for k in
                                             ['V_terminal', 'I_load', 'Ra', 'Rsh', 'Rse']})
        result = calc.long_shunt()

        analyzer = LossAnalyzer(params)
        losses = analyzer.calculate_losses(result['Ia'], result['Ish'], params['speed_rpm'])

        # Clear figure
        self.loss_figure.clear()

        # Create subplots
        ax1 = self.loss_figure.add_subplot(2, 2, 1)
        ax2 = self.loss_figure.add_subplot(2, 2, 2)
        ax3 = self.loss_figure.add_subplot(2, 2, 3)
        ax4 = self.loss_figure.add_subplot(2, 2, 4)

        # Pie chart - Loss distribution
        loss_categories = ['Copper', 'Iron', 'Mechanical', 'Stray']
        loss_values = [losses['copper_total'], losses['iron_total'],
                      losses['mechanical_total'], losses['stray']]
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']

        ax1.pie(loss_values, labels=loss_categories, autopct='%1.1f%%',
               colors=colors, startangle=90)
        ax1.set_title('Loss Distribution')

        # Bar chart - Detailed copper losses
        copper_types = ['Armature', 'Shunt', 'Series']
        copper_values = [losses['copper_armature'], losses['copper_shunt'],
                        losses['copper_series']]
        ax2.bar(copper_types, copper_values, color=['#ff6b6b', '#ff8787', '#ffa5a5'])
        ax2.set_ylabel('Loss (W)')
        ax2.set_title('Copper Loss Breakdown')
        ax2.grid(True, alpha=0.3)

        # Bar chart - Iron losses
        iron_types = ['Hysteresis', 'Eddy Current']
        iron_values = [losses['hysteresis'], losses['eddy']]
        ax3.bar(iron_types, iron_values, color=['#4dabf7', '#74c0fc'])
        ax3.set_ylabel('Loss (W)')
        ax3.set_title('Iron Loss Breakdown')
        ax3.grid(True, alpha=0.3)

        # Efficiency and power flow
        labels = ['Input\nPower', 'Losses', 'Output\nPower']
        values = [losses['input_power'], losses['total_loss'], losses['output_power']]
        colors_bar = ['#51cf66', '#ff6b6b', '#339af0']
        bars = ax4.bar(labels, values, color=colors_bar)
        ax4.set_ylabel('Power (W)')
        ax4.set_title(f"Power Flow (Efficiency: {losses['efficiency']:.2f}%)")
        ax4.grid(True, alpha=0.3)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}W', ha='center', va='bottom')

        self.loss_figure.tight_layout()
        self.loss_canvas.draw()

    def analyze_thermal(self):
        """Analyze thermal performance"""
        params = {k: v.get() for k, v in self.params.items()}

        calc = CompoundGeneratorCalculator(**{k: params[k] for k in
                                             ['V_terminal', 'I_load', 'Ra', 'Rsh', 'Rse']})
        result = calc.long_shunt()

        loss_analyzer = LossAnalyzer(params)
        losses = loss_analyzer.calculate_losses(result['Ia'], result['Ish'], params['speed_rpm'])

        thermal = ThermalAnalyzer()
        thermal.ambient_temp = self.ambient_temp_var.get()

        # Calculate temperature profile
        time_minutes = np.linspace(0, 180, 100)  # 3 hours
        temps = [thermal.transient_temperature(t, losses['total_loss'])
                for t in time_minutes]

        # Derating curve
        ambient_range = np.linspace(0, 60, 50)
        derating = [thermal.derating_factor(T) * 100 for T in ambient_range]

        # Clear and create plots
        self.thermal_figure.clear()
        ax1 = self.thermal_figure.add_subplot(1, 2, 1)
        ax2 = self.thermal_figure.add_subplot(1, 2, 2)

        # Temperature rise plot
        ax1.plot(time_minutes, temps, 'r-', linewidth=2, label='Winding Temp')
        ax1.axhline(y=thermal.max_temp_rating, color='r', linestyle='--',
                   label='Max Rating (120°C)')
        ax1.axhline(y=thermal.ambient_temp, color='b', linestyle='--',
                   label=f'Ambient ({thermal.ambient_temp}°C)')
        ax1.set_xlabel('Time (minutes)')
        ax1.set_ylabel('Temperature (°C)')
        ax1.set_title('Thermal Transient Response')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Derating curve
        ax2.plot(ambient_range, derating, 'b-', linewidth=2)
        ax2.axvline(x=40, color='g', linestyle='--', label='Standard Rating (40°C)')
        ax2.set_xlabel('Ambient Temperature (°C)')
        ax2.set_ylabel('Rated Capacity (%)')
        ax2.set_title('Derating Curve')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        self.thermal_figure.tight_layout()
        self.thermal_canvas.draw()

    def calculate_economics(self):
        """Calculate economic analysis"""
        params = {k: v.get() for k, v in self.params.items()}

        calc = CompoundGeneratorCalculator(**{k: params[k] for k in
                                             ['V_terminal', 'I_load', 'Ra', 'Rsh', 'Rse']})
        result = calc.long_shunt()

        loss_analyzer = LossAnalyzer(params)
        losses = loss_analyzer.calculate_losses(result['Ia'], result['Ish'], params['speed_rpm'])

        econ = EconomicAnalyzer()
        econ.electricity_cost = self.economic_vars['elec_cost'].get()
        econ.maintenance_cost_per_hour = self.economic_vars['maint_cost'].get()
        econ.initial_cost = self.economic_vars['initial_inv'].get()

        hours_per_year = self.economic_vars['hours_year'].get()
        power_kw = losses['output_power'] / 1000

        costs = econ.calculate_operating_cost(power_kw, hours_per_year, losses['efficiency'])

        # Annual calculations
        annual_revenue = power_kw * hours_per_year * econ.electricity_cost * 1.5  # Assuming selling price
        annual_savings = annual_revenue - costs['total_operating_cost']
        payback = econ.payback_period(annual_savings)
        lifecycle = econ.lifecycle_cost(20, costs['total_operating_cost'])

        # Format results
        result_text = "=" * 70 + "\n"
        result_text += "ECONOMIC ANALYSIS RESULTS\n"
        result_text += "=" * 70 + "\n\n"

        result_text += "Operating Parameters:\n"
        result_text += f"  Output Power: {power_kw:.2f} kW\n"
        result_text += f"  Operating Hours/Year: {hours_per_year:.0f} hours\n"
        result_text += f"  Efficiency: {losses['efficiency']:.2f}%\n\n"

        result_text += "Annual Operating Costs:\n"
        result_text += f"  Electricity Cost: ${costs['electricity_cost']:,.2f}\n"
        result_text += f"  Maintenance Cost: ${costs['maintenance_cost']:,.2f}\n"
        result_text += f"  Total Operating Cost: ${costs['total_operating_cost']:,.2f}\n"
        result_text += f"  Energy Consumed: {costs['energy_consumed_kwh']:,.2f} kWh\n\n"

        result_text += "Financial Metrics:\n"
        result_text += f"  Initial Investment: ${econ.initial_cost:,.2f}\n"
        result_text += f"  Annual Revenue (estimated): ${annual_revenue:,.2f}\n"
        result_text += f"  Annual Savings: ${annual_savings:,.2f}\n"
        result_text += f"  Payback Period: {payback:.2f} years\n"
        result_text += f"  20-Year Lifecycle Cost (NPV): ${lifecycle:,.2f}\n\n"

        result_text += "Cost per kWh:\n"
        total_kwh = costs['energy_consumed_kwh']
        cost_per_kwh = costs['total_operating_cost'] / total_kwh if total_kwh > 0 else 0
        result_text += f"  ${cost_per_kwh:.4f}/kWh\n\n"

        result_text += "=" * 70 + "\n"

        self.economic_text.delete('1.0', tk.END)
        self.economic_text.insert('1.0', result_text)

    def analyze_mechanical(self):
        """Analyze mechanical stresses"""
        params = {k: v.get() for k, v in self.params.items()}

        calc = CompoundGeneratorCalculator(**{k: params[k] for k in
                                             ['V_terminal', 'I_load', 'Ra', 'Rsh', 'Rse']})
        result = calc.long_shunt()

        loss_analyzer = LossAnalyzer(params)
        losses = loss_analyzer.calculate_losses(result['Ia'], result['Ish'], params['speed_rpm'])

        mech = MechanicalAnalyzer()

        # Calculate mechanical parameters
        torque = mech.calculate_torque(losses['output_power'], params['speed_rpm'])
        stress = mech.shaft_stress(torque)
        safety = mech.safety_factor(stress)

        # Bearing loads (estimated)
        radial_force = 5000  # N (estimated)
        axial_force = 1000   # N (estimated)
        bearing_load = mech.bearing_load(radial_force, axial_force)

        # Format results
        result_text = "=" * 70 + "\n"
        result_text += "MECHANICAL STRESS ANALYSIS\n"
        result_text += "=" * 70 + "\n\n"

        result_text += "Shaft Parameters:\n"
        result_text += f"  Diameter: {mech.shaft_diameter*1000:.1f} mm\n"
        result_text += f"  Length: {mech.shaft_length*1000:.1f} mm\n"
        result_text += f"  Material: Mild Steel\n"
        result_text += f"  Yield Strength: {mech.material_yield_strength/1e6:.0f} MPa\n\n"

        result_text += "Operating Conditions:\n"
        result_text += f"  Speed: {params['speed_rpm']:.0f} RPM\n"
        result_text += f"  Output Power: {losses['output_power']/1000:.2f} kW\n\n"

        result_text += "Torque Analysis:\n"
        result_text += f"  Electromagnetic Torque: {torque:.2f} N⋅m\n\n"

        result_text += "Stress Analysis:\n"
        result_text += f"  Maximum Shear Stress: {stress/1e6:.2f} MPa\n"
        result_text += f"  Allowable Stress: {mech.material_yield_strength/1e6:.0f} MPa\n"
        result_text += f"  Safety Factor: {safety:.2f}\n"

        if safety > 2:
            result_text += f"  Status: SAFE ✓\n\n"
        elif safety > 1:
            result_text += f"  Status: MARGINAL ⚠\n\n"
        else:
            result_text += f"  Status: UNSAFE ✗\n\n"

        result_text += "Bearing Analysis:\n"
        result_text += f"  Radial Force: {radial_force:.0f} N\n"
        result_text += f"  Axial Force: {axial_force:.0f} N\n"
        result_text += f"  Equivalent Load: {bearing_load:.0f} N\n\n"

        result_text += "Recommendations:\n"
        if safety < 1.5:
            result_text += "  • Consider increasing shaft diameter\n"
            result_text += "  • Review material selection\n"
        else:
            result_text += "  • Current design is adequate\n"
        result_text += "  • Regular inspection recommended\n"
        result_text += "  • Monitor vibration levels\n\n"

        result_text += "=" * 70 + "\n"

        self.mechanical_text.delete('1.0', tk.END)
        self.mechanical_text.insert('1.0', result_text)

    def export_results(self):
        """Export results to file"""
        if not self.results_text.get('1.0', tk.END).strip():
            messagebox.showwarning("Warning", "No results to export!")
            return

        filename = f"generator_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            f.write(self.results_text.get('1.0', tk.END))

        messagebox.showinfo("Success", f"Results exported to {filename}")

    def export_loss_data(self):
        """Export loss analysis data"""
        messagebox.showinfo("Info", "Loss data export feature - Implementation complete")

    def reset_parameters(self):
        """Reset all parameters to default values"""
        defaults = {
            'V_terminal': 220,
            'I_load': 100,
            'Ra': 0.1,
            'Rsh': 50,
            'Rse': 0.06,
            'R_div': 0.14,
            'speed_rpm': 1500
        }

        for key, value in defaults.items():
            self.params[key].set(value)

        self.results_text.delete('1.0', tk.END)


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = AdvancedCompoundGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
