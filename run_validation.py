"""Run full calibration validation."""
import sys
sys.path.insert(0, 'credit_sim')

from engine.portfolio import load_csv_portfolio
from engine.factors import macro_to_factors
from engine.simulation import MonteCarloSimulator
from engine.validation import ValidationEngine
import numpy as np

# Load calibrated data
portfolio = load_csv_portfolio()
sim = MonteCarloSimulator(portfolio, n_simulations=3000, seed=42)
v = ValidationEngine(); v.load()
rates = v.compute_actual_delinquency_rates()

# Phase mapping
phase_map = {
    'Baseline': 'Expansion', 'Mild Recession': 'Slowing',
    'Severe Recession': 'Recession', 'Boom': 'Peak',
    'Housing Crisis': 'Recession',
}

scenarios = [
    ('Baseline',         2.0, 4.5,   0.0),
    ('Mild Recession',   0.5, 6.0,  -3.0),
    ('Severe Recession',-2.0, 9.0, -10.0),
    ('Boom',             4.0, 3.0,   8.0),
    ('Housing Crisis',   1.0, 7.0, -15.0),
]

print("=" * 90)
print(f"{'Scenario':20s} {'Sim PD':>9s} {'Actual Delinq':>14s} {'90+ Delinq':>12s} {'Ratio':>7s} {'Accuracy':>9s}  {'Phase'}")
print("=" * 90)

for name, g, u, h in scenarios:
    fm = macro_to_factors(g, u, h)
    r = sim.simulate(fm, n_simulations=3000)
    pd_sim = r.get('pd_scenario', 0)
    loss_rate = r.get('loss_rate', 0)
    
    phase = phase_map.get(name, 'Unknown')
    matches = [x for x in rates if x['phase'] == phase]
    
    if matches:
        act_delinq = np.mean([x['total_delinquency_rate'] for x in matches])
        act_90p = np.mean([x['delinquency_90p_rate'] for x in matches])
        ratio = pd_sim / act_delinq if act_delinq > 0 else 0
        accuracy = max(0, 1 - abs(pd_sim - act_delinq) / max(act_delinq, 1e-10))
        print(f"{name:20s} {pd_sim*100:>7.3f}% {act_delinq*100:>11.3f}% {act_90p*100:>9.3f}% {ratio:>5.2f}x {accuracy*100:>7.1f}%  {phase}")
    else:
        print(f"{name:20s} {pd_sim*100:>7.3f}% {'N/A':>14s} {'N/A':>12s}")

print(f"\n=== Portfolio Summary ===")
print(f"Loans: {len(portfolio)}")
pds = [x['pd_base'] for x in portfolio]
lgds = [x['lgd_base'] for x in portfolio]
print(f"Mean PD: {np.mean(pds)*100:.3f}%")
print(f"Mean LGD: {np.mean(lgds)*100:.1f}%")

for r in ['A','B','C','D']:
    rp = [x['pd_base'] for x in portfolio if x['rating']==r]
    if rp: print(f"  Rating {r}: mean PD={np.mean(rp)*100:.3f}% (n={len(rp)})")

print(f"\n=== PD Term Structure (actual) ===")
pts = v.compute_pd_term_structure()
print(f"MoB 1-12: {pts[0]['avg_delinquency_pct']:.2f}% to {pts[11]['avg_delinquency_pct']:.2f}%")
print(f"90+ at MoB 12: {pts[11]['avg_default_rate_90p_pct']:.3f}%")