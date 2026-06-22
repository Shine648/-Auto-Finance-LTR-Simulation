"""Quick test of validation engine - prints stress comparison results."""
import sys
sys.path.insert(0, 'credit_sim')

from engine.validation import ValidationEngine
from engine.simulation import MonteCarloSimulator
from engine.portfolio import load_portfolio
from engine.factors import macro_to_factors, FactorModel
import json

print("Loading...")
v = ValidationEngine()
v.load()
portfolio = load_portfolio('credit_sim/data/portfolio.json')
sim = MonteCarloSimulator(portfolio, n_simulations=5000, seed=42)
fm = FactorModel()

results = []
for name, gdp, unemp, hpc in [
    ('Baseline',         2.0, 4.5,   0.0),
    ('Mild Recession',   0.5, 6.0,  -3.0),
    ('Severe Recession',-2.0, 9.0, -10.0),
    ('Boom',             4.0, 3.0,   8.0),
    ('Housing Crisis',   1.0, 7.0, -15.0),
]:
    factor_means = macro_to_factors(gdp, unemp, hpc)
    r = sim.simulate(factor_means, n_simulations=5000)
    pd_val = r.get('pd_scenario', 0)
    fm.set_factor_means(factor_means)
    label = fm.scenario_label
    
    # Run validation
    actual_rates = v.compute_actual_delinquency_rates()
    phase_map = {
        'Baseline': 'Expansion', 'Mild Recession': 'Slowing',
        'Severe Recession': 'Recession', 'Boom': 'Peak',
        'Housing Crisis': 'Recession',
    }
    phase = phase_map.get(label, 'Unknown')
    matches = [x for x in actual_rates if x['phase'] == phase]
    
    if matches:
        act_mean = sum(x['total_delinquency_rate'] for x in matches) / len(matches)
        act_90p = sum(x['delinquency_90p_rate'] for x in matches) / len(matches)
        ratio = pd_val / act_mean if act_mean > 0 else 0
        accuracy = max(0, 1 - abs(pd_val - act_mean) / max(act_mean, 1e-10))
        results.append({
            'scenario': label,
            'sim_pd': f'{pd_val*100:.3f}%',
            'actual_delinq': f'{act_mean*100:.3f}%',
            'actual_90p': f'{act_90p*100:.3f}%',
            'ratio': f'{ratio:.2f}x',
            'accuracy': f'{accuracy*100:.1f}%',
            'phase': phase,
            'n_months': len(matches),
        })
    else:
        results.append({
            'scenario': label,
            'sim_pd': f'{pd_val*100:.3f}%',
            'actual_delinq': 'NO DATA',
            'actual_90p': '-',
            'ratio': '-',
            'accuracy': '-',
            'phase': f'{phase} (no data)',
            'n_months': 0,
        })

print("\n" + "="*95)
print(f"{'Scenario':20s} {'Sim PD':>8s} {'Actual Delinq':>14s} {'90+ Delinq':>11s} {'Ratio':>7s} {'Accuracy':>10s} {'Phase'}")
print("="*95)
for r in results:
    print(f"{r['scenario']:20s} {r['sim_pd']:>8s} {r['actual_delinq']:>14s} {r['actual_90p']:>11s} {r['ratio']:>7s} {r['accuracy']:>10s} {r['phase']}")

print("\n=== PD Term Structure (aggregated, first 24 months) ===")
pts = v.compute_pd_term_structure()
print(f"{'MoB':>4s} {'Delinq%':>9s} {'90+%':>9s}")
for p in pts[:24]:
    print(f"{p['month_on_book']:>4d} {p['avg_delinquency_pct']:>7.3f}% {p['avg_default_rate_90p_pct']:>7.3f}%")