"""Portfolio generation and loading utilities."""
import json
import numpy as np
from typing import Dict, List
from pathlib import Path
from scipy.stats import norm

# Factor loading by industry: [w_G, w_I, w_R]
INDUSTRY_FACTOR_LOADINGS = {
    'tech':           {'w': [0.60, 0.10, 0.05]},
    'real_estate':    {'w': [0.35, -0.25, 0.70]},
    'manufacturing':  {'w': [0.50, 0.15, 0.20]},
    'retail':         {'w': [0.40, 0.10, 0.30]},
    'energy':         {'w': [0.45, 0.30, 0.10]},
}

# Credit rating mapping
RATING_PD_MAP = {
    'AAA': 0.0001,
    'AA':  0.0004,
    'A':   0.0010,
    'BBB': 0.0025,
    'BB':  0.0100,
    'B':   0.0500,
    'CCC': 0.1500,
}

RATING_WEIGHTS = [0.05, 0.10, 0.25, 0.30, 0.18, 0.10, 0.02]

# LGD by collateral type
LGD_MAP = {
    'residential_mortgage': 0.30,
    'commercial_mortgage':  0.45,
    'secured':              0.40,
    'unsecured':            0.60,
}

COLLATERAL_WEIGHTS = [0.30, 0.20, 0.30, 0.20]


def generate_portfolio(num_loans: int = 40000, seed: int = 42) -> List[Dict]:
    """Generate a synthetic loan portfolio."""
    rng = np.random.default_rng(seed)

    industries = list(INDUSTRY_FACTOR_LOADINGS.keys())
    industry_weights = [0.20, 0.25, 0.30, 0.15, 0.10]
    ratings_list = list(RATING_PD_MAP.keys())
    collateral_types = list(LGD_MAP.keys())

    ead = np.round(rng.lognormal(mean=13.0, sigma=0.8, size=num_loans), 2)
    chosen_ratings = rng.choice(ratings_list, size=num_loans, p=RATING_WEIGHTS)
    pd_base_arr = np.array([RATING_PD_MAP[r] for r in chosen_ratings])
    industry_arr = rng.choice(industries, size=num_loans, p=industry_weights)
    collateral_arr = rng.choice(collateral_types, size=num_loans, p=COLLATERAL_WEIGHTS)

    portfolio = []
    for i in range(num_loans):
        ind = industry_arr[i]
        coll = collateral_arr[i]
        w = INDUSTRY_FACTOR_LOADINGS[ind]['w']
        w_sq_sum = sum(x * x for x in w)
        sigma_i = np.sqrt(max(0.0, 1.0 - w_sq_sum))

        loan = {
            'id': f'LOAN_{i:06d}',
            'ead': float(ead[i]),
            'lgd_base': float(LGD_MAP[coll]),
            'pd_base': float(pd_base_arr[i]),
            'rating': str(chosen_ratings[i]),
            'industry': str(ind),
            'collateral_type': str(coll),
            'factor_weights': {
                'G': float(w[0]),
                'I': float(w[1]),
                'R': float(w[2]),
            },
            'sigma_idio': float(sigma_i),
        }
        portfolio.append(loan)

    return portfolio


def save_portfolio(portfolio: List[Dict], filepath: str = 'data/portfolio.json'):
    """Save portfolio to JSON."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(portfolio, f)
    print(f"Saved {len(portfolio)} loans to {path}")


def load_portfolio(filepath: str = 'data/portfolio.json') -> List[Dict]:
    """Load portfolio from JSON."""
    with open(filepath, 'r') as f:
        portfolio = json.load(f)
    return portfolio


def portfolio_to_arrays(portfolio: List[Dict]) -> dict:
    """Convert portfolio list to NumPy arrays for vectorized computation."""
    n = len(portfolio)
    ead = np.zeros(n)
    lgd = np.zeros(n)
    pd_base = np.zeros(n)
    w_G = np.zeros(n)
    w_I = np.zeros(n)
    w_R = np.zeros(n)
    sigma_idio = np.zeros(n)

    for i, loan in enumerate(portfolio):
        ead[i] = loan['ead']
        lgd[i] = loan['lgd_base']
        pd_base[i] = loan['pd_base']
        w_G[i] = loan['factor_weights']['G']
        w_I[i] = loan['factor_weights']['I']
        w_R[i] = loan['factor_weights']['R']
        sigma_idio[i] = loan['sigma_idio']

    # Default threshold B = Phi^{-1}(PD)
    B = norm.ppf(np.clip(pd_base, 1e-10, 1 - 1e-10))

    return {
        'ead': ead,
        'lgd': lgd,
        'pd_base': pd_base,
        'w_G': w_G,
        'w_I': w_I,
        'w_R': w_R,
        'sigma_idio': sigma_idio,
        'B': B,
        'n': n,
    }


if __name__ == '__main__':
    pf = generate_portfolio(40000)
    save_portfolio(pf)
    print("Portfolio generated successfully.")