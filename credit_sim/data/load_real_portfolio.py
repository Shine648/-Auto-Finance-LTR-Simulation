"""
Load auto finance CSV and convert to simulation portfolio JSON format.

Data Schema per loan:
  Loan_ID, Origination_Year, Borrower_Rating, Vehicle_Type,
  Loan_Amount, LTV, Term, Outstanding_Balance, Macro_Scenario,
  Simulated_PD, Simulated_LGD, Is_Default, Loss_Amount
"""
import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CSV_PATH = Path(__file__).parent.parent.parent / 'auto_finance_credit_portfolio.csv'
OUTPUT_PATH = Path(__file__).parent / 'portfolio.json'

# Macro phase → stress level mapping
MACRO_STRESS_MAP = {
    'Peak': 0.8,
    'Expansion': 0.5,
    'Normal': 0.0,
    'Early_Rec': -0.2,
    'Recovery': -0.3,
    'Slowing': -0.5,
    'Recession': -0.8,
    'Trough': -1.2,
}

# Vehicle type → industry (for factor loadings)
VEHICLE_TO_INDUSTRY = {
    'New': 'manufacturing',
    'Used': 'retail',
}

# Rating → factor loading multiplier (higher risk = more macro sensitivity)
RATING_FACTOR_MULT = {
    'A': 0.6,
    'B': 0.8,
    'C': 1.0,
    'D': 1.2,
}

# Base factor loadings by industry
BASE_FACTOR_LOADINGS = {
    'manufacturing': {'G': 0.50, 'I': 0.15, 'R': 0.20},
    'retail':        {'G': 0.40, 'I': 0.10, 'R': 0.30},
}


def load_and_convert(csv_path: str = None, output_path: str = None) -> list:
    """Load auto finance CSV and convert to simulation portfolio format."""
    csv_path = csv_path or str(CSV_PATH)
    output_path = output_path or str(OUTPUT_PATH)

    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        return None

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} records from {csv_path}")
    print(f"Columns: {list(df.columns)}")

    portfolio = []
    for idx, row in df.iterrows():
        loan_id = str(row['Loan_ID'])
        vehicle_type = str(row['Vehicle_Type'])
        rating = str(row['Borrower_Rating'])
        industry = VEHICLE_TO_INDUSTRY.get(vehicle_type, 'manufacturing')

        ead = float(row['Outstanding_Balance'])
        lgd = float(row['Simulated_LGD'])
        pd_val = float(row['Simulated_PD'])

        # Factor weights from industry × rating multiplier
        base_w = BASE_FACTOR_LOADINGS[industry]
        rmult = RATING_FACTOR_MULT.get(rating, 0.8)
        w_G = base_w['G'] * rmult
        w_I = base_w['I'] * rmult
        w_R = base_w['R'] * rmult
        w_sq_sum = w_G*w_G + w_I*w_I + w_R*w_R
        sigma_idio = np.sqrt(max(0.05, 1.0 - w_sq_sum))

        loan = {
            'id': loan_id,
            'origination_year': int(row['Observation_Year']),  # Year 1-8
            'borrower_rating': rating,
            'vehicle_type': vehicle_type,
            'loan_amount': float(row['Loan_Amount']),
            'ltv': float(row['LTV']),
            'term_months': int(row['Term_Months']),
            'ead': ead,
            'lgd_base': lgd,
            'pd_base': pd_val,
            'macro_scenario': str(row['Macro_Phase']),
            'macro_stress': MACRO_STRESS_MAP.get(str(row['Macro_Phase']), 0.0),
            'is_default': int(row['Is_Default']),
            'loss_amount': float(row['Loss_Amount']),
            'industry': industry,
            'factor_weights': {
                'G': round(w_G, 4),
                'I': round(w_I, 4),
                'R': round(w_R, 4),
            },
            'sigma_idio': round(sigma_idio, 4),
        }
        portfolio.append(loan)

    # Save
    with open(output_path, 'w') as f:
        json.dump(portfolio, f)

    print(f"\nSaved {len(portfolio)} loans to {output_path}")

    # Summary
    ead_arr = np.array([l['ead'] for l in portfolio])
    lgd_arr = np.array([l['lgd_base'] for l in portfolio])
    pd_arr = np.array([l['pd_base'] for l in portfolio])
    print(f"  Total exposure: ${ead_arr.sum():,.0f}")
    print(f"  Avg EAD: ${ead_arr.mean():,.0f}")
    print(f"  Avg LGD: {lgd_arr.mean():.3f}")
    print(f"  Avg PD: {pd_arr.mean():.4f}")
    print(f"  Historical default rate: {df['Is_Default'].mean():.4f}")

    return portfolio


if __name__ == '__main__':
    load_and_convert()