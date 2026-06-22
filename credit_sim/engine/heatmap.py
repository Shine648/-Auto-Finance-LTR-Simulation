"""
Grid-search engine for dual-stress sensitivity heatmap.

Maps Unemployment (3%-12%) × Used Car Price Index (-20% to +10%)
to a 15×15 loss matrix, with contour lines marking capital adequacy thresholds.
"""
import numpy as np
from typing import Dict, List, Optional
from scipy.interpolate import griddata

from .factors import macro_to_factors
from .simulation import MonteCarloSimulator


class HeatmapEngine:
    """
    Grid-search engine for dual-stress sensitivity analysis.

    Generates a 2D loss matrix over [Unemployment × Used Car Price] space,
    computes contour lines for capital adequacy thresholds, and returns
    structured data for Plotly.js frontend visualization.
    """

    def __init__(self, portfolio_data: List[Dict],
                 n_simulations: int = 2000,
                 seed: int = 42):
        self.portfolio_data = portfolio_data
        self.n_simulations = n_simulations
        self.seed = seed
        self._sim = MonteCarloSimulator(portfolio_data, n_simulations=5000, seed=seed)

    def grid_search(self,
                    unemp_min: float = 3.0,
                    unemp_max: float = 12.0,
                    hp_min: float = -20.0,
                    hp_max: float = 10.0,
                    grid_size: int = 15,
                    gdp_growth: float = 2.0,
                    n_simulations: Optional[int] = None) -> Dict:
        """
        Perform grid search over unemployment × house price space.
        Uses synchronous execution (no parallelization) for Windows compatibility.

        Args:
            unemp_min/max: Unemployment range in %
            hp_min/max: House price / used car price change range in %
            grid_size: Number of grid points per dimension (total = grid_size²)
            gdp_growth: Fixed GDP growth rate (default baseline)

        Returns:
            Dict with matrices for Plotly heatmap + contour data
        """
        n_sim = n_simulations or self.n_simulations

        # Generate mesh grid
        unemp_vals = np.linspace(unemp_min, unemp_max, grid_size)
        hp_vals = np.linspace(hp_min, hp_max, grid_size)
        X, Y = np.meshgrid(unemp_vals, hp_vals)

        # Run synchronously (Windows multiprocessing cannot pickle MonteCarloSimulator)
        results = []
        total = grid_size * grid_size
        for i in range(grid_size):
            for j in range(grid_size):
                unemp = X[i, j]
                hp = Y[i, j]
                factor_means = macro_to_factors(gdp_growth=gdp_growth, unemployment=unemp, house_price_change=hp)
                try:
                    res = self._sim.simulate(factor_means, n_simulations=n_sim)
                    results.append({
                        'unemployment': unemp,
                        'house_price_change': hp,
                        'mean_loss': res['mean_loss'],
                        'var_99': res['var_99'],
                        'loss_rate': res['loss_rate'],
                        'total_exposure': res['total_exposure'],
                    })
                except Exception as e:
                    print(f"Grid point ({i},{j}) unemp={unemp:.1f} hp={hp:.1f} failed: {e}")
            print(f"  Heatmap progress: {i+1}/{grid_size} rows complete ({((i+1)*grid_size)}/{total} points)")

        # Map results back to grid
        loss_matrix = np.full((grid_size, grid_size), np.nan)
        var99_matrix = np.full((grid_size, grid_size), np.nan)
        loss_rate_matrix = np.full((grid_size, grid_size), np.nan)

        for r in results:
            ui = int(np.round((r['unemployment'] - unemp_min) / (unemp_max - unemp_min) * (grid_size - 1)))
            hj = int(np.round((r['house_price_change'] - hp_min) / (hp_max - hp_min) * (grid_size - 1)))
            ui = np.clip(ui, 0, grid_size - 1)
            hj = np.clip(hj, 0, grid_size - 1)
            loss_matrix[hj, ui] = r['mean_loss']
            var99_matrix[hj, ui] = r['var_99']
            loss_rate_matrix[hj, ui] = r['loss_rate']

        # Fill NaN with nearest neighbor interpolation
        valid_mask = ~np.isnan(loss_matrix)
        if not np.all(valid_mask):
            points_valid = np.column_stack((X[valid_mask], Y[valid_mask]))
            values_valid = loss_matrix[valid_mask]
            loss_matrix = griddata(points_valid, values_valid, (X, Y), method='nearest', fill_value=0)

        # Compute contour for capital adequacy threshold (8% loss rate)
        contour_levels = self._compute_contour(X, Y, loss_rate_matrix, levels_pct=[6.0, 8.0, 10.0])

        # Compute safe zone (loss_rate < capital_threshold)
        capital_threshold = 0.08  # 8% loss rate = capital depletion line
        safe_zone = loss_rate_matrix < capital_threshold

        return {
            'unemployment_range': [unemp_min, unemp_max],
            'hp_range': [hp_min, hp_max],
            'grid_size': grid_size,
            'X': X.tolist(),
            'Y': Y.tolist(),
            'loss_matrix': loss_matrix.tolist(),
            'var99_matrix': var99_matrix.tolist(),
            'loss_rate_matrix': (loss_rate_matrix * 100).tolist(),  # Convert to percentage
            'contours': contour_levels,
            'safe_zone': safe_zone.tolist(),
            'capital_threshold_pct': capital_threshold * 100,
            # Metadata for color bar
            'unit': '元',
            'unit_bps': 'bps',
        }

    def _compute_contour(self, X: np.ndarray, Y: np.ndarray,
                         Z: np.ndarray, levels_pct: List[float]) -> List[Dict]:
        """
        Compute contour lines for given loss rate levels.

        Returns list of {level, xs, ys} for Plotly contour overlay.
        Uses matplotlib's allsegs which works across all versions.
        """
        import matplotlib.pyplot as plt

        contours = []
        try:
            fig = plt.figure(figsize=(1, 1))
            ax = fig.add_subplot(111)
            cs = ax.contour(X, Y, Z * 100, levels=levels_pct)
            # allsegs is the most compatible API across matplotlib versions
            for level_idx, level in enumerate(cs.levels):
                segs = cs.allsegs[level_idx]
                for seg in segs:
                    if len(seg) > 2:
                        contours.append({
                            'level': float(level),
                            'xs': seg[:, 0].tolist(),
                            'ys': seg[:, 1].tolist(),
                        })
            plt.close(fig)
        except Exception as e:
            print(f"Contour computation warning: {e}")
            # Fallback: approximate contour using threshold
            for level in levels_pct:
                mask = Z * 100 >= level
                if np.any(mask):
                    contours.append({
                        'level': level,
                        'xs': X[mask][::5].tolist(),
                        'ys': Y[mask][::5].tolist(),
                    })
        return contours

    def point_simulation(self, unemployment: float,
                         house_price_change: float,
                         gdp_growth: float = 2.0,
                         n_simulations: Optional[int] = None) -> Dict:
        """Run a single simulation at a specific grid point (for double-click callback)."""
        n_sim = n_simulations or self.n_simulations
        factor_means = macro_to_factors(gdp_growth, unemployment, house_price_change)
        return self._sim.simulate(factor_means, n_simulations=n_sim)