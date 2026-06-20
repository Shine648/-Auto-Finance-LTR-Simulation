"""
8-Year Macro Economic Cycle Framework for Auto Finance.

Phases:
  Year 1: Expansion   - 稳步扩张期
  Year 2: Peak        - 繁荣见顶期
  Year 3: Slowing     - 增速放缓期
  Year 4: Recession   - 经济衰退期
  Year 5: Trough      - 深度谷底期
  Year 6: Early Rec.  - 复苏初期
  Year 7: Recovery    - 稳步复苏期
  Year 8: Normal      - 回归常态期

Each phase defines:
  - GDP growth, unemployment, house price change
  - Target LTR (Loss-to-Receivables Ratio)
  - Factor mean shifts for simulation
"""
import numpy as np

# Phase definition: (year, name_cn, gdp, unemployment, house_price_change, target_ltr)
PHASE_DATA = [
    (1, 'Expansion',     '稳步扩张期',  6.0, 4.2,  2.0, 0.0080),
    (2, 'Peak',          '繁荣见顶期',  6.5, 3.5,  3.5, 0.0050),
    (3, 'Slowing',       '增速放缓期',  5.0, 4.5,  0.5, 0.0095),
    (4, 'Recession',     '经济衰退期',  3.0, 6.0, -3.0, 0.0210),
    (5, 'Trough',        '深度谷底期',  1.5, 7.5, -7.0, 0.0350),
    (6, 'Early Recovery','复苏初期',    4.0, 5.5, -1.0, 0.0180),
    (7, 'Recovery',      '稳步复苏期',  5.2, 4.8,  1.5, 0.0110),
    (8, 'Normal',        '回归常态期',  5.8, 4.3,  2.5, 0.0075),
]

# Factor mean shifts for each phase (G, I, R)
# G = Growth factor (positive = good), I = Interest rate, R = Real estate
PHASE_FACTOR_MEANS = {
    1: np.array([0.6,  0.2,  0.3]),   # Expansion
    2: np.array([0.8,  0.5,  0.4]),   # Peak
    3: np.array([0.2,  0.1,  0.0]),   # Slowing
    4: np.array([-0.8, 0.3, -0.5]),   # Recession
    5: np.array([-1.5, 0.0, -1.2]),   # Trough (severe stress)
    6: np.array([-0.2, -0.2, -0.2]),  # Early Recovery
    7: np.array([0.3, -0.1,  0.1]),   # Recovery
    8: np.array([0.5,  0.0,  0.3]),   # Normal
}


def get_phase_info(year: int) -> dict:
    """Get phase info for a given year (1-8)."""
    for y, en, cn, gdp, unemp, hpc, ltr in PHASE_DATA:
        if y == year:
            return {
                'year': y,
                'phase_en': en,
                'phase_cn': cn,
                'gdp_growth': gdp,
                'unemployment': unemp,
                'house_price_change': hpc,
                'target_ltr': ltr,
                'factor_means': PHASE_FACTOR_MEANS[y].tolist(),
            }
    return None


def get_all_phases() -> list:
    """Get list of all phase info."""
    return [get_phase_info(y) for y in range(1, 9)]


def compute_ltr(total_loss: float, average_balance: float) -> float:
    """Compute Loss-to-Receivables Ratio.
    LTR = Total Annual Net Loss / Average Annual Credit Asset Balance
    """
    if average_balance <= 0:
        return 0.0
    return total_loss / average_balance


class MacroCycleModel:
    """Model that maps year/phases to factor means and scenario params."""

    def __init__(self):
        self.phases = get_all_phases()

    def get_factor_means(self, year: int) -> np.ndarray:
        """Get factor means for a given year (1-8)."""
        return PHASE_FACTOR_MEANS.get(year, np.zeros(3))

    def get_macro_params(self, year: int) -> dict:
        """Get GDP, unemployment, house price for a year."""
        info = get_phase_info(year)
        if info is None:
            return {'gdp_growth': 2.0, 'unemployment': 4.5, 'house_price_change': 0.0}
        return {
            'gdp_growth': info['gdp_growth'],
            'unemployment': info['unemployment'],
            'house_price_change': info['house_price_change'],
        }

    def get_target_ltr(self, year: int) -> float:
        """Get the target/reference LTR for a given year."""
        info = get_phase_info(year)
        return info['target_ltr'] if info else 0.01

    def pd_scaling_factor(self, year: int, base_pd: float) -> float:
        """
        Scale PD based on macro phase.
        Recession/Trough phases increase PD, Boom/Expansion decrease it.
        Returns a multiplier on the base PD.
        """
        factor_means = self.get_factor_means(year)
        g_factor = factor_means[0]  # Growth factor
        # Map G factor to PD multiplier via logistic function
        # G > 0 (good) → lower PD, G < 0 (bad) → higher PD
        # At G=0 → multiplier ≈ 1.0
        # At G=-1.5 (Trough) → multiplier ≈ 2.5-3.0
        # At G=0.8 (Peak) → multiplier ≈ 0.6-0.7
        multiplier = np.exp(-g_factor * 0.6)
        return float(np.clip(multiplier, 0.4, 3.5))

    def lgd_scaling_factor(self, year: int, vehicle_type: str) -> float:
        """
        Scale LGD based on macro phase and vehicle type.
        Used cars are more sensitive to economic downturns.
        """
        factor_means = self.get_factor_means(year)
        r_factor = factor_means[2]  # Real estate factor proxy

        # Base multiplier: worse economy → higher LGD
        base_mult = np.exp(-r_factor * 0.3)

        # Used cars have higher LGD sensitivity
        if vehicle_type == 'Used':
            base_mult *= 1.15

        return float(np.clip(base_mult, 0.8, 1.8))