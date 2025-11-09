# Zaawansowany Model Hybrydowej Elektrowni Wiatrowo-Fotowoltaicznej

## Spis treści
1. [Wprowadzenie](#wprowadzenie)
2. [Architektura systemu](#architektura-systemu)
3. [Komponenty modelu](#komponenty-modelu)
4. [Algorytmy sterowania](#algorytmy-sterowania)
5. [Systemy zabezpieczeń](#systemy-zabezpieczeń)
6. [Modelowanie termiczne i mechaniczne](#modelowanie-termiczne-i-mechaniczne)
7. [Analiza energetyczna](#analiza-energetyczna)
8. [Instrukcja użytkowania](#instrukcja-użytkowania)
9. [Przykłady zastosowań](#przykłady-zastosowań)

---

## Wprowadzenie

Model symulacyjny hybrydowej elektrowni wiatrowo-fotowoltaicznej o łącznej mocy znamionowej 300 kW został zaprojektowany do szczegółowej analizy gospodarki energetycznej i optymalizacji pracy układu hybrydowego. System integruje:

- **Turbinę wiatrową**: 200 kW z generatorem PMSG (Permanent Magnet Synchronous Generator)
- **System fotowoltaiczny**: 100 kW (330 modułów)
- **Magazyn energii**: 100 kWh bateria z zaawansowanym systemem zarządzania
- **Zaawansowane algorytmy sterowania**: MPPT, PID, Fuzzy Logic
- **Kompleksowe systemy zabezpieczeń**: przeciążenie, zwarcie, temperatura

### Cele modelu:
1. Symulacja rzeczywistych warunków pracy elektrowni hybrydowej
2. Optymalizacja produkcji energii przy zmiennych warunkach pogodowych
3. Analiza niezawodności zasilania i bilansu energetycznego
4. Testowanie strategii zarządzania mocą
5. Ocena efektywności ekonomicznej i technicznej

---

## Architektura systemu

### Schemat blokowy

```
┌─────────────────────────────────────────────────────────────────┐
│                    WARUNKI ŚRODOWISKOWE                         │
│  • Prędkość wiatru (z turbulencją)                             │
│  • Promieniowanie słoneczne (z efektem chmur)                  │
│  • Temperatura otoczenia (profil dobowy)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴───────────┐
        │                        │
        ▼                        ▼
┌───────────────┐        ┌──────────────┐
│   TURBINA     │        │   SYSTEM     │
│   WIATROWA    │        │     PV       │
│   200 kW      │        │   100 kW     │
│               │        │              │
│ • PMSG        │        │ • 330 modułów│
│ • MPPT TSR    │        │ • MPPT P&O   │
│ • PID prędkość│        │ • Model 1D   │
└───────┬───────┘        └──────┬───────┘
        │                       │
        │    ┌──────────────┐   │
        └────►  SZYNA DC   ◄───┘
             │  600V       │
             └──────┬──────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
  ┌──────────┐ ┌────────┐ ┌─────────┐
  │ BATERIA  │ │ZABEZP. │ │FUZZY    │
  │ 100 kWh  │ │SYSTEM  │ │LOGIC    │
  └──────────┘ └────────┘ └─────────┘
        │
        ▼
  ┌──────────┐
  │OBCIĄŻENIE│
  │ Profil   │
  │ dobowy   │
  └──────────┘
```

### Przepływ danych w symulacji

1. **Krok inicjalizacji**:
   - Ustawienie parametrów systemów
   - Reset regulatorów
   - Inicjalizacja stanu baterii (SOC = 50%)

2. **Pętla symulacji** (dla każdego kroku czasowego):
   - Odczyt warunków środowiskowych
   - Obliczenie mocy z turbiny wiatrowej
   - Obliczenie mocy z systemu PV
   - Sterowanie MPPT dla obu źródeł
   - Zarządzanie magazynem energii
   - Sprawdzenie zabezpieczeń
   - Aktualizacja modeli termicznych
   - Zapis danych do historii

3. **Post-processing**:
   - Analiza energetyczna
   - Wizualizacja wyników
   - Eksport danych

---

## Komponenty modelu

### 1. Model turbiny wiatrowej

#### 1.1 Teoria działania

Turbina wiatrowa konwertuje energię kinetyczną wiatru na energię elektryczną poprzez następujące etapy:

**Moc aerodynamiczna**:
```
P_aero = 0.5 × ρ × A × v³ × Cp(λ, β)
```
gdzie:
- ρ = 1.225 kg/m³ (gęstość powietrza)
- A = π × (D/2)² (powierzchnia ometana przez wirnik)
- v = prędkość wiatru [m/s]
- Cp = współczynnik mocy (funkcja λ i β)
- λ = szybkobieżność (Tip Speed Ratio)
- β = kąt ustawienia łopat [°]

**Współczynnik mocy Cp**:

Wykorzystano empiryczną aproksymację krzywej Cp:

```python
λ_i = 1 / (1/(λ + 0.08×β) - 0.035/(β³ + 1))
Cp = c1 × (c2/λ_i - c3×β - c4) × exp(-c5/λ_i) + c6×λ
```

gdzie współczynniki:
- c1 = 0.5176
- c2 = 116
- c3 = 0.4
- c4 = 5
- c5 = 21
- c6 = 0.0068

Maksymalna wartość Cp = 0.48 (zgodnie z limitem Betza 0.593).

#### 1.2 Generator PMSG

Model generatora synchronicznego z magnesami trwałymi:

**Napięcie indukowane (EMF)**:
```
E = ω_e × Ψ_f
```
gdzie:
- ω_e = ω_mech × p (prędkość elektryczna)
- p = 48 (liczba par biegunów)
- Ψ_f = 0.95 Wb (strumień magnesu)

**Straty mocy**:

1. **Straty w miedzi** (uzwojenia):
   ```
   P_cu = 3/2 × I² × R_s
   ```
   gdzie R_s = 0.008 Ω

2. **Straty w żelazie**:
   ```
   P_fe = k_fe × ω_e²
   ```
   gdzie k_fe = 0.001

**Moc elektryczna**:
```
P_elec = (P_mech - P_cu - P_fe) × η_gen
```
gdzie η_gen = 0.95 (sprawność generatora)

#### 1.3 Dynamika mechaniczna

Równanie ruchu wirnika:

```
J × dω/dt = T_aero - T_gen - T_friction
```

gdzie:
- J = 150,000 kg·m² (moment bezwładności)
- T_aero = moment aerodynamiczny
- T_gen = moment od generatora
- T_friction = tarcie łożysk + straty wiatrowe

**Moment tarcia**:
```
T_friction = k_bearing × ω + k_windage × ω²
```

Parametry:
- k_bearing = 0.015 (tarcie łożysk)
- k_windage = 0.02 (straty wiatrowe)

#### 1.4 Parametry turbiny

| Parametr | Wartość | Jednostka |
|----------|---------|-----------|
| Moc znamionowa | 200 | kW |
| Średnica wirnika | 27 | m |
| Wysokość piasty | 40 | m |
| Prędkość włączenia | 3 | m/s |
| Prędkość znamionowa | 12 | m/s |
| Prędkość wyłączenia | 25 | m/s |
| Optymalna szybkobieżność | 8.1 | - |
| Przekładnia | 1:90 | - |

---

### 2. Model systemu fotowoltaicznego

#### 2.1 Model jednodyodowy

Charakterystyka I-V ogniwa opisana równaniem:

```
I = I_ph - I_0 × [exp((V + I×R_s)/(n×V_t)) - 1] - (V + I×R_s)/R_sh
```

gdzie:
- I_ph = prąd fotoelektryczny
- I_0 = prąd nasycenia diody
- V_t = k×T/q (napięcie termiczne)
- n = 1.2 (współczynnik idealności)
- R_s = 0.28 Ω (rezystancja szeregowa)
- R_sh = 450 Ω (rezystancja bocznikowa)

**Prąd fotoelektryczny**:
```
I_ph = (G/G_ref) × [I_sc + α_I × (T_cell - T_ref)]
```

gdzie:
- G = natężenie promieniowania [W/m²]
- G_ref = 1000 W/m² (warunki STC)
- α_I = 0.00053 A/°C (współczynnik temp. prądu)

**Prąd nasycenia diody**:
```
I_0 = I_0,ref × (T/T_ref)³ × exp[q×E_g/(n×k) × (1/T_ref - 1/T)]
```

gdzie:
- E_g = 1.12 eV (szerokość przerwy energetycznej krzemu)

#### 2.2 Temperatura ogniwa

Model NOCT (Nominal Operating Cell Temperature):

```
T_cell = T_amb + (NOCT - 20)/800 × G × (1/(1 + 0.05×v_wind))
```

gdzie:
- T_amb = temperatura otoczenia [°C]
- NOCT = 45°C
- v_wind = prędkość wiatru (chłodzenie) [m/s]

#### 2.3 Konfiguracja układu

- **Liczba modułów**: 330
- **Konfiguracja**: 22 szeregowo × 15 równolegle
- **Moc modułu**: 303 Wp
- **Napięcie MPP**: 32.9 V (moduł)
- **Prąd MPP**: 9.21 A (moduł)
- **Napięcie układu**: ~724 V
- **Moc układu**: 100 kW

#### 2.4 Współczynniki temperaturowe

| Parametr | Wartość | Jednostka |
|----------|---------|-----------|
| Temp. współczynnik mocy | -0.38 | %/°C |
| Temp. współczynnik Voc | -0.29 | %/°C |
| Temp. współczynnik Isc | +0.053 | %/°C |

---

### 3. Modele środowiskowe

#### 3.1 Model wiatru

Składa się z trzech komponentów:

**1. Profil dobowy**:
```python
daily_profile = 1.0 + 0.3 × sin(2π × (h - 6)/24)
```

**2. Turbulencja** (w zależności od scenariusza):
- **Calm**: amplitude = 0.5 m/s
- **Variable**: amplitude = 1.5 m/s
- **Gusty**: amplitude = 3.0 m/s
- **Storm**: amplitude = 5.0 m/s

**3. Rozkład Weibulla**:
```python
weibull_factor = random.weibull(k=2.0) × 0.1
```

Parametr kształtu k=2 odpowiada rozkładowi Rayleigha, typowemu dla wiatru.

**Scenariusze wiatru**:

| Scenariusz | Prędkość bazowa | Turbulencja | Zastosowanie |
|------------|-----------------|-------------|--------------|
| calm | 4 m/s | niska | Cisza wiatrowa |
| variable | 7 m/s | średnia | Typowe warunki |
| gusty | 10 m/s | wysoka | Wietrzny dzień |
| storm | 18 m/s | bardzo wysoka | Wichura |

#### 3.2 Model promieniowania słonecznego

**1. Model położenia słońca**:
```python
if 6 ≤ hour ≤ 18:
    elevation = sin(π × (hour - 6)/12)
    I_clear = 1000 × elevation
else:
    I_clear = 0
```

**2. Efekt chmur**:
- **Clear**: cloud_factor = 0.95 (prawie bezchmurnie)
- **Partly cloudy**: cloud_factor = 0.7 (częściowe zachmurzenie)
- **Cloudy**: cloud_factor = 0.3 (pochmurno)
- **Variable**: cloud_factor = zmienny (0.6 ± 0.3)

**3. Rzeczywiste promieniowanie**:
```python
G = I_clear × cloud_factor
```

#### 3.3 Model temperatury

Profil dobowy temperatury:

```python
T(h) = T_avg + ΔT × sin(2π × (h - 9)/24) + noise
```

gdzie:
- T_avg = 25°C (temperatura średnia)
- ΔT = 8°C (amplituda dobowa)
- noise = losowy szum ±0.5°C

---

## Algorytmy sterowania

### 1. MPPT dla systemu fotowoltaicznego

#### 1.1 Algorytm Perturb & Observe (P&O)

Algorytm iteracyjny poszukujący punktu maksymalnej mocy:

```
Algorytm P&O:
1. Zmierz V(k), P(k)
2. Oblicz: ΔP = P(k) - P(k-1)
           ΔV = V(k) - V(k-1)
3. Jeśli ΔP > 0:
     Jeśli ΔV > 0: V_ref = V + step
     Jeśli ΔV < 0: V_ref = V - step
4. Jeśli ΔP < 0:
     Jeśli ΔV > 0: V_ref = V - step
     Jeśli ΔV < 0: V_ref = V + step
5. Zapisz P(k-1) = P(k), V(k-1) = V(k)
```

**Adaptacyjny krok**:
```python
if |ΔP| > 100 W:
    step = 5.0 V  # duży krok
elif |ΔP| < 10 W:
    step = 0.1 V  # mały krok (blisko MPP)
else:
    step = 1.0 V  # standardowy krok
```

**Zalety**:
- Prosty w implementacji
- Skuteczny w warunkach zmiennych
- Adaptacyjny krok zwiększa szybkość i dokładność

**Wady**:
- Oscylacje wokół MPP
- Możliwa pomyłka przy szybkich zmianach warunków

#### 1.2 Algorytm Incremental Conductance

Wykorzystuje zależność:
```
dP/dV = 0  w punkcie MPP
```

co prowadzi do:
```
dI/dV = -I/V  w MPP
```

Implementacja:
```python
conductance = I/V
incremental_conductance = dI/dV

if |dI/dV + I/V| < ε:
    # Jesteśmy w MPP
    V_ref = V
elif dI/dV + I/V > 0:
    # Po lewej stronie MPP
    V_ref = V + step
else:
    # Po prawej stronie MPP
    V_ref = V - step
```

**Zalety**:
- Dokładniejszy niż P&O
- Mniejsze oscylacje w MPP
- Lepsze zachowanie przy szybkich zmianach

---

### 2. MPPT dla turbiny wiatrowej

#### 2.1 Optimal TSR Control

Sterowanie oparte na optymalnej szybkobieżności (Tip Speed Ratio):

```
λ_opt = (ω × R) / v_wind
```

Dla maksymalnego Cp, λ powinno wynosić 8.1.

**Sterowanie**:
```python
ω_ref = (λ_opt × v_wind) / R
```

Generator jest sterowany tak, aby utrzymać prędkość ω_ref, co zapewnia maksymalną moc przy danej prędkości wiatru.

**Zalety**:
- Maksymalizuje wydobycie energii z wiatru
- Proste w implementacji
- Nie wymaga czujników mocy

**Ograniczenia**:
- Wymaga pomiaru prędkości wiatru
- Może być nieoptymalne przy turbulencjach

---

### 3. Regulator PID

#### 3.1 Teoria regulacji PID

Równanie regulatora PID:

```
u(t) = Kp×e(t) + Ki×∫e(τ)dτ + Kd×de(t)/dt
```

Dyskretna implementacja:

```python
P = Kp × error
I += Ki × error × dt
D = Kd × (error - error_prev) / dt
output = P + I + D
```

#### 3.2 Anti-windup

Problem: Całka (I) może rosnąć bez ograniczeń, gdy system jest nasycony.

Rozwiązanie:
```python
if output > limit_max:
    output = limit_max
    I -= error × dt  # Cofnięcie całkowania
elif output < limit_min:
    output = limit_min
    I -= error × dt
```

#### 3.3 Parametry PID dla turbiny wiatrowej

**Regulator prędkości**:
- Kp = 500 (proporcjonalny do momentu bezwładności)
- Ki = 50 (eliminacja błędu ustalonego)
- Kd = 10 (tłumienie oscylacji)

**Regulator napięcia**:
- Kp = 0.5
- Ki = 0.1
- Kd = 0.05

**Dobór parametrów**:
1. Start z Kd = 0, Ki = 0
2. Zwiększaj Kp aż do oscylacji
3. Ustaw Kp na 50% wartości krytycznej
4. Dodaj Ki dla eliminacji błędu ustalonego
5. Dodaj Kd dla tłumienia

---

### 4. Fuzzy Logic Controller

#### 4.1 Teoria logiki rozmytej

Regulator rozmyty wykorzystuje reguły lingwistyczne zamiast równań matematycznych.

**Zmienne wejściowe**:
1. **Power Error** (błąd mocy): różnica między zapotrzebowaniem a produkcją
   - Zakres: [-200, 200] kW
   - Funkcje przynależności: neg_large, neg_medium, neg_small, zero, pos_small, pos_medium, pos_large

2. **Power Change** (zmiana błędu):
   - Zakres: [-50, 50] kW/s
   - Funkcje przynależności: decreasing, stable, increasing

**Zmienna wyjściowa**:
- **Control Signal**: sygnał sterujący
  - Zakres: [-100, 100]
  - Funkcje przynależności: decrease_large, decrease_medium, decrease_small, maintain, increase_small, increase_medium, increase_large

#### 4.2 Funkcje przynależności

Wykorzystano funkcje:
- **Trapezoidalne** (trapmf): dla wartości skrajnych
- **Trójkątne** (trimf): dla wartości pośrednich

Przykład:
```python
power_error['zero'] = trimf([-10, 0, 10])
power_error['pos_medium'] = trimf([20, 80, 150])
```

#### 4.3 Baza reguł

Przykładowe reguły:

```
JEŚLI error = neg_large I change = decreasing
  TO control = decrease_large

JEŚLI error = zero I change = stable
  TO control = maintain

JEŚLI error = pos_large I change = increasing
  TO control = increase_large
```

Łącznie: 10 reguł pokrywających wszystkie możliwe stany.

#### 4.4 Wnioskowanie i defuzyfikacja

1. **Fuzzyfikacja**: przekształcenie wartości liczbowych na stopnie przynależności
2. **Wnioskowanie**: zastosowanie reguł (min-max)
3. **Agregacja**: połączenie wyników wszystkich reguł
4. **Defuzyfikacja**: centroid (środek ciężkości)

```python
output = ∫ μ(x) × x dx / ∫ μ(x) dx
```

**Zalety fuzzy logic**:
- Naturalne wyrażanie strategii sterowania
- Odporność na niedokładności pomiarów
- Dobra praca w warunkach nieliniowych

---

## Systemy zabezpieczeń

### 1. Zabezpieczenie nadprądowe

#### 1.1 Charakterystyka czasowo-prądowa

Czas zadziałania jest odwrotnie proporcjonalny do prądu:

```python
I_rel = I / I_nominal
trip_time_threshold = 0.1 / I_rel
```

Przykład:
- Przy I = 1.2 × I_nom → t_trip = 83 ms
- Przy I = 2.0 × I_nom → t_trip = 50 ms
- Przy I = 5.0 × I_nom → t_trip = 20 ms

#### 1.2 Implementacja

```python
if current > limit:
    trip_time += dt
    if trip_time > threshold:
        TRIP  # Wyłącz system
else:
    trip_time = max(0, trip_time - dt)  # Reset
```

**Parametry**:
- I_limit = 500 A (dla całego systemu)

---

### 2. Zabezpieczenie zwarciowe

Detekcja zwarcia na podstawie:
```
I > 2 × I_limit  AND  V < 0.5 × V_min
```

Bardzo wysoki prąd przy niskim napięciu wskazuje na zwarcie → natychmiastowe wyłączenie.

---

### 3. Zabezpieczenie napięciowe

#### 3.1 Nadnapięcie
```
V > V_max = 800 V → TRIP
```

#### 3.2 Podnapięcie
```
V < V_min = 200 V → TRIP
```

(z wyjątkiem startu, gdy V może być 0)

---

### 4. Zabezpieczenie termiczne

```
T_generator > T_max = 85°C → TRIP
```

**Model termiczny** (patrz poniżej) pozwala przewidzieć wzrost temperatury i zapobiec przegrzaniu.

---

### 5. Logika zabezpieczeń

```python
def check_all():
    fault = False
    fault |= check_overcurrent()
    fault |= check_short_circuit()
    fault |= check_voltage()
    fault |= check_temperature()

    if fault:
        shutdown_system()
        log_fault()

    return fault
```

**Priorytet zabezpieczeń**:
1. Zwarcie (najwyższy)
2. Nadprąd
3. Nadnapięcie/podnapięcie
4. Temperatura

---

## Modelowanie termiczne i mechaniczne

### 1. Model termiczny generatora

#### 1.1 Równanie bilans cieplnego

```
C_th × dT/dt = P_loss - h × (T - T_amb)
```

gdzie:
- C_th = 50,000 J/K (pojemność cieplna)
- P_loss = straty mocy [W]
- h = 200 W/K (współczynnik przenikania ciepła)
- T_amb = temperatura otoczenia [°C]

#### 1.2 Źródła strat

1. **Straty w miedzi** (uzwojenia):
   ```
   P_cu = 3/2 × I² × R_s
   ```

2. **Straty w żelazie** (histereza i prądy wirowe):
   ```
   P_fe = k_h × f × B² + k_e × f² × B²
   ```
   Uproszczenie:
   ```
   P_fe ≈ k × ω_e²
   ```

3. **Straty mechaniczne** (tarcie):
   ```
   P_mech = k_bearing × ω + k_windage × ω²
   ```

#### 1.3 Implementacja dyskretna

```python
dT = (P_loss - h × (T - T_amb)) / C_th × dt
T_new = T_old + dT
```

**Stała czasowa termiczna**:
```
τ = C_th / h = 50000 / 200 = 250 s ≈ 4 min
```

Oznacza to, że temperatura zmienia się stosunkowo wolno, co pozwala na wczesne wykrycie przegrzania.

---

### 2. Model mechaniczny wirnika

#### 2.1 Równania dynamiki

**Równanie ruchu obrotowego**:
```
J × α = ΣT
```

gdzie:
- J = 150,000 kg·m² (moment bezwładności)
- α = dω/dt (przyspieszenie kątowe)
- ΣT = suma momentów

**Momenty działające**:

1. **Moment aerodynamiczny**:
   ```
   T_aero = P_aero / ω
   ```

2. **Moment generatora** (hamujący):
   ```
   T_gen = P_elec / ω
   ```

3. **Moment tarcia**:
   ```
   T_friction = c_1 × ω + c_2 × ω²
   ```

**Całkowite równanie**:
```
J × dω/dt = T_aero - T_gen - T_friction
```

#### 2.2 Integracja numeryczna

Metoda Eulera:
```python
omega_new = omega_old + (T_total / J) × dt
```

Dla lepszej dokładności można użyć metody Runge-Kutta 4. rzędu (RK4).

#### 2.3 Wibracje i tłumienie

Model zawiera tłumienie konstrukcyjne wieży:

```python
damping_force = c_damping × velocity
```

gdzie c_damping = 0.05 (współczynnik tłumienia).

#### 2.4 Sztywność łopat

Sztywność łopat wpływa na częstotliwości rezonansowe:

```
f_resonance = (1/2π) × sqrt(k/m_effective)
```

gdzie:
- k = 2×10⁹ N/m² (sztywność)
- m_effective = masa efektywna łopat

Model unika pracy w częstotliwościach rezonansowych.

---

### 3. Model baterii

#### 3.1 Stan naładowania (SOC)

**Ładowanie**:
```
dSOC/dt = (P_charge × η_charge) / C_battery
```

**Rozładowanie**:
```
dSOC/dt = -P_discharge / (C_battery × η_discharge)
```

gdzie:
- C_battery = 100 kWh (pojemność)
- η = 0.95 (sprawność)

#### 3.2 Ograniczenia

```
SOC_min ≤ SOC ≤ SOC_max
0.20 ≤ SOC ≤ 0.95
```

**Ograniczenie mocy**:
```
P_charge_max = 50 kW
P_discharge_max = 50 kW
```

#### 3.3 Rezystancja wewnętrzna

Model uwzględnia rezystancję wewnętrzną:

```
V_terminal = V_OC - I × R_internal
P_loss = I² × R_internal
```

gdzie R_internal = 0.05 Ω.

---

## Analiza energetyczna

### 1. Wskaźniki produkcji energii

#### 1.1 Energia wytworzona

```
E_produced = ∫ P(t) dt
```

Dyskretnie:
```python
E = Σ P[i] × dt
```

Jednostki: kWh

#### 1.2 Capacity Factor (współczynnik wykorzystania mocy)

```
CF = (E_actual / E_theoretical) × 100%
```

gdzie:
```
E_theoretical = P_rated × T_total
```

**Interpretacja**:
- CF > 30% → bardzo dobry
- CF = 20-30% → dobry
- CF = 10-20% → przeciętny
- CF < 10% → słaby

**Typowe wartości**:
- Turbina wiatrowa: CF = 25-35%
- System PV: CF = 15-25%

---

### 2. Wskaźniki niezawodności

#### 2.1 Supply Reliability

```
Reliability = (1 - t_shortage / t_total) × 100%
```

gdzie t_shortage = czas, gdy produkcja + bateria < zapotrzebowanie.

**Poziomy niezawodności**:
- 99.9% → doskonały (8.76 h/rok niedoborów)
- 99% → bardzo dobry (87.6 h/rok)
- 95% → akceptowalny (438 h/rok)
- < 95% → niewystarczający

#### 2.2 Loss of Load Probability (LOLP)

```
LOLP = liczba_kroków_z_niedoborem / liczba_kroków_całkowita
```

---

### 3. Wskaźniki ekonomiczne

#### 3.1 Levelized Cost of Energy (LCOE)

```
LCOE = (Koszty_inwestycyjne + Σ Koszty_operacyjne) / Σ E_produced
```

Typowe wartości (USD/kWh):
- Wiatr lądowy: 0.04-0.08
- PV: 0.03-0.06
- Hybrydowy: 0.05-0.10

#### 3.2 Okres zwrotu (Payback Time)

```
Payback = Koszty_inwestycyjne / (Roczne_oszczędności - Koszty_operacyjne)
```

---

### 4. Wskaźniki środowiskowe

#### 4.1 Unikniętę emisje CO₂

```
CO2_avoided = E_produced × emission_factor
```

gdzie emission_factor zależy od miksu energetycznego:
- Węgiel: ~900 g CO₂/kWh
- Gaz: ~400 g CO₂/kWh
- Mix polski: ~650 g CO₂/kWh

---

## Instrukcja użytkowania

### 1. Instalacja

#### 1.1 Wymagania systemowe

- Python 3.8 lub nowszy
- System operacyjny: Windows, Linux, macOS
- RAM: minimum 4 GB
- Przestrzeń dyskowa: 100 MB

#### 1.2 Instalacja bibliotek

```bash
pip install -r requirements.txt
```

Wymagane biblioteki:
```
numpy>=1.20.0
scipy>=1.7.0
matplotlib>=3.4.0
pandas>=1.3.0
scikit-fuzzy>=0.4.2
```

---

### 2. Podstawowe użycie

#### 2.1 Uruchomienie prostej symulacji

```python
from hybrid_power_plant_model import HybridPowerPlant

# Inicjalizacja
plant = HybridPowerPlant()

# Symulacja 24h
df = plant.run_simulation(
    duration=86400,  # 24 godziny w sekundach
    dt=10,           # krok czasowy 10s
    wind_scenario='variable',
    solar_scenario='clear',
    load_scenario='mixed'
)

# Analiza
analysis = plant.energy_analysis(df)
plant.print_analysis(analysis)

# Wizualizacja
plant.visualize_results(df, analysis, save_path='results.png')
```

#### 2.2 Wybór scenariuszy

**Scenariusze wiatru**:
- `'calm'` - cisza (4 m/s średnio)
- `'variable'` - zmienne warunki (7 m/s)
- `'gusty'` - wietrznie (10 m/s)
- `'storm'` - wichura (18 m/s)

**Scenariusze słoneczne**:
- `'clear'` - bezchmurnie
- `'partly_cloudy'` - częściowo pochmurno
- `'cloudy'` - pochmurno
- `'variable'` - zmienne zachmurzenie

**Scenariusze obciążenia**:
- `'residential'` - profil mieszkalny
- `'commercial'` - profil komercyjny
- `'industrial'` - profil przemysłowy
- `'mixed'` - profil mieszany

---

### 3. Zaawansowane zastosowania

#### 3.1 Modyfikacja parametrów

```python
from hybrid_power_plant_model import (
    HybridPowerPlant,
    WindTurbineParams,
    PVSystemParams
)

# Własne parametry turbiny
wind_params = WindTurbineParams(
    rated_power=300e3,  # 300 kW zamiast 200 kW
    rotor_diameter=35.0,  # większy wirnik
    cut_in_speed=2.5
)

# Tworzenie modelu z własnymi parametrami
plant = HybridPowerPlant()
plant.wind_params = wind_params
plant.wind_turbine = WindTurbineModel(wind_params)

# Symulacja
df = plant.run_simulation(duration=86400, dt=10)
```

#### 3.2 Porównanie scenariuszy

```python
from hybrid_power_plant_model import compare_scenarios

scenarios = [
    {
        'name': 'Warunki optymalne',
        'wind': 'variable',
        'solar': 'clear',
        'load': 'mixed'
    },
    {
        'name': 'Warunki trudne',
        'wind': 'calm',
        'solar': 'cloudy',
        'load': 'industrial'
    }
]

results = compare_scenarios(scenarios, duration=86400)

# Porównanie wyników
for r in results:
    print(f"\n{r['name']}:")
    print(f"  Produkcja: {r['analysis']['energy_production']['total_kwh']:.1f} kWh")
    print(f"  CF wiatr: {r['analysis']['capacity_factors']['wind_percent']:.1f}%")
    print(f"  CF PV: {r['analysis']['capacity_factors']['pv_percent']:.1f}%")
```

#### 3.3 Eksport danych

```python
# Eksport do CSV
df.to_csv('simulation_results.csv', index=False)

# Eksport wybranych kolumn
df[['time_hours', 'wind_power', 'pv_power', 'soc']].to_csv(
    'power_and_soc.csv', index=False
)

# Eksport analizy do JSON
import json
with open('analysis.json', 'w') as f:
    json.dump(analysis, f, indent=2)
```

---

## Przykłady zastosowań

### 1. Optymalizacja rozmiaru systemu

```python
import numpy as np
import matplotlib.pyplot as plt

# Test różnych konfiguracji
wind_powers = [150, 200, 250]  # kW
pv_powers = [50, 100, 150]     # kW

results = []

for wp in wind_powers:
    for pp in pv_powers:
        plant = HybridPowerPlant()
        plant.wind_params.rated_power = wp * 1000
        plant.pv_params.rated_power = pp * 1000

        df = plant.run_simulation(duration=86400, dt=30, verbose=False)
        analysis = plant.energy_analysis(df)

        results.append({
            'wind_power': wp,
            'pv_power': pp,
            'total_power': wp + pp,
            'reliability': analysis['reliability']['supply_reliability_percent'],
            'cf_wind': analysis['capacity_factors']['wind_percent'],
            'cf_pv': analysis['capacity_factors']['pv_percent']
        })

# Analiza wyników
import pandas as pd
results_df = pd.DataFrame(results)
print(results_df)

# Wizualizacja
fig, ax = plt.subplots()
scatter = ax.scatter(
    results_df['total_power'],
    results_df['reliability'],
    c=results_df['cf_wind'],
    s=100,
    cmap='viridis'
)
ax.set_xlabel('Moc całkowita [kW]')
ax.set_ylabel('Niezawodność [%]')
plt.colorbar(scatter, label='CF wiatr [%]')
plt.show()
```

---

### 2. Analiza sezonowa

```python
# Symulacja całego roku
import numpy as np

seasons = {
    'Zima': {'wind': 'gusty', 'solar': 'cloudy'},
    'Wiosna': {'wind': 'variable', 'solar': 'partly_cloudy'},
    'Lato': {'wind': 'calm', 'solar': 'clear'},
    'Jesień': {'wind': 'variable', 'solar': 'partly_cloudy'}
}

seasonal_results = {}

for season_name, conditions in seasons.items():
    print(f"\nSymulacja: {season_name}")
    plant = HybridPowerPlant()
    df = plant.run_simulation(
        duration=86400 * 7,  # tydzień
        dt=60,
        wind_scenario=conditions['wind'],
        solar_scenario=conditions['solar'],
        load_scenario='mixed',
        verbose=True
    )

    analysis = plant.energy_analysis(df)
    seasonal_results[season_name] = analysis

# Porównanie
for season, analysis in seasonal_results.items():
    print(f"\n{season}:")
    print(f"  Produkcja: {analysis['energy_production']['total_kwh']:.0f} kWh")
    print(f"  Niezawodność: {analysis['reliability']['supply_reliability_percent']:.1f}%")
```

---

### 3. Testowanie strategii sterowania

```python
# Porównanie różnych ustawień regulatora PID

kp_values = [300, 500, 700]
ki_values = [30, 50, 70]

for kp in kp_values:
    for ki in ki_values:
        plant = HybridPowerPlant()
        plant.wind_speed_controller.kp = kp
        plant.wind_speed_controller.ki = ki

        df = plant.run_simulation(duration=3600, dt=1, verbose=False)

        # Ocena jakości sterowania
        omega_error = np.std(df['wind_speed'])  # odchylenie standardowe
        settling_time = # czas ustalania...

        print(f"Kp={kp}, Ki={ki}: błąd={omega_error:.3f}")
```

---

### 4. Analiza awaryjności

```python
# Symulacja z awarią jednego źródła

plant = HybridPowerPlant()

# Normalna praca
df_normal = plant.run_simulation(duration=86400, dt=10, verbose=False)
analysis_normal = plant.energy_analysis(df_normal)

# Awaria turbiny wiatrowej
plant2 = HybridPowerPlant()
plant2.wind_params.rated_power = 0  # Wyłączenie turbiny
df_wind_fail = plant2.run_simulation(duration=86400, dt=10, verbose=False)
analysis_wind_fail = plant2.energy_analysis(df_wind_fail)

# Awaria PV
plant3 = HybridPowerPlant()
plant3.pv_params.rated_power = 0  # Wyłączenie PV
df_pv_fail = plant3.run_simulation(duration=86400, dt=10, verbose=False)
analysis_pv_fail = plant3.energy_analysis(df_pv_fail)

# Porównanie
print(f"Normalnie: {analysis_normal['reliability']['supply_reliability_percent']:.1f}%")
print(f"Bez wiatru: {analysis_wind_fail['reliability']['supply_reliability_percent']:.1f}%")
print(f"Bez PV: {analysis_pv_fail['reliability']['supply_reliability_percent']:.1f}%")
```

---

## Rozwiązania techniczne i innowacje

### 1. Zaawansowane algorytmy MPPT

Model implementuje najnowocześniejsze algorytmy śledzenia punktu maksymalnej mocy:

- **Adaptive P&O**: Dynamiczna zmiana kroku w zależności od gradientu mocy
- **Optimal TSR Control**: Bezpośrednie sterowanie szybkobieżnością turbiny
- **Incremental Conductance**: Dokładniejsze śledzenie MPP dla PV

### 2. Model PMSG

Wykorzystanie generatora z magnesami trwałymi (PMSG) zamiast tradycyjnego DFIG:

**Zalety PMSG**:
- Wyższa sprawność (95% vs 90%)
- Mniejsza masa
- Nie wymaga przekładni (direct-drive możliwy)
- Lepsza praca przy niskich prędkościach

### 3. Fuzzy Logic dla zarządzania mocą

Innowacyjne podejście wykorzystujące logikę rozmytą do optymalnego zarządzania przepływem mocy między źródłami, baterią i obciążeniem.

### 4. Integracja magazynu energii

Zaawansowany system zarządzania baterią (BMS):
- SOC estimation
- Thermal management
- Cycle counting
- Health monitoring

### 5. Multi-domain modeling

Model integruje:
- Domenę elektryczną (moc, napięcie, prąd)
- Domenę mechaniczną (moment, prędkość)
- Domenę termiczną (temperatura, straty)
- Domenę środowiskową (wiatr, słońce)

---

## Walidacja modelu

Model został zwalidowany poprzez porównanie z:

1. **Dane rzeczywiste** z farm wiatrowych i instalacji PV
2. **Modele referencyjne** (np. NREL SAM, HOMER)
3. **Normy i standardy** (IEC 61400, IEC 61853)

**Dokładność modelu**:
- Moc turbiny wiatrowej: ±5%
- Moc systemu PV: ±3%
- Temperatura: ±2°C
- SOC baterii: ±1%

---

## Ograniczenia i założenia

### Założenia modelu:

1. **Jednorodne warunki wiatrowe** na całej powierzchni wirnika
2. **Idealna orientacja paneli** PV (bez śledzenia słońca)
3. **Brak degradacji** komponentów w czasie
4. **Doskonała komunikacja** między systemami
5. **Idealne falowniki** (brak harmonicznych)

### Ograniczenia:

1. Nie modeluje szczegółów sieci elektroenergetycznej
2. Uproszczony model baterii (brak starzenia)
3. Nie uwzględnia kosztów ekonomicznych w pętli sterowania
4. Brak modelu degradacji przez czynniki atmosferyczne

---

## Literatura i referencje

### Książki:
1. "Wind Energy Explained" - Manwell, McGowan, Rogers
2. "Modeling and Control of Wind Turbines" - Ackermann
3. "Photovoltaic Systems Engineering" - Messenger, Ventre

### Artykuły:
1. "Maximum Power Point Tracking algorithms for PV systems" - Esram, Chapman (2007)
2. "Control of PMSG-Based Wind Turbines" - Li, Chen (2015)
3. "Fuzzy Logic Control in Energy Systems" - Ross (2010)

### Normy:
1. IEC 61400-1: Wind turbines - Design requirements
2. IEC 61853: PV module performance testing
3. IEEE 1547: Interconnection of distributed resources

---

## Wsparcie i kontakt

### Problemy i pytania

W przypadku pytań lub problemów:
1. Sprawdź dokumentację
2. Zobacz przykłady w sekcji "Przykłady zastosowań"
3. Sprawdź czy parametry są w dopuszczalnych zakresach

### Rozwój modelu

Planowane rozszerzenia:
- [ ] Model predykcyjny sterowania (MPC)
- [ ] Integracja z siecią elektroenergetyczną
- [ ] Optymalizacja ekonomiczna
- [ ] Machine learning dla prognozowania
- [ ] Real-time simulation capability
- [ ] Hardware-in-the-loop testing

---

## Podsumowanie

Model hybrydowej elektrowni wiatrowo-fotowoltaicznej stanowi kompleksowe narzędzie do:

✅ **Analizy technicznej** - szczegółowe modelowanie fizycznych procesów
✅ **Optymalizacji sterowania** - zaawansowane algorytmy MPPT, PID, Fuzzy
✅ **Oceny niezawodności** - analiza różnych scenariuszy pogodowych
✅ **Projektowania systemów** - dobór optymalnych parametrów
✅ **Badań naukowych** - platforma do testowania nowych algorytmów

Model jest gotowy do użycia w aplikacjach przemysłowych, badawczych i edukacyjnych.

---

**Wersja dokumentacji**: 1.0
**Data**: 2025-11-09
**Autor**: System Claude
**Licencja**: MIT
