"""Factor model definition and macro-to-factor mapping."""
import numpy as np
from typing import Dict, List, Optional

# Factor names
FACTOR_NAMES = ['G', 'I', 'R']
# G = Economic Growth factor
# I = Interest Rate factor
# R = Real Estate factor


def macro_to_factors(gdp_growth: float = 0.0,
                     unemployment: float = 0.0,
                     house_price_change: float = 0.0) -> np.ndarray:
    """
    Map macro-economic variables to factor mean vector mu_F.

    Positive factor means = good economic conditions, negative = distressed.

    Mapping logic:
    - GDP below baseline 2.0% -> negative G factor (lower growth = worse)
    - Unemployment above baseline 4.5% -> negative G factor (more unemployed = worse)
    - House price decline -> directly negative R factor
    - Interest rates: higher growth pushes rates up, higher unemployment pushes rates down

    Args:
        gdp_growth: GDP growth rate in percent (e.g. 2.0 for 2% growth)
        unemployment: Unemployment rate in percent (e.g. 5.0 for 5%)
        house_price_change: House price change in percent (e.g. -5.0 for -5%)

    Returns:
        numpy array [mu_G, mu_I, mu_R] factor means
    """
    # Baseline: 2.0% GDP growth, 4.5% unemployment, 0% house price change
    mu_G = 0.0
    mu_I = 0.0
    mu_R = 0.0

    # == CALIBRATED FACTOR MAPPING (reduced sensitivity) ==
    # Calibrated so Recession (GDP=-2%, Unemp=9%, HPC=-10%) produces
    # factor means in range [-1.0, 0.5], giving PD ~2-4x base
    
    # GDP deviation from baseline (2.0%)
    # Calibrated: old 0.4 → 0.15 (factor range: -1.2 to +0.9 → -0.45 to +0.34)
    gdp_dev = gdp_growth - 2.0
    mu_G += gdp_dev * 0.15

    # Unemployment deviation from baseline (4.5%)
    # Higher unemployment = negative for economy
    # Calibrated: old 0.3 → 0.10
    unemp_dev = unemployment - 4.5
    mu_G -= unemp_dev * 0.10  # higher unemp -> lower G

    # Interest rate factor
    # Calibrated: old 0.2/0.15 → 0.08/0.05
    mu_I += gdp_dev * 0.08
    mu_I -= unemp_dev * 0.05

    # Real estate factor: directly from house price change
    # Calibrated: old 0.15 → 0.06
    # house_price_change=0 -> R=0, -10% -> R=-0.6, +10% -> R=+0.6
    mu_R += house_price_change * 0.06

    return np.array([mu_G, mu_I, mu_R])


class FactorModel:
    """
    Multi-factor model for credit portfolio.

    Each borrower i has asset return:
        A_i = w_G*F_G + w_I*F_I + w_R*F_R + sigma_i * epsilon_i

    where F ~ N(mu_F, I) and epsilon_i ~ N(0,1), independent.
    """

    def __init__(self, factor_means: Optional[np.ndarray] = None):
        self.factor_means = factor_means if factor_means is not None else np.zeros(3)

    def set_scenario(self, gdp_growth: float, unemployment: float,
                     house_price_change: float):
        """Set factor means from macro scenario."""
        self.factor_means = macro_to_factors(gdp_growth, unemployment,
                                             house_price_change)

    def set_factor_means(self, means: np.ndarray):
        """Directly set factor means."""
        self.factor_means = np.array(means)

    @property
    def scenario_label(self) -> str:
        """Get scenario label based on factor means."""
        g = self.factor_means[0]
        r = self.factor_means[2]
        if g < -1.0 and r < -1.0:
            return "Severe Recession"
        elif g < -0.5:
            return "Recession"
        elif g > 0.5 and r > 0.5:
            return "Boom"
        elif abs(g) < 0.3 and abs(r) < 0.3:
            return "Baseline"
        else:
            return "Mild Stress"

    def get_presets(self) -> Dict[str, np.ndarray]:
        """Get preset scenario factor means (calibrated)."""
        return {
            'Baseline': np.array([0.0, 0.0, 0.0]),
            'Mild Recession': np.array([-0.2, 0.1, -0.2]),
            'Severe Recession': np.array([-0.6, 0.2, -0.6]),
            'Boom': np.array([0.5, 0.3, 0.5]),
            'Housing Crisis': np.array([-0.1, -0.2, -0.9]),
        }
