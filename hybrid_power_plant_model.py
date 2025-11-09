"""
Zaawansowany Model Hybrydowej Elektrowni Wiatrowo-Fotowoltaicznej
====================================================================

Model symulacyjny dla elektrowni hybrydowej o mocy 300 kW z zaawansowanymi
systemami sterowania MPPT, Fuzzy Logic i PID.

Autor: System Claude
Data: 2025-11-09
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy.integrate import odeint
from scipy.optimize import fsolve
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from dataclasses import dataclass
from typing import Tuple, Dict, List
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


# ========================== STAŁE I PARAMETRY ==========================

@dataclass
class WindTurbineParams:
    """Parametry turbiny wiatrowej"""
    rated_power: float = 200e3  # 200 kW moc znamionowa
    rotor_diameter: float = 27.0  # średnica wirnika [m]
    hub_height: float = 40.0  # wysokość piasty [m]
    cut_in_speed: float = 3.0  # prędkość włączenia [m/s]
    rated_speed: float = 12.0  # prędkość znamionowa [m/s]
    cut_out_speed: float = 25.0  # prędkość wyłączenia [m/s]
    air_density: float = 1.225  # gęstość powietrza [kg/m³]
    cp_max: float = 0.48  # maksymalny współczynnik mocy
    lambda_opt: float = 8.1  # optymalna szybkobieżność
    generator_efficiency: float = 0.95
    gearbox_ratio: float = 1:90
    moment_inertia: float = 150000  # moment bezwładności [kg·m²]

    # Parametry generatora PMSG (Permanent Magnet Synchronous Generator)
    pole_pairs: int = 48
    stator_resistance: float = 0.008  # [Ω]
    d_axis_inductance: float = 0.00035  # [H]
    q_axis_inductance: float = 0.00045  # [H]
    flux_linkage: float = 0.95  # [Wb]

    # Parametry mechaniczne
    bearing_friction: float = 0.015
    windage_loss: float = 0.02
    tower_damping: float = 0.05
    blade_stiffness: float = 2e9  # [N/m²]


@dataclass
class PVSystemParams:
    """Parametry systemu fotowoltaicznego"""
    rated_power: float = 100e3  # 100 kW moc znamionowa
    num_modules: int = 330  # liczba modułów
    module_power: float = 303  # moc modułu [W]
    voc: float = 40.3  # napięcie otwartego obwodu [V]
    isc: float = 9.87  # prąd zwarcia [A]
    vmp: float = 32.9  # napięcie w punkcie MPP [V]
    imp: float = 9.21  # prąd w punkcie MPP [A]
    temp_coeff_power: float = -0.0038  # współczynnik temperaturowy mocy [1/°C]
    temp_coeff_voc: float = -0.0029  # współczynnik temperaturowy Voc [1/°C]
    temp_coeff_isc: float = 0.00053  # współczynnik temperaturowy Isc [1/°C]
    noct: float = 45.0  # temperatura nominalna pracy [°C]
    series_modules: int = 22
    parallel_strings: int = 15

    # Parametry modelu jednodyodowego
    ideality_factor: float = 1.2
    series_resistance: float = 0.28  # [Ω]
    shunt_resistance: float = 450.0  # [Ω]


@dataclass
class EnergyStorageParams:
    """Parametry systemu magazynowania energii"""
    capacity: float = 100e3  # pojemność [Wh]
    max_charge_rate: float = 50e3  # maksymalny prąd ładowania [W]
    max_discharge_rate: float = 50e3  # maksymalny prąd rozładowania [W]
    efficiency: float = 0.95
    soc_min: float = 0.20  # minimalny stan naładowania
    soc_max: float = 0.95  # maksymalny stan naładowania
    internal_resistance: float = 0.05  # [Ω]


# ========================== MODELE ŚRODOWISKOWE ==========================

class EnvironmentalModel:
    """Model warunków środowiskowych"""

    def __init__(self):
        self.base_wind_speed = 7.0  # podstawowa prędkość wiatru [m/s]
        self.base_irradiance = 800.0  # podstawowe promieniowanie [W/m²]
        self.base_temperature = 25.0  # podstawowa temperatura [°C]

    def wind_speed(self, t: float, scenario: str = 'variable') -> float:
        """
        Modelowanie prędkości wiatru z turbulencją i zmianami dobowymi

        Args:
            t: czas [s]
            scenario: scenariusz wiatru ('calm', 'variable', 'gusty', 'storm')
        """
        hour = (t / 3600) % 24

        # Profil dobowy wiatru
        daily_profile = 1.0 + 0.3 * np.sin(2 * np.pi * (hour - 6) / 24)

        if scenario == 'calm':
            base = 4.0
            turbulence = 0.5 * np.sin(0.1 * t) + 0.3 * np.sin(0.05 * t)
        elif scenario == 'variable':
            base = 7.0
            turbulence = 1.5 * np.sin(0.1 * t) + 0.8 * np.sin(0.05 * t) + 0.5 * np.sin(0.2 * t)
        elif scenario == 'gusty':
            base = 10.0
            turbulence = 3.0 * np.sin(0.15 * t) + 2.0 * np.sin(0.08 * t) + 1.0 * np.random.randn()
        elif scenario == 'storm':
            base = 18.0
            turbulence = 5.0 * np.sin(0.2 * t) + 3.0 * np.sin(0.1 * t)
        else:
            base = self.base_wind_speed
            turbulence = 0

        # Dodanie efektu Weibulla dla realizmu
        weibull_factor = np.random.weibull(2.0) * 0.1

        wind = base * daily_profile + turbulence + weibull_factor
        return max(0, wind)

    def solar_irradiance(self, t: float, scenario: str = 'clear') -> float:
        """
        Modelowanie promieniowania słonecznego z efektami chmur i dobowymi zmianami

        Args:
            t: czas [s]
            scenario: scenariusz pogody ('clear', 'partly_cloudy', 'cloudy', 'variable')
        """
        hour = (t / 3600) % 24

        # Model położenia słońca
        if 6 <= hour <= 18:
            sun_elevation = np.sin(np.pi * (hour - 6) / 12)
            clear_sky_irradiance = 1000 * sun_elevation
        else:
            clear_sky_irradiance = 0

        # Efekt chmur
        if scenario == 'clear':
            cloud_factor = 0.95 + 0.05 * np.sin(0.01 * t)
        elif scenario == 'partly_cloudy':
            cloud_factor = 0.7 + 0.2 * np.sin(0.05 * t) + 0.1 * np.sin(0.1 * t)
        elif scenario == 'cloudy':
            cloud_factor = 0.3 + 0.1 * np.sin(0.02 * t)
        elif scenario == 'variable':
            cloud_factor = 0.6 + 0.3 * np.sin(0.08 * t) + 0.1 * np.random.randn()
        else:
            cloud_factor = 1.0

        irradiance = clear_sky_irradiance * max(0, min(1, cloud_factor))
        return max(0, irradiance)

    def ambient_temperature(self, t: float) -> float:
        """
        Modelowanie temperatury otoczenia

        Args:
            t: czas [s]
        """
        hour = (t / 3600) % 24

        # Profil dobowy temperatury
        daily_avg = self.base_temperature
        daily_variation = 8.0 * np.sin(2 * np.pi * (hour - 9) / 24)

        # Małe fluktuacje
        noise = 0.5 * np.random.randn()

        return daily_avg + daily_variation + noise


# ========================== MODEL TURBINY WIATROWEJ ==========================

class WindTurbineModel:
    """Zaawansowany model turbiny wiatrowej z PMSG"""

    def __init__(self, params: WindTurbineParams):
        self.params = params
        self.rotor_area = np.pi * (params.rotor_diameter / 2) ** 2
        self.omega = 0.0  # prędkość kątowa rotora [rad/s]
        self.theta = 0.0  # kąt obrotu [rad]
        self.pitch_angle = 0.0  # kąt ustawienia łopat [deg]
        self.temperature = 25.0  # temperatura generatora [°C]

    def power_coefficient(self, lambda_tsr: float, beta: float) -> float:
        """
        Współczynnik mocy Cp używając aproksymacji krzywej

        Args:
            lambda_tsr: szybkobieżność (Tip Speed Ratio)
            beta: kąt ustawienia łopat [deg]
        """
        # Funkcja aproksymująca Cp oparta na danych empirycznych
        c1, c2, c3, c4, c5, c6 = 0.5176, 116, 0.4, 5, 21, 0.0068

        lambda_i = 1 / (1/(lambda_tsr + 0.08*beta) - 0.035/(beta**3 + 1))

        cp = c1 * (c2/lambda_i - c3*beta - c4) * np.exp(-c5/lambda_i) + c6*lambda_tsr

        return max(0, min(self.params.cp_max, cp))

    def aerodynamic_power(self, wind_speed: float, omega: float, pitch: float) -> float:
        """
        Obliczenie mocy aerodynamicznej

        Args:
            wind_speed: prędkość wiatru [m/s]
            omega: prędkość kątowa rotora [rad/s]
            pitch: kąt ustawienia łopat [deg]
        """
        if wind_speed < self.params.cut_in_speed or wind_speed > self.params.cut_out_speed:
            return 0.0

        # Prędkość obwodowa końcówek łopat
        tip_speed = omega * self.params.rotor_diameter / 2

        # Szybkobieżność
        if wind_speed > 0.1:
            lambda_tsr = tip_speed / wind_speed
        else:
            lambda_tsr = 0

        # Współczynnik mocy
        cp = self.power_coefficient(lambda_tsr, pitch)

        # Moc aerodynamiczna
        p_aero = 0.5 * self.params.air_density * self.rotor_area * wind_speed**3 * cp

        return min(p_aero, self.params.rated_power)

    def generator_electrical_power(self, omega: float, torque: float) -> Tuple[float, Dict]:
        """
        Model generatora PMSG (Permanent Magnet Synchronous Generator)

        Args:
            omega: prędkość kątowa [rad/s]
            torque: moment obrotowy [Nm]

        Returns:
            Moc elektryczna i parametry generatora
        """
        # Prędkość mechaniczna do elektrycznej
        omega_e = omega * self.params.pole_pairs

        # Napięcie indukowane (EMF)
        e_mag = omega_e * self.params.flux_linkage

        # Prąd generatora (uproszczony model)
        if omega > 0:
            current = torque / (self.params.flux_linkage * self.params.pole_pairs)
        else:
            current = 0

        # Straty w uzwojeniach
        copper_loss = 3 * current**2 * self.params.stator_resistance / 2

        # Straty w żelazie (proporcjonalne do kwadratu częstotliwości)
        iron_loss = 0.001 * omega_e**2

        # Moc mechaniczna
        p_mech = torque * omega

        # Moc elektryczna
        p_elec = p_mech - copper_loss - iron_loss
        p_elec *= self.params.generator_efficiency

        params = {
            'emf': e_mag,
            'current': current,
            'copper_loss': copper_loss,
            'iron_loss': iron_loss,
            'efficiency': p_elec / p_mech if p_mech > 0 else 0
        }

        return max(0, p_elec), params

    def mechanical_dynamics(self, state: np.ndarray, t: float,
                           wind_speed: float, pitch_angle: float,
                           gen_torque: float) -> np.ndarray:
        """
        Równania dynamiki mechanicznej turbiny

        Args:
            state: [theta, omega] - kąt i prędkość kątowa
            t: czas
            wind_speed: prędkość wiatru
            pitch_angle: kąt ustawienia łopat
            gen_torque: moment od generatora
        """
        theta, omega = state

        # Moment aerodynamiczny
        p_aero = self.aerodynamic_power(wind_speed, omega, pitch_angle)
        if omega > 0.1:
            t_aero = p_aero / omega
        else:
            t_aero = 0

        # Moment tarcia
        t_friction = self.params.bearing_friction * omega + \
                     self.params.windage_loss * omega**2

        # Równanie ruchu
        d_omega = (t_aero - gen_torque - t_friction) / self.params.moment_inertia
        d_theta = omega

        return np.array([d_theta, d_omega])

    def thermal_model(self, p_loss: float, dt: float) -> float:
        """
        Model termiczny generatora

        Args:
            p_loss: straty mocy [W]
            dt: krok czasowy [s]
        """
        # Pojemność cieplna generatora
        thermal_capacity = 50000  # [J/K]

        # Współczynnik przenikania ciepła
        heat_transfer_coeff = 200  # [W/K]

        # Temperatura otoczenia
        t_ambient = 25.0

        # Zmiana temperatury
        dt_temp = (p_loss - heat_transfer_coeff * (self.temperature - t_ambient)) / \
                  thermal_capacity * dt

        self.temperature += dt_temp

        return self.temperature


# ========================== MODEL SYSTEMU FOTOWOLTAICZNEGO ==========================

class PVSystemModel:
    """Zaawansowany model systemu fotowoltaicznego"""

    def __init__(self, params: PVSystemParams):
        self.params = params
        self.temperature = 25.0  # temperatura modułu [°C]

    def cell_temperature(self, irradiance: float, ambient_temp: float,
                        wind_speed: float = 1.0) -> float:
        """
        Obliczenie temperatury ogniwa

        Args:
            irradiance: natężenie promieniowania [W/m²]
            ambient_temp: temperatura otoczenia [°C]
            wind_speed: prędkość wiatru [m/s]
        """
        # Model temperatury z uwzględnieniem chłodzenia wiatrem
        noct_factor = (self.params.noct - 20) / 800
        wind_factor = 1.0 / (1.0 + 0.05 * wind_speed)

        cell_temp = ambient_temp + irradiance * noct_factor * wind_factor

        self.temperature = cell_temp
        return cell_temp

    def single_diode_model(self, irradiance: float, temperature: float,
                          voltage: float) -> float:
        """
        Model jednodyodowy ogniwa fotowoltaicznego

        Args:
            irradiance: natężenie promieniowania [W/m²]
            temperature: temperatura ogniwa [°C]
            voltage: napięcie [V]

        Returns:
            Prąd [A]
        """
        # Stałe fizyczne
        k = 1.381e-23  # stała Boltzmanna [J/K]
        q = 1.602e-19  # ładunek elektronu [C]

        # Temperatura w Kelvinach
        T = temperature + 273.15
        T_ref = 25 + 273.15

        # Napięcie termiczne
        V_t = k * T / q * self.params.ideality_factor

        # Prąd fotoelektryczny (zależny od promieniowania i temperatury)
        I_ph = (irradiance / 1000) * (self.params.isc +
                self.params.temp_coeff_isc * (temperature - 25))

        # Prąd nasycenia diody
        I_0 = self.params.isc / (np.exp(self.params.voc / (self.params.ideality_factor * V_t)) - 1)
        I_0 = I_0 * (T / T_ref)**3 * np.exp(q * 1.12 / (self.params.ideality_factor * k) *
                                             (1/T_ref - 1/T))

        # Równanie charakterystyki (rozwiązywane iteracyjnie)
        def current_equation(I):
            return I_ph - I_0 * (np.exp((voltage + I * self.params.series_resistance) / V_t) - 1) - \
                   (voltage + I * self.params.series_resistance) / self.params.shunt_resistance - I

        try:
            current = fsolve(current_equation, I_ph)[0]
            return max(0, current)
        except:
            return 0

    def array_power(self, irradiance: float, temperature: float, voltage: float) -> Tuple[float, float]:
        """
        Obliczenie mocy całego układu PV

        Args:
            irradiance: natężenie promieniowania [W/m²]
            temperature: temperatura ogniwa [°C]
            voltage: napięcie pracy [V]

        Returns:
            (moc, prąd)
        """
        # Prąd pojedynczego modułu
        i_module = self.single_diode_model(irradiance, temperature,
                                          voltage / self.params.series_modules)

        # Prąd i moc układu
        i_array = i_module * self.params.parallel_strings
        p_array = voltage * i_array

        return p_array, i_array

    def mpp_parameters(self, irradiance: float, temperature: float) -> Dict:
        """
        Obliczenie parametrów punktu maksymalnej mocy (MPP)

        Args:
            irradiance: natężenie promieniowania [W/m²]
            temperature: temperatura [°C]

        Returns:
            Słownik z parametrami MPP
        """
        # Skanowanie krzywej I-V dla znalezienia MPP
        voltages = np.linspace(0, self.params.voc * self.params.series_modules, 200)
        powers = []

        for v in voltages:
            p, _ = self.array_power(irradiance, temperature, v)
            powers.append(p)

        powers = np.array(powers)
        mpp_idx = np.argmax(powers)

        return {
            'voltage': voltages[mpp_idx],
            'power': powers[mpp_idx],
            'current': powers[mpp_idx] / voltages[mpp_idx] if voltages[mpp_idx] > 0 else 0
        }


# ========================== REGULATORY MPPT ==========================

class MPPTController:
    """Regulatory MPPT dla optymalizacji mocy"""

    def __init__(self, type: str = 'perturb_observe'):
        self.type = type
        self.v_ref = 0.0
        self.power_prev = 0.0
        self.voltage_prev = 0.0
        self.perturbation = 0.5

        # Parametry P&O
        self.step_size = 1.0
        self.min_step = 0.1
        self.max_step = 5.0

    def perturb_and_observe(self, voltage: float, power: float) -> float:
        """
        Algorytm Perturb & Observe dla MPPT

        Args:
            voltage: aktualne napięcie
            power: aktualna moc

        Returns:
            Nowe napięcie referencyjne
        """
        if self.power_prev == 0:
            self.power_prev = power
            self.voltage_prev = voltage
            return voltage

        dP = power - self.power_prev
        dV = voltage - self.voltage_prev

        # Adaptacyjny krok
        if abs(dP) > 100:
            step = self.max_step
        elif abs(dP) < 10:
            step = self.min_step
        else:
            step = self.step_size

        if dP > 0:
            if dV > 0:
                v_ref = voltage + step
            else:
                v_ref = voltage - step
        else:
            if dV > 0:
                v_ref = voltage - step
            else:
                v_ref = voltage + step

        self.power_prev = power
        self.voltage_prev = voltage
        self.v_ref = v_ref

        return v_ref

    def incremental_conductance(self, voltage: float, current: float,
                                power: float) -> float:
        """
        Algorytm Incremental Conductance dla MPPT

        Args:
            voltage: aktualne napięcie
            current: aktualny prąd
            power: aktualna moc

        Returns:
            Nowe napięcie referencyjne
        """
        if self.voltage_prev == 0:
            self.voltage_prev = voltage
            return voltage

        dI = current - (self.power_prev / self.voltage_prev if self.voltage_prev > 0 else 0)
        dV = voltage - self.voltage_prev

        if abs(dV) < 0.01:
            v_ref = voltage
        else:
            conductance = current / voltage if voltage > 0 else 0
            incremental_conductance = dI / dV if dV != 0 else 0

            if abs(incremental_conductance + conductance) < 0.01:
                v_ref = voltage  # W MPP
            elif incremental_conductance + conductance > 0:
                v_ref = voltage + self.step_size
            else:
                v_ref = voltage - self.step_size

        self.voltage_prev = voltage
        self.power_prev = power
        self.v_ref = v_ref

        return v_ref


class WindMPPTController:
    """MPPT dla turbiny wiatrowej - optymalizacja TSR (Tip Speed Ratio)"""

    def __init__(self, optimal_tsr: float = 8.1):
        self.optimal_tsr = optimal_tsr
        self.omega_ref = 0.0

    def optimal_speed_control(self, wind_speed: float, rotor_diameter: float) -> float:
        """
        Obliczenie optymalnej prędkości kątowej dla maksymalnej mocy

        Args:
            wind_speed: prędkość wiatru [m/s]
            rotor_diameter: średnica wirnika [m]

        Returns:
            Optymalna prędkość kątowa [rad/s]
        """
        if wind_speed < 0.1:
            return 0.0

        # omega_opt = lambda_opt * v_wind / R
        radius = rotor_diameter / 2
        omega_opt = self.optimal_tsr * wind_speed / radius

        self.omega_ref = omega_opt
        return omega_opt


# ========================== REGULATORY PID ==========================

class PIDController:
    """Regulator PID z anti-windup"""

    def __init__(self, kp: float, ki: float, kd: float,
                 output_limits: Tuple[float, float] = (-np.inf, np.inf)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits

        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = 0.0

    def compute(self, setpoint: float, measurement: float, current_time: float) -> float:
        """
        Obliczenie sygnału sterującego PID

        Args:
            setpoint: wartość zadana
            measurement: wartość zmierzona
            current_time: aktualny czas

        Returns:
            Sygnał sterujący
        """
        error = setpoint - measurement

        # Dt
        if self.prev_time == 0:
            dt = 0.01
        else:
            dt = current_time - self.prev_time

        if dt <= 0:
            dt = 0.01

        # Człon proporcjonalny
        p_term = self.kp * error

        # Człon całkujący z anti-windup
        self.integral += error * dt
        i_term = self.ki * self.integral

        # Człon różniczkujący
        if dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0
        d_term = self.kd * derivative

        # Sygnał wyjściowy
        output = p_term + i_term + d_term

        # Ograniczenia i anti-windup
        if output > self.output_limits[1]:
            output = self.output_limits[1]
            self.integral -= error * dt  # Anti-windup
        elif output < self.output_limits[0]:
            output = self.output_limits[0]
            self.integral -= error * dt  # Anti-windup

        self.prev_error = error
        self.prev_time = current_time

        return output

    def reset(self):
        """Reset regulatora"""
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = 0.0


# ========================== REGULATOR FUZZY LOGIC ==========================

class FuzzyPowerController:
    """Regulator rozmyty dla zarządzania mocą"""

    def __init__(self):
        # Definicja zmiennych lingwistycznych

        # Błąd mocy (różnica między zapotrzebowaniem a produkcją)
        power_error = ctrl.Antecedent(np.arange(-200, 201, 1), 'power_error')
        power_error['neg_large'] = fuzz.trapmf(power_error.universe, [-200, -200, -150, -80])
        power_error['neg_medium'] = fuzz.trimf(power_error.universe, [-150, -80, -20])
        power_error['neg_small'] = fuzz.trimf(power_error.universe, [-50, -20, 0])
        power_error['zero'] = fuzz.trimf(power_error.universe, [-10, 0, 10])
        power_error['pos_small'] = fuzz.trimf(power_error.universe, [0, 20, 50])
        power_error['pos_medium'] = fuzz.trimf(power_error.universe, [20, 80, 150])
        power_error['pos_large'] = fuzz.trapmf(power_error.universe, [80, 150, 200, 200])

        # Zmiana błędu mocy
        power_change = ctrl.Antecedent(np.arange(-50, 51, 1), 'power_change')
        power_change['decreasing'] = fuzz.trapmf(power_change.universe, [-50, -50, -20, -5])
        power_change['stable'] = fuzz.trimf(power_change.universe, [-10, 0, 10])
        power_change['increasing'] = fuzz.trapmf(power_change.universe, [5, 20, 50, 50])

        # Sygnał sterujący
        control_signal = ctrl.Consequent(np.arange(-100, 101, 1), 'control_signal')
        control_signal['decrease_large'] = fuzz.trapmf(control_signal.universe, [-100, -100, -70, -40])
        control_signal['decrease_medium'] = fuzz.trimf(control_signal.universe, [-70, -40, -15])
        control_signal['decrease_small'] = fuzz.trimf(control_signal.universe, [-30, -15, 0])
        control_signal['maintain'] = fuzz.trimf(control_signal.universe, [-10, 0, 10])
        control_signal['increase_small'] = fuzz.trimf(control_signal.universe, [0, 15, 30])
        control_signal['increase_medium'] = fuzz.trimf(control_signal.universe, [15, 40, 70])
        control_signal['increase_large'] = fuzz.trapmf(control_signal.universe, [40, 70, 100, 100])

        # Reguły rozmyte
        rules = [
            ctrl.Rule(power_error['neg_large'] & power_change['decreasing'],
                     control_signal['decrease_large']),
            ctrl.Rule(power_error['neg_large'] & power_change['stable'],
                     control_signal['decrease_medium']),
            ctrl.Rule(power_error['neg_medium'] & power_change['decreasing'],
                     control_signal['decrease_medium']),
            ctrl.Rule(power_error['neg_medium'] & power_change['stable'],
                     control_signal['decrease_small']),
            ctrl.Rule(power_error['neg_small'] | power_error['zero'],
                     control_signal['maintain']),
            ctrl.Rule(power_error['pos_small'] & power_change['stable'],
                     control_signal['increase_small']),
            ctrl.Rule(power_error['pos_medium'] & power_change['increasing'],
                     control_signal['increase_medium']),
            ctrl.Rule(power_error['pos_medium'] & power_change['stable'],
                     control_signal['increase_small']),
            ctrl.Rule(power_error['pos_large'] & power_change['increasing'],
                     control_signal['increase_large']),
            ctrl.Rule(power_error['pos_large'] & power_change['stable'],
                     control_signal['increase_medium']),
        ]

        # System sterowania
        self.control_system = ctrl.ControlSystem(rules)
        self.controller = ctrl.ControlSystemSimulation(self.control_system)

        self.prev_error = 0.0

    def compute(self, power_demand: float, power_production: float) -> float:
        """
        Obliczenie sygnału sterującego

        Args:
            power_demand: zapotrzebowanie na moc [kW]
            power_production: aktualna produkcja [kW]

        Returns:
            Sygnał sterujący [-100, 100]
        """
        error = power_demand - power_production
        error_change = error - self.prev_error

        # Ograniczenie zakresów wejściowych
        error = np.clip(error, -200, 200)
        error_change = np.clip(error_change, -50, 50)

        try:
            self.controller.input['power_error'] = error
            self.controller.input['power_change'] = error_change
            self.controller.compute()

            output = self.controller.output['control_signal']
        except:
            output = 0.0

        self.prev_error = error

        return output


# ========================== SYSTEMY ZABEZPIECZEŃ ==========================

class ProtectionSystem:
    """System zabezpieczeń przed przeciążeniem i zwarciem"""

    def __init__(self):
        self.overcurrent_limit = 500  # [A]
        self.overvoltage_limit = 800  # [V]
        self.undervoltage_limit = 200  # [V]
        self.overtemperature_limit = 85  # [°C]
        self.fault_flags = {
            'overcurrent': False,
            'overvoltage': False,
            'undervoltage': False,
            'overtemperature': False,
            'short_circuit': False,
            'ground_fault': False
        }
        self.trip_time = 0.0

    def check_overcurrent(self, current: float, dt: float = 0.01) -> bool:
        """
        Sprawdzenie przeciążenia prądowego z charakterystyką czasowo-prądową

        Args:
            current: prąd [A]
            dt: krok czasowy [s]
        """
        # Charakterystyka czasowo-prądowa (im większy prąd, tym szybszy zanik)
        if current > self.overcurrent_limit:
            trip_threshold = 0.1 / (current / self.overcurrent_limit)  # odwrotnie proporcjonalny czas
            self.trip_time += dt

            if self.trip_time > trip_threshold:
                self.fault_flags['overcurrent'] = True
                return True
        else:
            self.trip_time = max(0, self.trip_time - dt)

        return False

    def check_short_circuit(self, current: float, voltage: float) -> bool:
        """
        Detekcja zwarcia - bardzo wysoki prąd przy niskim napięciu

        Args:
            current: prąd [A]
            voltage: napięcie [V]
        """
        if current > 2 * self.overcurrent_limit and voltage < 0.5 * self.undervoltage_limit:
            self.fault_flags['short_circuit'] = True
            return True
        return False

    def check_voltage(self, voltage: float) -> bool:
        """
        Sprawdzenie napięcia

        Args:
            voltage: napięcie [V]
        """
        if voltage > self.overvoltage_limit:
            self.fault_flags['overvoltage'] = True
            return True
        elif voltage < self.undervoltage_limit and voltage > 10:  # ignoruj 0V podczas startu
            self.fault_flags['undervoltage'] = True
            return True
        return False

    def check_temperature(self, temperature: float) -> bool:
        """
        Sprawdzenie temperatury

        Args:
            temperature: temperatura [°C]
        """
        if temperature > self.overtemperature_limit:
            self.fault_flags['overtemperature'] = True
            return True
        return False

    def check_all(self, current: float, voltage: float, temperature: float, dt: float = 0.01) -> Dict:
        """
        Sprawdzenie wszystkich zabezpieczeń

        Returns:
            Słownik z flagami błędów
        """
        self.check_overcurrent(current, dt)
        self.check_short_circuit(current, voltage)
        self.check_voltage(voltage)
        self.check_temperature(temperature)

        return self.fault_flags

    def is_fault(self) -> bool:
        """Sprawdzenie czy wystąpił jakikolwiek błąd"""
        return any(self.fault_flags.values())

    def reset(self):
        """Reset zabezpieczeń"""
        self.fault_flags = {key: False for key in self.fault_flags}
        self.trip_time = 0.0


# ========================== MODEL OBCIĄŻENIA ==========================

class LoadProfile:
    """Model profilu obciążenia dobowego"""

    def __init__(self, base_load: float = 150e3):
        self.base_load = base_load  # [W]

    def get_load(self, t: float, scenario: str = 'residential') -> float:
        """
        Obliczenie obciążenia w danym czasie

        Args:
            t: czas [s]
            scenario: typ profilu ('residential', 'commercial', 'industrial', 'mixed')

        Returns:
            Obciążenie [W]
        """
        hour = (t / 3600) % 24

        if scenario == 'residential':
            # Profil mieszkalny - szczyty rano i wieczorem
            if 0 <= hour < 6:
                factor = 0.3 + 0.1 * np.sin(np.pi * hour / 6)
            elif 6 <= hour < 9:
                factor = 0.4 + 0.4 * (hour - 6) / 3
            elif 9 <= hour < 17:
                factor = 0.5 + 0.1 * np.sin(2 * np.pi * (hour - 9) / 8)
            elif 17 <= hour < 22:
                factor = 0.6 + 0.3 * np.sin(np.pi * (hour - 17) / 5)
            else:
                factor = 0.6 - 0.3 * (hour - 22) / 2

        elif scenario == 'commercial':
            # Profil komercyjny - szczyt w godzinach pracy
            if 8 <= hour < 18:
                factor = 0.8 + 0.2 * np.sin(np.pi * (hour - 8) / 10)
            else:
                factor = 0.2

        elif scenario == 'industrial':
            # Profil przemysłowy - stabilne obciążenie w ciągu dnia
            if 6 <= hour < 22:
                factor = 0.9 + 0.1 * np.random.randn() * 0.1
            else:
                factor = 0.4 + 0.1 * np.random.randn() * 0.1

        elif scenario == 'mixed':
            # Profil mieszany
            factor = 0.5 + 0.3 * np.sin(2 * np.pi * (hour - 8) / 24) + \
                     0.1 * np.sin(4 * np.pi * hour / 24)
        else:
            factor = 0.5

        # Dodanie losowego szumu
        noise = 0.05 * np.random.randn()

        load = self.base_load * max(0.1, min(1.0, factor + noise))

        return load


# ========================== GŁÓWNY MODEL HYBRYDOWEJ ELEKTROWNI ==========================

class HybridPowerPlant:
    """Główny model hybrydowej elektrowni wiatrowo-fotowoltaicznej"""

    def __init__(self):
        # Inicjalizacja komponentów
        self.wind_params = WindTurbineParams()
        self.pv_params = PVSystemParams()
        self.storage_params = EnergyStorageParams()

        self.wind_turbine = WindTurbineModel(self.wind_params)
        self.pv_system = PVSystemModel(self.pv_params)
        self.environment = EnvironmentalModel()

        # Regulatory
        self.pv_mppt = MPPTController(type='perturb_observe')
        self.wind_mppt = WindMPPTController(optimal_tsr=self.wind_params.lambda_opt)

        self.wind_speed_controller = PIDController(kp=500, ki=50, kd=10,
                                                   output_limits=(0, 200000))
        self.voltage_controller = PIDController(kp=0.5, ki=0.1, kd=0.05,
                                               output_limits=(200, 800))
        self.fuzzy_controller = FuzzyPowerController()

        # Zabezpieczenia
        self.wind_protection = ProtectionSystem()
        self.pv_protection = ProtectionSystem()

        # Profil obciążenia
        self.load_profile = LoadProfile(base_load=200e3)

        # Stan systemu
        self.soc = 0.5  # Stan naładowania magazynu energii
        self.dc_bus_voltage = 600.0  # Napięcie szyny DC [V]

        # Historia danych
        self.history = {
            'time': [],
            'wind_power': [],
            'pv_power': [],
            'total_power': [],
            'load_power': [],
            'battery_power': [],
            'soc': [],
            'wind_speed': [],
            'irradiance': [],
            'temperature': [],
            'dc_voltage': [],
            'wind_temp': [],
            'efficiency': [],
            'curtailed_power': []
        }

    def simulate_step(self, t: float, dt: float = 1.0,
                     wind_scenario: str = 'variable',
                     solar_scenario: str = 'clear',
                     load_scenario: str = 'mixed') -> Dict:
        """
        Symulacja pojedynczego kroku czasowego

        Args:
            t: czas [s]
            dt: krok czasowy [s]
            wind_scenario: scenariusz wiatru
            solar_scenario: scenariusz słońca
            load_scenario: scenariusz obciążenia

        Returns:
            Słownik z wynikami kroku symulacji
        """
        # ===== WARUNKI ŚRODOWISKOWE =====
        wind_speed = self.environment.wind_speed(t, wind_scenario)
        irradiance = self.environment.solar_irradiance(t, solar_scenario)
        ambient_temp = self.environment.ambient_temperature(t)

        # ===== TURBINA WIATROWA =====

        # MPPT - optymalna prędkość obrotowa
        omega_ref = self.wind_mppt.optimal_speed_control(wind_speed,
                                                         self.wind_params.rotor_diameter)

        # Regulator PID prędkości
        gen_torque = self.wind_speed_controller.compute(omega_ref,
                                                        self.wind_turbine.omega, t)

        # Obliczenie mocy aerodynamicznej
        p_aero = self.wind_turbine.aerodynamic_power(wind_speed,
                                                     self.wind_turbine.omega,
                                                     self.wind_turbine.pitch_angle)

        # Moc elektryczna generatora
        if self.wind_turbine.omega > 0:
            torque_mech = p_aero / self.wind_turbine.omega
        else:
            torque_mech = 0

        p_wind, gen_params = self.wind_turbine.generator_electrical_power(
            self.wind_turbine.omega, torque_mech)

        # Model termiczny
        p_loss_wind = gen_params['copper_loss'] + gen_params['iron_loss']
        wind_temp = self.wind_turbine.thermal_model(p_loss_wind, dt)

        # Sprawdzenie zabezpieczeń
        wind_current = gen_params['current']
        wind_faults = self.wind_protection.check_all(wind_current, self.dc_bus_voltage,
                                                     wind_temp, dt)

        if self.wind_protection.is_fault():
            p_wind = 0  # Wyłączenie turbiny w przypadku awarii

        # Aktualizacja dynamiki (uproszczona integracja Eulera)
        self.wind_turbine.omega += (torque_mech - gen_torque -
                                    self.wind_params.bearing_friction * self.wind_turbine.omega) / \
                                   self.wind_params.moment_inertia * dt
        self.wind_turbine.omega = max(0, self.wind_turbine.omega)

        # ===== SYSTEM FOTOWOLTAICZNY =====

        # Temperatura ogniwa
        cell_temp = self.pv_system.cell_temperature(irradiance, ambient_temp, wind_speed)

        # Parametry MPP
        mpp_params = self.pv_system.mpp_parameters(irradiance, cell_temp)

        # MPPT - regulator napięcia
        v_ref = self.pv_mppt.perturb_and_observe(mpp_params['voltage'], mpp_params['power'])

        # Moc PV
        p_pv, i_pv = self.pv_system.array_power(irradiance, cell_temp, v_ref)

        # Sprawdzenie zabezpieczeń
        pv_faults = self.pv_protection.check_all(i_pv, v_ref, cell_temp, dt)

        if self.pv_protection.is_fault():
            p_pv = 0  # Wyłączenie PV w przypadku awarii

        # ===== OBCIĄŻENIE =====
        p_load = self.load_profile.get_load(t, load_scenario)

        # ===== BILANS MOCY I MAGAZYN ENERGII =====

        # Całkowita produkcja
        p_total = p_wind + p_pv

        # Różnica mocy
        p_diff = p_total - p_load

        # Sterowanie rozmyte dla optymalizacji przepływu mocy
        fuzzy_signal = self.fuzzy_controller.compute(p_load / 1000, p_total / 1000)

        # Zarządzanie magazynem energii
        p_battery = 0
        p_curtailed = 0

        if p_diff > 0:  # Nadwyżka energii
            # Ładowanie baterii
            if self.soc < self.storage_params.soc_max:
                p_charge = min(p_diff, self.storage_params.max_charge_rate,
                             (self.storage_params.soc_max - self.soc) *
                             self.storage_params.capacity / dt)
                p_battery = -p_charge  # Ujemne = ładowanie
                self.soc += (p_charge * dt * self.storage_params.efficiency) / \
                           self.storage_params.capacity
            else:
                # Bateria pełna - curtailment (ograniczenie produkcji)
                p_curtailed = p_diff

        else:  # Niedobór energii
            # Rozładowanie baterii
            if self.soc > self.storage_params.soc_min:
                p_discharge = min(abs(p_diff), self.storage_params.max_discharge_rate,
                                (self.soc - self.storage_params.soc_min) *
                                self.storage_params.capacity / dt)
                p_battery = p_discharge  # Dodatnie = rozładowanie
                self.soc -= (p_discharge * dt) / \
                           (self.storage_params.capacity * self.storage_params.efficiency)

        # Ograniczenie SOC
        self.soc = np.clip(self.soc, self.storage_params.soc_min, self.storage_params.soc_max)

        # ===== NAPIĘCIE SZYNY DC =====

        # Regulator napięcia szyny DC
        v_dc_ref = 600.0  # [V]
        power_balance = p_total - p_load + p_battery

        # Prosta dynamika napięcia szyny DC
        c_dc = 0.01  # Pojemność szyny DC [F]
        self.dc_bus_voltage += (power_balance / self.dc_bus_voltage) / c_dc * dt
        self.dc_bus_voltage = np.clip(self.dc_bus_voltage, 400, 750)

        # ===== EFEKTYWNOŚĆ CAŁKOWITA =====
        if p_total > 0:
            efficiency = (p_load - abs(p_battery) * (1 - self.storage_params.efficiency)) / p_total
        else:
            efficiency = 0

        # ===== ZAPIS HISTORII =====
        self.history['time'].append(t)
        self.history['wind_power'].append(p_wind / 1000)  # kW
        self.history['pv_power'].append(p_pv / 1000)
        self.history['total_power'].append(p_total / 1000)
        self.history['load_power'].append(p_load / 1000)
        self.history['battery_power'].append(p_battery / 1000)
        self.history['soc'].append(self.soc * 100)
        self.history['wind_speed'].append(wind_speed)
        self.history['irradiance'].append(irradiance)
        self.history['temperature'].append(ambient_temp)
        self.history['dc_voltage'].append(self.dc_bus_voltage)
        self.history['wind_temp'].append(wind_temp)
        self.history['efficiency'].append(efficiency * 100)
        self.history['curtailed_power'].append(p_curtailed / 1000)

        # ===== WYNIKI KROKU =====
        results = {
            'time': t,
            'wind_power': p_wind,
            'pv_power': p_pv,
            'total_power': p_total,
            'load_power': p_load,
            'battery_power': p_battery,
            'soc': self.soc,
            'wind_speed': wind_speed,
            'irradiance': irradiance,
            'ambient_temp': ambient_temp,
            'cell_temp': cell_temp,
            'wind_temp': wind_temp,
            'dc_voltage': self.dc_bus_voltage,
            'efficiency': efficiency,
            'curtailed_power': p_curtailed,
            'wind_faults': wind_faults,
            'pv_faults': pv_faults
        }

        return results

    def run_simulation(self, duration: float = 86400, dt: float = 10,
                      wind_scenario: str = 'variable',
                      solar_scenario: str = 'clear',
                      load_scenario: str = 'mixed',
                      verbose: bool = True) -> pd.DataFrame:
        """
        Uruchomienie pełnej symulacji

        Args:
            duration: czas trwania symulacji [s]
            dt: krok czasowy [s]
            wind_scenario: scenariusz wiatru
            solar_scenario: scenariusz słońca
            load_scenario: scenariusz obciążenia
            verbose: wyświetlanie postępu

        Returns:
            DataFrame z wynikami
        """
        # Reset historii
        self.history = {key: [] for key in self.history}

        # Reset regulatorów
        self.wind_speed_controller.reset()
        self.voltage_controller.reset()
        self.pv_mppt.power_prev = 0
        self.soc = 0.5

        # Symulacja
        num_steps = int(duration / dt)

        if verbose:
            print(f"Rozpoczęcie symulacji...")
            print(f"Czas trwania: {duration/3600:.1f} godz")
            print(f"Krok czasowy: {dt} s")
            print(f"Liczba kroków: {num_steps}")
            print(f"Scenariusze: Wiatr={wind_scenario}, Słońce={solar_scenario}, Obciążenie={load_scenario}")
            print("-" * 60)

        for i in range(num_steps):
            t = i * dt

            self.simulate_step(t, dt, wind_scenario, solar_scenario, load_scenario)

            if verbose and i % (num_steps // 20) == 0:
                progress = (i / num_steps) * 100
                print(f"Postęp: {progress:.0f}% | t={t/3600:.1f}h | "
                      f"P_wind={self.history['wind_power'][-1]:.1f}kW | "
                      f"P_pv={self.history['pv_power'][-1]:.1f}kW | "
                      f"SOC={self.history['soc'][-1]:.0f}%")

        if verbose:
            print("-" * 60)
            print("Symulacja zakończona!")

        # Konwersja do DataFrame
        df = pd.DataFrame(self.history)
        df['time_hours'] = df['time'] / 3600

        return df

    def energy_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Szczegółowa analiza gospodarki energetycznej

        Args:
            df: DataFrame z wynikami symulacji

        Returns:
            Słownik z analizą energetyczną
        """
        dt = df['time'].diff().mean()

        # Energia wytworzona
        e_wind = (df['wind_power'].sum() * dt) / 3600  # kWh
        e_pv = (df['pv_power'].sum() * dt) / 3600
        e_total = e_wind + e_pv

        # Energia zużyta
        e_load = (df['load_power'].sum() * dt) / 3600

        # Energia z/do baterii
        e_battery_charge = (df[df['battery_power'] < 0]['battery_power'].abs().sum() * dt) / 3600
        e_battery_discharge = (df[df['battery_power'] > 0]['battery_power'].sum() * dt) / 3600

        # Energia zredukowana (curtailment)
        e_curtailed = (df['curtailed_power'].sum() * dt) / 3600

        # Współczynniki
        capacity_factor_wind = (e_wind / (self.wind_params.rated_power / 1000 *
                                          df['time_hours'].max())) * 100
        capacity_factor_pv = (e_pv / (self.pv_params.rated_power / 1000 *
                                      df['time_hours'].max())) * 100

        # Niezawodność zasilania
        power_shortage = df[df['total_power'] + df['battery_power'] * 1000 < df['load_power']]
        reliability = (1 - len(power_shortage) / len(df)) * 100

        # Udział źródeł
        wind_share = (e_wind / e_total * 100) if e_total > 0 else 0
        pv_share = (e_pv / e_total * 100) if e_total > 0 else 0

        # Sprawność baterii
        battery_efficiency = (e_battery_discharge / e_battery_charge * 100) if e_battery_charge > 0 else 0

        # Średnie wartości
        avg_wind_power = df['wind_power'].mean()
        avg_pv_power = df['pv_power'].mean()
        avg_load_power = df['load_power'].mean()

        max_wind_power = df['wind_power'].max()
        max_pv_power = df['pv_power'].max()
        max_load_power = df['load_power'].max()

        analysis = {
            'energy_production': {
                'wind_kwh': e_wind,
                'pv_kwh': e_pv,
                'total_kwh': e_total
            },
            'energy_consumption': {
                'load_kwh': e_load,
                'curtailed_kwh': e_curtailed
            },
            'battery': {
                'charged_kwh': e_battery_charge,
                'discharged_kwh': e_battery_discharge,
                'efficiency_percent': battery_efficiency,
                'cycles': e_battery_charge / (self.storage_params.capacity / 1000)
            },
            'capacity_factors': {
                'wind_percent': capacity_factor_wind,
                'pv_percent': capacity_factor_pv
            },
            'energy_mix': {
                'wind_share_percent': wind_share,
                'pv_share_percent': pv_share
            },
            'reliability': {
                'supply_reliability_percent': reliability,
                'shortage_hours': len(power_shortage) * dt / 3600
            },
            'power_statistics': {
                'avg_wind_kw': avg_wind_power,
                'avg_pv_kw': avg_pv_power,
                'avg_load_kw': avg_load_power,
                'max_wind_kw': max_wind_power,
                'max_pv_kw': max_pv_power,
                'max_load_kw': max_load_power
            }
        }

        return analysis

    def visualize_results(self, df: pd.DataFrame, analysis: Dict = None,
                         save_path: str = None):
        """
        Zaawansowana wizualizacja wyników symulacji

        Args:
            df: DataFrame z wynikami
            analysis: Analiza energetyczna
            save_path: Ścieżka do zapisu wykresu
        """
        fig = plt.figure(figsize=(20, 14))
        gs = GridSpec(5, 3, figure=fig, hspace=0.3, wspace=0.3)

        # 1. Moc w czasie
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(df['time_hours'], df['wind_power'], label='Turbina wiatrowa', linewidth=1.5)
        ax1.plot(df['time_hours'], df['pv_power'], label='System PV', linewidth=1.5)
        ax1.plot(df['time_hours'], df['total_power'], label='Produkcja całkowita',
                linewidth=2, linestyle='--')
        ax1.plot(df['time_hours'], df['load_power'], label='Obciążenie',
                linewidth=2, color='red', alpha=0.7)
        ax1.fill_between(df['time_hours'], 0, df['curtailed_power'],
                        label='Energia zredukowana', alpha=0.3, color='orange')
        ax1.set_xlabel('Czas [h]')
        ax1.set_ylabel('Moc [kW]')
        ax1.set_title('Produkcja i zużycie mocy w czasie', fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # 2. Moc baterii i SOC
        ax2 = fig.add_subplot(gs[1, :])
        ax2_twin = ax2.twinx()
        ax2.bar(df['time_hours'], df['battery_power'], label='Moc baterii',
               width=df['time_hours'].diff().mean(), alpha=0.6, color='green')
        ax2_twin.plot(df['time_hours'], df['soc'], label='SOC',
                     linewidth=2, color='blue')
        ax2.set_xlabel('Czas [h]')
        ax2.set_ylabel('Moc baterii [kW]', color='green')
        ax2_twin.set_ylabel('Stan naładowania [%]', color='blue')
        ax2.set_title('Zarządzanie magazynem energii', fontsize=14, fontweight='bold')
        ax2.tick_params(axis='y', labelcolor='green')
        ax2_twin.tick_params(axis='y', labelcolor='blue')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper left')
        ax2_twin.legend(loc='upper right')

        # 3. Warunki środowiskowe
        ax3 = fig.add_subplot(gs[2, 0])
        ax3.plot(df['time_hours'], df['wind_speed'], linewidth=1.5, color='steelblue')
        ax3.axhline(y=self.wind_params.cut_in_speed, color='green',
                   linestyle='--', label='Prędkość włączenia', alpha=0.7)
        ax3.axhline(y=self.wind_params.rated_speed, color='orange',
                   linestyle='--', label='Prędkość znamionowa', alpha=0.7)
        ax3.axhline(y=self.wind_params.cut_out_speed, color='red',
                   linestyle='--', label='Prędkość wyłączenia', alpha=0.7)
        ax3.set_xlabel('Czas [h]')
        ax3.set_ylabel('Prędkość wiatru [m/s]')
        ax3.set_title('Profile wiatru', fontsize=12, fontweight='bold')
        ax3.legend(fontsize=8)
        ax3.grid(True, alpha=0.3)

        ax4 = fig.add_subplot(gs[2, 1])
        ax4.plot(df['time_hours'], df['irradiance'], linewidth=1.5, color='gold')
        ax4.fill_between(df['time_hours'], 0, df['irradiance'], alpha=0.3, color='yellow')
        ax4.set_xlabel('Czas [h]')
        ax4.set_ylabel('Promieniowanie [W/m²]')
        ax4.set_title('Promieniowanie słoneczne', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)

        ax5 = fig.add_subplot(gs[2, 2])
        ax5.plot(df['time_hours'], df['temperature'], linewidth=1.5, color='red')
        ax5.set_xlabel('Czas [h]')
        ax5.set_ylabel('Temperatura [°C]')
        ax5.set_title('Temperatura otoczenia', fontsize=12, fontweight='bold')
        ax5.grid(True, alpha=0.3)

        # 4. Analiza termiczna
        ax6 = fig.add_subplot(gs[3, 0])
        ax6.plot(df['time_hours'], df['wind_temp'], linewidth=1.5, color='darkred')
        ax6.axhline(y=self.wind_protection.overtemperature_limit, color='red',
                   linestyle='--', label='Limit temperatury', alpha=0.7)
        ax6.set_xlabel('Czas [h]')
        ax6.set_ylabel('Temperatura [°C]')
        ax6.set_title('Temperatura generatora wiatrowego', fontsize=12, fontweight='bold')
        ax6.legend()
        ax6.grid(True, alpha=0.3)

        # 5. Napięcie szyny DC
        ax7 = fig.add_subplot(gs[3, 1])
        ax7.plot(df['time_hours'], df['dc_voltage'], linewidth=1.5, color='purple')
        ax7.axhline(y=600, color='green', linestyle='--', label='Napięcie nominalne', alpha=0.7)
        ax7.set_xlabel('Czas [h]')
        ax7.set_ylabel('Napięcie [V]')
        ax7.set_title('Napięcie szyny DC', fontsize=12, fontweight='bold')
        ax7.legend()
        ax7.grid(True, alpha=0.3)

        # 6. Sprawność systemu
        ax8 = fig.add_subplot(gs[3, 2])
        ax8.plot(df['time_hours'], df['efficiency'], linewidth=1.5, color='green')
        ax8.set_xlabel('Czas [h]')
        ax8.set_ylabel('Sprawność [%]')
        ax8.set_title('Sprawność systemu', fontsize=12, fontweight='bold')
        ax8.grid(True, alpha=0.3)

        # 7. Analiza energetyczna - wykres kołowy
        if analysis:
            ax9 = fig.add_subplot(gs[4, 0])
            labels = ['Turbina wiatrowa', 'System PV']
            sizes = [analysis['energy_production']['wind_kwh'],
                    analysis['energy_production']['pv_kwh']]
            colors = ['steelblue', 'gold']
            ax9.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors,
                   startangle=90)
            ax9.set_title('Udział źródeł w produkcji energii', fontsize=12, fontweight='bold')

            # 8. Bilans energetyczny
            ax10 = fig.add_subplot(gs[4, 1])
            categories = ['Produkcja\nwiatr', 'Produkcja\nPV', 'Zużycie',
                         'Bat. ład.', 'Bat. rozł.', 'Redukcja']
            values = [
                analysis['energy_production']['wind_kwh'],
                analysis['energy_production']['pv_kwh'],
                analysis['energy_consumption']['load_kwh'],
                analysis['battery']['charged_kwh'],
                analysis['battery']['discharged_kwh'],
                analysis['energy_consumption']['curtailed_kwh']
            ]
            colors_bar = ['steelblue', 'gold', 'red', 'lightgreen', 'darkgreen', 'orange']
            ax10.bar(categories, values, color=colors_bar, alpha=0.7)
            ax10.set_ylabel('Energia [kWh]')
            ax10.set_title('Bilans energetyczny', fontsize=12, fontweight='bold')
            ax10.tick_params(axis='x', rotation=45)
            ax10.grid(True, alpha=0.3, axis='y')

            # 9. Wskaźniki wydajności
            ax11 = fig.add_subplot(gs[4, 2])
            ax11.axis('off')

            metrics_text = f"""
            KLUCZOWE WSKAŹNIKI WYDAJNOŚCI
            {'='*40}

            PRODUKCJA ENERGII:
            • Całkowita: {analysis['energy_production']['total_kwh']:.1f} kWh
            • Wiatr: {analysis['energy_production']['wind_kwh']:.1f} kWh
            • PV: {analysis['energy_production']['pv_kwh']:.1f} kWh

            WSPÓŁCZYNNIKI WYKORZYSTANIA:
            • CF Wiatr: {analysis['capacity_factors']['wind_percent']:.1f}%
            • CF PV: {analysis['capacity_factors']['pv_percent']:.1f}%

            MAGAZYN ENERGII:
            • Cykle: {analysis['battery']['cycles']:.2f}
            • Sprawność: {analysis['battery']['efficiency_percent']:.1f}%

            NIEZAWODNOŚĆ:
            • Zasilanie: {analysis['reliability']['supply_reliability_percent']:.2f}%
            • Niedobory: {analysis['reliability']['shortage_hours']:.2f} h

            MIECHANIZM REDUKCJI:
            • Zredukowano: {analysis['energy_consumption']['curtailed_kwh']:.1f} kWh
            """

            ax11.text(0.1, 0.95, metrics_text, transform=ax11.transAxes,
                     fontsize=9, verticalalignment='top', fontfamily='monospace',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.suptitle('ZAAWANSOWANA ANALIZA HYBRYDOWEJ ELEKTROWNI WIATROWO-FOTOWOLTAICZNEJ',
                    fontsize=16, fontweight='bold', y=0.995)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\nWykres zapisany: {save_path}")

        plt.tight_layout()
        return fig

    def print_analysis(self, analysis: Dict):
        """
        Wydruk szczegółowej analizy w formie tekstowej

        Args:
            analysis: Słownik z analizą energetyczną
        """
        print("\n" + "="*80)
        print(" " * 15 + "SZCZEGÓŁOWA ANALIZA GOSPODARKI ENERGETYCZNEJ")
        print("="*80)

        print("\n📊 PRODUKCJA ENERGII:")
        print("-" * 80)
        print(f"  Turbina wiatrowa:          {analysis['energy_production']['wind_kwh']:>10.2f} kWh")
        print(f"  System fotowoltaiczny:     {analysis['energy_production']['pv_kwh']:>10.2f} kWh")
        print(f"  Produkcja całkowita:       {analysis['energy_production']['total_kwh']:>10.2f} kWh")

        print("\n⚡ ZUŻYCIE ENERGII:")
        print("-" * 80)
        print(f"  Obciążenie:                {analysis['energy_consumption']['load_kwh']:>10.2f} kWh")
        print(f"  Energia zredukowana:       {analysis['energy_consumption']['curtailed_kwh']:>10.2f} kWh")

        print("\n🔋 MAGAZYN ENERGII:")
        print("-" * 80)
        print(f"  Energia ładowania:         {analysis['battery']['charged_kwh']:>10.2f} kWh")
        print(f"  Energia rozładowania:      {analysis['battery']['discharged_kwh']:>10.2f} kWh")
        print(f"  Sprawność baterii:         {analysis['battery']['efficiency_percent']:>10.1f} %")
        print(f"  Liczba cykli:              {analysis['battery']['cycles']:>10.2f}")

        print("\n📈 WSPÓŁCZYNNIKI WYKORZYSTANIA (Capacity Factor):")
        print("-" * 80)
        print(f"  Turbina wiatrowa:          {analysis['capacity_factors']['wind_percent']:>10.1f} %")
        print(f"  System fotowoltaiczny:     {analysis['capacity_factors']['pv_percent']:>10.1f} %")

        print("\n🎯 MIX ENERGETYCZNY:")
        print("-" * 80)
        print(f"  Udział energii wiatrowej:  {analysis['energy_mix']['wind_share_percent']:>10.1f} %")
        print(f"  Udział energii słonecznej: {analysis['energy_mix']['pv_share_percent']:>10.1f} %")

        print("\n✅ NIEZAWODNOŚĆ ZASILANIA:")
        print("-" * 80)
        print(f"  Niezawodność dostaw:       {analysis['reliability']['supply_reliability_percent']:>10.2f} %")
        print(f"  Czas niedoborów:           {analysis['reliability']['shortage_hours']:>10.2f} h")

        print("\n📊 STATYSTYKI MOCY:")
        print("-" * 80)
        print(f"  Średnia moc wiatrowa:      {analysis['power_statistics']['avg_wind_kw']:>10.1f} kW")
        print(f"  Średnia moc PV:            {analysis['power_statistics']['avg_pv_kw']:>10.1f} kW")
        print(f"  Średnie obciążenie:        {analysis['power_statistics']['avg_load_kw']:>10.1f} kW")
        print(f"  Maks. moc wiatrowa:        {analysis['power_statistics']['max_wind_kw']:>10.1f} kW")
        print(f"  Maks. moc PV:              {analysis['power_statistics']['max_pv_kw']:>10.1f} kW")
        print(f"  Maks. obciążenie:          {analysis['power_statistics']['max_load_kw']:>10.1f} kW")

        print("\n" + "="*80)


# ========================== FUNKCJE POMOCNICZE ==========================

def compare_scenarios(scenarios: List[Dict], duration: float = 86400):
    """
    Porównanie różnych scenariuszy pracy elektrowni

    Args:
        scenarios: Lista słowników z parametrami scenariuszy
        duration: Czas trwania symulacji [s]
    """
    results = []

    for i, scenario in enumerate(scenarios):
        print(f"\n{'='*80}")
        print(f"SCENARIUSZ {i+1}: {scenario.get('name', f'Scenariusz {i+1}')}")
        print(f"{'='*80}")

        plant = HybridPowerPlant()
        df = plant.run_simulation(
            duration=duration,
            dt=scenario.get('dt', 10),
            wind_scenario=scenario.get('wind', 'variable'),
            solar_scenario=scenario.get('solar', 'clear'),
            load_scenario=scenario.get('load', 'mixed'),
            verbose=True
        )

        analysis = plant.energy_analysis(df)
        plant.print_analysis(analysis)

        results.append({
            'name': scenario.get('name', f'Scenariusz {i+1}'),
            'dataframe': df,
            'analysis': analysis,
            'plant': plant
        })

    return results


# ========================== GŁÓWNA FUNKCJA ==========================

def main():
    """Główna funkcja demonstracyjna"""

    print("="*80)
    print(" " * 10 + "ZAAWANSOWANY MODEL HYBRYDOWEJ ELEKTROWNI")
    print(" " * 8 + "Wiatrowo-Fotowoltaicznej o mocy 300 kW")
    print("="*80)

    # Inicjalizacja modelu
    plant = HybridPowerPlant()

    # Symulacja - 24 godziny (1 dzień)
    print("\n🔄 Uruchamianie symulacji dobowej...")
    df = plant.run_simulation(
        duration=86400,  # 24h
        dt=10,  # krok 10s
        wind_scenario='variable',
        solar_scenario='clear',
        load_scenario='mixed',
        verbose=True
    )

    # Analiza energetyczna
    print("\n📊 Przeprowadzanie analizy energetycznej...")
    analysis = plant.energy_analysis(df)
    plant.print_analysis(analysis)

    # Wizualizacja
    print("\n📈 Generowanie wizualizacji...")
    plant.visualize_results(df, analysis, save_path='hybrid_plant_analysis.png')

    print("\n✅ Analiza zakończona pomyślnie!")

    # Zapis wyników do CSV
    df.to_csv('simulation_results.csv', index=False)
    print("\n💾 Wyniki zapisane do: simulation_results.csv")

    plt.show()

    return plant, df, analysis


if __name__ == "__main__":
    # Uruchomienie głównej symulacji
    plant, df, analysis = main()

    # Przykład porównania scenariuszy
    print("\n\n" + "="*80)
    print("PORÓWNANIE RÓŻNYCH SCENARIUSZY POGODOWYCH")
    print("="*80)

    scenarios = [
        {
            'name': 'Dzień spokojny (niska produkcja)',
            'wind': 'calm',
            'solar': 'cloudy',
            'load': 'residential',
            'dt': 10
        },
        {
            'name': 'Dzień optymalny (wysoka produkcja)',
            'wind': 'variable',
            'solar': 'clear',
            'load': 'mixed',
            'dt': 10
        },
        {
            'name': 'Dzień wichury (ekstremalne warunki)',
            'wind': 'gusty',
            'solar': 'partly_cloudy',
            'load': 'industrial',
            'dt': 10
        }
    ]

    # scenario_results = compare_scenarios(scenarios, duration=86400)

    print("\n\n🎉 Wszystkie symulacje zakończone!")
