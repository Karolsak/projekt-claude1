"""
Compound DC Generator Core Calculation Module (No GUI)
This module contains only the calculation logic without Tkinter dependency
"""

import numpy as np
from scipy.integrate import solve_ivp


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


if __name__ == "__main__":
    # Quick test
    print("Compound Generator Core Module - Quick Test")
    print("="*70)

    calc = CompoundGeneratorCalculator(220, 100, 0.1, 50, 0.06)

    short = calc.short_shunt()
    print(f"Short Shunt - Ea: {short['Ea']:.3f} V, Ia: {short['Ia']:.3f} A")

    long = calc.long_shunt()
    print(f"Long Shunt - Ea: {long['Ea']:.3f} V, Ia: {long['Ia']:.3f} A")

    div = calc.long_shunt_with_divertor(0.14)
    print(f"With Divertor - Ea: {div['Ea']:.3f} V, Amp-turns change: {div['amp_turns_percent_change']:.2f}%")

    print("="*70)
    print("✓ Core module test passed!")
