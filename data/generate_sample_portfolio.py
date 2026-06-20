"""
Generate a sample synthetic portfolio for demo/CI purposes.
This creates fake data so users can run the system without the real CSV.
"""
import sys, os, json, numpy as np, pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_PATH = Path(__file__).parent / 'portfolio.json'

RATINGS = ['A','B','C','D']
RATING_WEIGHTS = [0.30, 0.40, 0.20, 0.10]
VEHICLES = ['New', 'Used']
VEHICLE_WEIGHTS = [0.65, 0.35]
PHASES = ['Expansion','Peak','Slowing','Recession','Trough','Early Recovery','Recovery','Normal']
PHASE_WEIGHTS = [0.15, 0.12, 0.15, 0.12, 0.10, 0.12, 0.12, 0.12]

def generate(num_loans=5000, seed=123):
    rng = np.random.default_rng(seed)

    ratings = rng.choice(RATINGS, size=num_loans, p=RATING_WEIGHTS)
    vehicles = rng.choice(VEHICLES, size=num_loans, p=VEHICLE_WEIGHTS)
    years = rng.integers(1, 9, size=num_loans)
    phases = rng.choice(PHASES, size=num_loans, p=PHASE_WEIGHTS)

    loan_amount = rng.lognormal(mean=11.5, sigma=0.6, size=num_loans)
    ltv = rng.uniform(0.40, 0.85, size=num_loans)
    term = rng.choice([24, 36, 48, 60], size=num_loans, p=[0.1, 0.3, 0.4, 0.2])
    outstanding = loan_amount * rng.uniform(0.3, 0.95, size=num_loans)

    # PD by rating
    pd_map = {'A': 0.01, 'B': 0.03, 'C': 0.08, 'D': 0.18}
    # LGD by vehicle
    lgd_map = {'New': 0.40, 'Used': 0.55}

    # Macro stress multiplier (year-based)
    stress_map = {1:0.4, 2:0.2, 3:0.6, 4:1.5, 5:2.5, 6:1.2, 7:0.7, 8:0.5}

    portfolio = []
    for i in range(num_loans):
        r = ratings[i]
        v = vehicles[i]
        y = years[i]
        pd_base = pd_map[r] * stress_map[y]
        lgd_base = lgd_map[v] * (1.0 + 0.1 * (stress_map[y] - 0.5))
        pd_base = np.clip(pd_base, 0.001, 0.35)
        lgd_base = np.clip(lgd_base, 0.20, 0.80)

        is_default = int(rng.random() < pd_base)
        loss = outstanding[i] * lgd_base if is_default else 0.0

        loan = {
            'id': f'SAMPLE_{i:06d}',
            'origination_year': int(y),
            'borrower_rating': str(r),
            'vehicle_type': str(v),
            'loan_amount': round(float(loan_amount[i]), 2),
            'ltv': round(float(ltv[i]), 4),
            'term_months': int(term[i]),
            'ead': round(float(outstanding[i]), 2),
            'lgd_base': round(float(lgd_base), 4),
            'pd_base': round(float(pd_base), 4),
            'macro_scenario': str(phases[i]),
            'is_default': is_default,
            'loss_amount': round(float(loss), 2),
            'industry': 'manufacturing' if v == 'New' else 'retail',
            'factor_weights': {'G': 0.48, 'I': 0.12, 'R': 0.25},
            'sigma_idio': round(np.sqrt(1 - 0.48**2 - 0.12**2 - 0.25**2), 4),
        }
        portfolio.append(loan)

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(portfolio, f)

    print(f"Generated {len(portfolio)} sample loans → {OUTPUT_PATH}")
    print(f"  Default rate: {sum(l['is_default'] for l in portfolio)/len(portfolio):.3f}")
    print(f"  Total exposure: ${sum(l['ead'] for l in portfolio):,.0f}")
    return portfolio

if __name__ == '__main__':
    generate()