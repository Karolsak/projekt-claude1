"""
Przykładowe skrypty demonstracyjne dla modelu hybrydowej elektrowni
====================================================================

Ten plik zawiera przykłady użycia modelu dla różnych scenariuszy.
"""

import numpy as np
import matplotlib.pyplot as plt
from hybrid_power_plant_model import (
    HybridPowerPlant,
    compare_scenarios,
    WindTurbineParams,
    PVSystemParams
)


def example_1_basic_simulation():
    """
    Przykład 1: Podstawowa symulacja 24-godzinna
    """
    print("="*80)
    print("PRZYKŁAD 1: Podstawowa symulacja dobowa")
    print("="*80)

    plant = HybridPowerPlant()

    df = plant.run_simulation(
        duration=86400,  # 24 godziny
        dt=10,
        wind_scenario='variable',
        solar_scenario='clear',
        load_scenario='mixed',
        verbose=True
    )

    analysis = plant.energy_analysis(df)
    plant.print_analysis(analysis)

    plant.visualize_results(df, analysis, save_path='example1_basic.png')

    return plant, df, analysis


def example_2_scenario_comparison():
    """
    Przykład 2: Porównanie różnych scenariuszy pogodowych
    """
    print("\n\n" + "="*80)
    print("PRZYKŁAD 2: Porównanie scenariuszy pogodowych")
    print("="*80)

    scenarios = [
        {
            'name': 'Warunki idealne',
            'wind': 'variable',
            'solar': 'clear',
            'load': 'residential',
            'dt': 10
        },
        {
            'name': 'Dzień pochmurny, wietrzny',
            'wind': 'gusty',
            'solar': 'cloudy',
            'load': 'mixed',
            'dt': 10
        },
        {
            'name': 'Cisza i bezchmurnie',
            'wind': 'calm',
            'solar': 'clear',
            'load': 'industrial',
            'dt': 10
        }
    ]

    results = compare_scenarios(scenarios, duration=86400)

    # Wizualizacja porównawcza
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    for i, r in enumerate(results):
        ax = axes[i//2, i%2]
        df = r['dataframe']
        ax.plot(df['time_hours'], df['wind_power'], label='Wiatr')
        ax.plot(df['time_hours'], df['pv_power'], label='PV')
        ax.plot(df['time_hours'], df['load_power'], label='Obciążenie', linestyle='--')
        ax.set_title(r['name'])
        ax.set_xlabel('Czas [h]')
        ax.set_ylabel('Moc [kW]')
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Czwarty wykres - porównanie energii
    ax = axes[1, 1]
    names = [r['name'] for r in results]
    wind_energy = [r['analysis']['energy_production']['wind_kwh'] for r in results]
    pv_energy = [r['analysis']['energy_production']['pv_kwh'] for r in results]

    x = np.arange(len(names))
    width = 0.35

    ax.bar(x - width/2, wind_energy, width, label='Wiatr', alpha=0.8)
    ax.bar(x + width/2, pv_energy, width, label='PV', alpha=0.8)
    ax.set_ylabel('Energia [kWh]')
    ax.set_title('Porównanie produkcji energii')
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('example2_comparison.png', dpi=300, bbox_inches='tight')
    print("\nWykres porównawczy zapisany: example2_comparison.png")

    return results


def example_3_weekly_simulation():
    """
    Przykład 3: Symulacja tygodniowa
    """
    print("\n\n" + "="*80)
    print("PRZYKŁAD 3: Symulacja tygodniowa")
    print("="*80)

    plant = HybridPowerPlant()

    df = plant.run_simulation(
        duration=7*86400,  # 7 dni
        dt=60,  # większy krok dla długiej symulacji
        wind_scenario='variable',
        solar_scenario='partly_cloudy',
        load_scenario='mixed',
        verbose=True
    )

    analysis = plant.energy_analysis(df)
    plant.print_analysis(analysis)

    # Dodatkowa wizualizacja - trend SOC
    fig, axes = plt.subplots(3, 1, figsize=(15, 10))

    # Moc
    axes[0].plot(df['time_hours'], df['wind_power'], label='Wiatr', alpha=0.7)
    axes[0].plot(df['time_hours'], df['pv_power'], label='PV', alpha=0.7)
    axes[0].plot(df['time_hours'], df['load_power'], label='Obciążenie',
                linestyle='--', color='red', alpha=0.7)
    axes[0].set_ylabel('Moc [kW]')
    axes[0].set_title('Profil mocy - tydzień')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # SOC
    axes[1].plot(df['time_hours'], df['soc'], color='blue', linewidth=2)
    axes[1].axhline(y=20, color='red', linestyle='--', alpha=0.5, label='Min SOC')
    axes[1].axhline(y=95, color='orange', linestyle='--', alpha=0.5, label='Max SOC')
    axes[1].set_ylabel('SOC [%]')
    axes[1].set_title('Stan naładowania baterii')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Sprawność
    axes[2].plot(df['time_hours'], df['efficiency'], color='green', alpha=0.7)
    axes[2].set_ylabel('Sprawność [%]')
    axes[2].set_xlabel('Czas [h]')
    axes[2].set_title('Sprawność systemu')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('example3_weekly.png', dpi=300, bbox_inches='tight')
    print("\nWykres tygodniowy zapisany: example3_weekly.png")

    return plant, df, analysis


def example_4_parameter_optimization():
    """
    Przykład 4: Optymalizacja parametrów systemu
    """
    print("\n\n" + "="*80)
    print("PRZYKŁAD 4: Optymalizacja rozmiaru systemu")
    print("="*80)

    # Test różnych proporcji wiatr/PV
    ratios = [
        (250, 50),   # 5:1
        (200, 100),  # 2:1 (bazowy)
        (150, 150),  # 1:1
        (100, 200),  # 1:2
        (50, 250),   # 1:5
    ]

    results = []

    for wind_kw, pv_kw in ratios:
        print(f"\nTestowanie konfiguracji: Wiatr={wind_kw}kW, PV={pv_kw}kW")

        plant = HybridPowerPlant()
        plant.wind_params.rated_power = wind_kw * 1000
        plant.pv_params.rated_power = pv_kw * 1000

        df = plant.run_simulation(
            duration=86400,
            dt=30,
            wind_scenario='variable',
            solar_scenario='clear',
            load_scenario='mixed',
            verbose=False
        )

        analysis = plant.energy_analysis(df)

        results.append({
            'wind_kw': wind_kw,
            'pv_kw': pv_kw,
            'total_kw': wind_kw + pv_kw,
            'ratio': f"{wind_kw}:{pv_kw}",
            'energy_kwh': analysis['energy_production']['total_kwh'],
            'reliability': analysis['reliability']['supply_reliability_percent'],
            'cf_wind': analysis['capacity_factors']['wind_percent'],
            'cf_pv': analysis['capacity_factors']['pv_percent'],
            'curtailed': analysis['energy_consumption']['curtailed_kwh']
        })

    # Wizualizacja
    import pandas as pd
    results_df = pd.DataFrame(results)

    print("\n" + "="*80)
    print("WYNIKI OPTYMALIZACJI:")
    print("="*80)
    print(results_df.to_string(index=False))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Energia vs stosunek
    axes[0, 0].bar(results_df['ratio'], results_df['energy_kwh'], color='steelblue', alpha=0.7)
    axes[0, 0].set_ylabel('Energia wyprodukowana [kWh]')
    axes[0, 0].set_xlabel('Stosunek Wiatr:PV')
    axes[0, 0].set_title('Produkcja energii')
    axes[0, 0].grid(True, alpha=0.3, axis='y')
    axes[0, 0].tick_params(axis='x', rotation=45)

    # Niezawodność vs stosunek
    axes[0, 1].plot(results_df['ratio'], results_df['reliability'],
                   marker='o', linewidth=2, markersize=8, color='green')
    axes[0, 1].axhline(y=95, color='red', linestyle='--', alpha=0.5, label='Cel 95%')
    axes[0, 1].set_ylabel('Niezawodność [%]')
    axes[0, 1].set_xlabel('Stosunek Wiatr:PV')
    axes[0, 1].set_title('Niezawodność zasilania')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].tick_params(axis='x', rotation=45)

    # Capacity factors
    x = np.arange(len(results_df))
    width = 0.35
    axes[1, 0].bar(x - width/2, results_df['cf_wind'], width,
                  label='CF Wiatr', alpha=0.8)
    axes[1, 0].bar(x + width/2, results_df['cf_pv'], width,
                  label='CF PV', alpha=0.8)
    axes[1, 0].set_ylabel('Capacity Factor [%]')
    axes[1, 0].set_xlabel('Konfiguracja')
    axes[1, 0].set_title('Współczynniki wykorzystania')
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(results_df['ratio'], rotation=45)
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3, axis='y')

    # Energia zredukowana (curtailment)
    axes[1, 1].bar(results_df['ratio'], results_df['curtailed'],
                  color='orange', alpha=0.7)
    axes[1, 1].set_ylabel('Energia zredukowana [kWh]')
    axes[1, 1].set_xlabel('Stosunek Wiatr:PV')
    axes[1, 1].set_title('Straty przez curtailment')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    axes[1, 1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig('example4_optimization.png', dpi=300, bbox_inches='tight')
    print("\nWykres optymalizacji zapisany: example4_optimization.png")

    # Znajdź optymalną konfigurację
    best_idx = results_df['reliability'].idxmax()
    best_config = results_df.iloc[best_idx]

    print(f"\n{'='*80}")
    print("OPTYMALNA KONFIGURACJA (max niezawodność):")
    print(f"{'='*80}")
    print(f"Wiatr: {best_config['wind_kw']} kW")
    print(f"PV: {best_config['pv_kw']} kW")
    print(f"Niezawodność: {best_config['reliability']:.2f}%")
    print(f"Produkcja: {best_config['energy_kwh']:.1f} kWh/dzień")
    print(f"{'='*80}")

    return results_df


def example_5_extreme_conditions():
    """
    Przykład 5: Test w ekstremalnych warunkach
    """
    print("\n\n" + "="*80)
    print("PRZYKŁAD 5: Testy w warunkach ekstremalnych")
    print("="*80)

    extreme_scenarios = [
        {
            'name': 'Wichura + burza (test zabezpieczeń)',
            'wind': 'storm',
            'solar': 'cloudy',
            'load': 'industrial'
        },
        {
            'name': 'Cisza nocna (zależność od baterii)',
            'wind': 'calm',
            'solar': 'cloudy',
            'load': 'residential'
        },
        {
            'name': 'Dzień słoneczny, bez wiatru',
            'wind': 'calm',
            'solar': 'clear',
            'load': 'commercial'
        }
    ]

    for scenario in extreme_scenarios:
        print(f"\n{'-'*80}")
        print(f"Test: {scenario['name']}")
        print(f"{'-'*80}")

        plant = HybridPowerPlant()
        df = plant.run_simulation(
            duration=86400,
            dt=10,
            wind_scenario=scenario['wind'],
            solar_scenario=scenario['solar'],
            load_scenario=scenario['load'],
            verbose=False
        )

        analysis = plant.energy_analysis(df)

        # Sprawdzenie działania zabezpieczeń
        num_faults = 0
        # To wymaga dostępu do flag błędów z każdego kroku, co nie jest
        # dostępne w historii. W rzeczywistym zastosowaniu dodalibyśmy
        # tracking błędów.

        print(f"\nWyniki:")
        print(f"  Produkcja wiatr: {analysis['energy_production']['wind_kwh']:.1f} kWh")
        print(f"  Produkcja PV: {analysis['energy_production']['pv_kwh']:.1f} kWh")
        print(f"  Niezawodność: {analysis['reliability']['supply_reliability_percent']:.2f}%")
        print(f"  Min SOC: {df['soc'].min():.1f}%")
        print(f"  Max SOC: {df['soc'].max():.1f}%")
        print(f"  Max temperatura generatora: {df['wind_temp'].max():.1f}°C")


def example_6_battery_analysis():
    """
    Przykład 6: Szczegółowa analiza pracy baterii
    """
    print("\n\n" + "="*80)
    print("PRZYKŁAD 6: Analiza pracy magazynu energii")
    print("="*80)

    plant = HybridPowerPlant()

    df = plant.run_simulation(
        duration=3*86400,  # 3 dni
        dt=30,
        wind_scenario='variable',
        solar_scenario='partly_cloudy',
        load_scenario='mixed',
        verbose=True
    )

    # Analiza cykli baterii
    soc = df['soc'].values
    battery_power = df['battery_power'].values

    # Zliczanie cykli (uproszczone)
    charging_events = np.sum(np.diff(battery_power < 0).astype(int) == 1)
    discharging_events = np.sum(np.diff(battery_power > 0).astype(int) == 1)

    # Analiza głębokości rozładowania (DoD)
    soc_range = soc.max() - soc.min()

    print(f"\nAnaliza baterii:")
    print(f"  Liczba rozpoczęć ładowania: {charging_events}")
    print(f"  Liczba rozpoczęć rozładowania: {discharging_events}")
    print(f"  Zakres SOC: {soc_range:.1f}%")
    print(f"  Średni SOC: {soc.mean():.1f}%")

    # Wizualizacja
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    # SOC w czasie
    axes[0].plot(df['time_hours'], df['soc'], linewidth=1.5)
    axes[0].fill_between(df['time_hours'], 20, 95, alpha=0.2, color='green',
                         label='Zakres operacyjny')
    axes[0].set_ylabel('SOC [%]')
    axes[0].set_title('Stan naładowania baterii')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Moc baterii
    colors = ['red' if p > 0 else 'green' for p in df['battery_power']]
    axes[1].bar(df['time_hours'], df['battery_power'],
               width=df['time_hours'].diff().mean(),
               color=colors, alpha=0.6)
    axes[1].axhline(y=0, color='black', linewidth=0.5)
    axes[1].set_ylabel('Moc baterii [kW]')
    axes[1].set_title('Przepływ mocy (dodatni=rozładowanie, ujemny=ładowanie)')
    axes[1].grid(True, alpha=0.3)

    # Histogram SOC
    axes[2].hist(df['soc'], bins=50, color='blue', alpha=0.7, edgecolor='black')
    axes[2].set_xlabel('SOC [%]')
    axes[2].set_ylabel('Liczba wystąpień')
    axes[2].set_title('Rozkład stanu naładowania')
    axes[2].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('example6_battery.png', dpi=300, bbox_inches='tight')
    print("\nWykres analizy baterii zapisany: example6_battery.png")

    return df


def run_all_examples():
    """Uruchomienie wszystkich przykładów"""
    print("\n" + "="*80)
    print(" "*20 + "URUCHAMIANIE WSZYSTKICH PRZYKŁADÓW")
    print("="*80 + "\n")

    try:
        # Przykład 1
        plant1, df1, analysis1 = example_1_basic_simulation()

        # Przykład 2
        results2 = example_2_scenario_comparison()

        # Przykład 3
        plant3, df3, analysis3 = example_3_weekly_simulation()

        # Przykład 4
        results4 = example_4_parameter_optimization()

        # Przykład 5
        example_5_extreme_conditions()

        # Przykład 6
        df6 = example_6_battery_analysis()

        print("\n\n" + "="*80)
        print(" "*25 + "WSZYSTKIE PRZYKŁADY ZAKOŃCZONE!")
        print("="*80)
        print("\nWygenerowane pliki:")
        print("  - example1_basic.png")
        print("  - example2_comparison.png")
        print("  - example3_weekly.png")
        print("  - example4_optimization.png")
        print("  - example6_battery.png")
        print("  - simulation_results.csv")
        print("\n")

    except Exception as e:
        print(f"\n❌ Błąd podczas wykonywania przykładów: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Możesz uruchomić wszystkie przykłady lub wybrane:

    # Opcja 1: Wszystkie przykłady
    run_all_examples()

    # Opcja 2: Wybrane przykłady (odkomentuj co chcesz uruchomić)
    # example_1_basic_simulation()
    # example_2_scenario_comparison()
    # example_3_weekly_simulation()
    # example_4_parameter_optimization()
    # example_5_extreme_conditions()
    # example_6_battery_analysis()

    plt.show()  # Wyświetl wszystkie wykresy
