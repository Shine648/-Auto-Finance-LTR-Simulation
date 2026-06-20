"""Loss distribution, VaR, and other risk metrics."""
import numpy as np
from typing import Dict, List, Optional


def compute_loss_distribution(losses: np.ndarray,
                              n_bins: int = 50) -> Dict:
    """Compute histogram of loss distribution."""
    hist, bin_edges = np.histogram(losses, bins=n_bins)
    return {
        'bins': bin_edges.tolist(),
        'counts': hist.tolist(),
        'bin_centers': ((bin_edges[:-1] + bin_edges[1:]) / 2).tolist(),
        'n_bins': n_bins,
    }


def compute_var_es(losses: np.ndarray,
                   alpha: float = 0.99) -> Dict:
    """Compute Value-at-Risk and Expected Shortfall."""
    sorted_losses = np.sort(losses)
    n = len(sorted_losses)
    var_idx = int(np.ceil(alpha * n)) - 1
    var = float(sorted_losses[var_idx])
    es = float(np.mean(sorted_losses[var_idx:]))
    return {
        'alpha': alpha,
        'var': var,
        'es': es,
    }


def compare_scenarios(scenario_results: Dict[str, Dict]) -> List[Dict]:
    """Compare metrics across multiple scenarios."""
    comparison = []
    for name, result in scenario_results.items():
        comparison.append({
            'scenario': name,
            'mean_loss': result['mean_loss'],
            'var_95': result['var_95'],
            'var_99': result['var_99'],
            'es_95': result['es_95'],
            'es_99': result['es_99'],
            'loss_rate': result['loss_rate'],
            'n_defaults_mean': result['n_defaults_mean'],
        })
    return comparison


def compute_gdp_sensitivity(gdp_values: List[float],
                             unemployment: float,
                             house_price_change: float,
                             simulator) -> List[Dict]:
    """Compute loss metrics across a range of GDP values."""
    results = []
    for gdp in gdp_values:
        result = simulator.simulate_scenario(
            gdp_growth=gdp,
            unemployment=unemployment,
            house_price_change=house_price_change,
            n_simulations=5000,
        )
        results.append({
            'gdp_growth': gdp,
            'mean_loss': result['mean_loss'],
            'var_99': result['var_99'],
            'loss_rate': result['loss_rate'],
        })
    return results