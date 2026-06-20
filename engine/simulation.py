"""Monte Carlo and Vasicek simulation engines for credit portfolio.

EL = PD × LGD × EAD  (fully decomposed, all components macro-driven)
"""
import numpy as np
from scipy.stats import norm
from typing import Dict, Optional, List

from .portfolio import portfolio_to_arrays
from .factors import macro_to_factors


class MonteCarloSimulator:
    """
    Multi-factor Monte Carlo simulation.
    
    Core model (Probit/Merton):
        A_i = w_G·F_G + w_I·F_I + w_R·F_R + σ_i·ε_i
        Default if A_i < B_i, where B_i = Φ⁻¹(PD_base_i)
    
    Conditional PD (explicit Probit form):
        PD_i(F) = Φ((B_i - w_i·F) / σ_i)
    
    Dynamic LGD:
        LGD_i(F_R) = LGD_base_i × max(0.5, min(1.5, 1.0 - 0.03 × F_R))
        (When housing factor R is negative → LGD increases)
    
    Expected Loss per loan:
        EL_i = PD_i(F) × LGD_i(F_R) × EAD_i
    """

    def __init__(self, portfolio_data: List[Dict],
                 n_simulations: int = 10000,
                 seed: Optional[int] = None):
        self.portfolio_data = portfolio_data
        self.n_simulations = n_simulations
        self.seed = seed
        self._load_arrays()

    def _load_arrays(self):
        """Convert portfolio to NumPy arrays for vectorized computation."""
        self._arrays = portfolio_to_arrays(self.portfolio_data)
        arr = self._arrays
        self._weights = np.column_stack([arr['w_G'], arr['w_I'], arr['w_R']]).astype(np.float64)
        self._B = arr['B'].astype(np.float64)
        self._sigma_idio = arr['sigma_idio'].astype(np.float64)
        self._ead = arr['ead'].astype(np.float64)
        self._lgd_base = arr['lgd'].astype(np.float64)
        self._pd_base = arr['pd_base'].astype(np.float64)

    @property
    def arrays(self):
        return self._arrays

    def compute_dynamic_pd(self, factor_means: np.ndarray) -> np.ndarray:
        """
        Compute conditional PD given factor means using Merton/Probit model.
        
        PD_i(F) = Φ((B_i - w_i·μ_F) / σ_i)
        
        This is a Probit model where:
        - B_i = Φ⁻¹(PD_base_i) is the intercept
        - w_i are the factor loadings (regression coefficients)
        - μ_F are the macro factor values
        - σ_i is the idiosyncratic risk weight
        
        When GDP is negative (μ_G < 0): w_G positive → -w_G·μ_G positive → numerator increases
        → conditional PD increases. This captures "经济下行时违约率跳升".
        """
        systematic_shift = (self._weights[:, 0] * factor_means[0] +
                           self._weights[:, 1] * factor_means[1] +
                           self._weights[:, 2] * factor_means[2])
        
        numerator = self._B - systematic_shift
        denominator = self._sigma_idio
        cond_pd = norm.cdf(numerator / denominator)
        return np.clip(cond_pd, 0.0, 1.0)

    def compute_dynamic_lgd(self, factor_means: np.ndarray) -> np.ndarray:
        """
        Compute dynamic LGD based on real estate factor.
        
        When housing prices fall (R factor negative), LGD increases
        because collateral recovery value drops.
        
        LGD_i = LGD_base_i × clamp(1.0 - 0.03 × F_R, 0.5, 1.5)
        
        Example:
        - F_R = 0 (baseline): LGD = LGD_base × 1.0 (no adjustment)
        - F_R = -1.5 (housing crisis): LGD = LGD_base × 1.045 (4.5% increase)
        - F_R = -2.5 (severe housing crash): LGD = LGD_base × 1.075 (7.5% increase)
        """
        r_factor = factor_means[2]  # Real estate factor
        lgd_multiplier = np.clip(1.0 - 0.03 * r_factor, 0.5, 1.5)
        return self._lgd_base * lgd_multiplier

    def simulate(self, factor_means: np.ndarray,
                 n_simulations: Optional[int] = None) -> Dict:
        """
        Run Monte Carlo simulation with factor-driven PD and LGD.
        
        Returns full EL decomposition: PD, LGD, EAD for each loan.
        """
        n_sim = n_simulations or self.n_simulations
        rng = np.random.default_rng(self.seed)
        arr = self.arrays
        n_loans = arr['n']

        # === Compute dynamic PD and LGD ===
        cond_pd = self.compute_dynamic_pd(factor_means)
        dyn_lgd = self.compute_dynamic_lgd(factor_means)

        # Expected loss per loan (analytical, no MC needed)
        el_per_loan = cond_pd * dyn_lgd * arr['ead']
        total_analytical_el = float(np.sum(el_per_loan))

        # Weighted average metrics
        total_exposure = float(np.sum(arr['ead']))
        wavg_pd = float(np.average(cond_pd, weights=arr['ead']))
        wavg_lgd = float(np.average(dyn_lgd, weights=arr['ead']))

        # === Monte Carlo simulation for distribution (VaR, ES) ===
        weights_f32 = self._weights.astype(np.float32)
        B_f32 = self._B.astype(np.float32)
        sigma_f32 = self._sigma_idio.astype(np.float32)
        ead_f32 = arr['ead'].astype(np.float32)
        lgd_f32 = dyn_lgd.astype(np.float32)
        factor_means_f32 = factor_means.astype(np.float32)

        chunk_size = min(2000, n_sim)
        all_losses = np.zeros(n_sim, dtype=np.float64)
        all_defaults = np.zeros(n_sim, dtype=np.float64)
        all_pd_per_loan = np.zeros((n_sim, n_loans), dtype=np.bool_) if n_sim <= 500 else None

        start = 0
        while start < n_sim:
            end = min(start + chunk_size, n_sim)
            actual_chunk = end - start

            F = rng.normal(loc=factor_means_f32, scale=1.0, size=(actual_chunk, 3)).astype(np.float32)
            systematic = F @ weights_f32.T
            eps = rng.normal(0, 1, size=(actual_chunk, n_loans)).astype(np.float32) * sigma_f32[np.newaxis, :]
            A = systematic + eps
            defaulted = A < B_f32[np.newaxis, :]

            # Loss using DYNAMIC LGD
            chunk_losses = np.sum(defaulted * (ead_f32 * lgd_f32)[np.newaxis, :], axis=1)
            all_losses[start:end] = chunk_losses
            all_defaults[start:end] = np.sum(defaulted, axis=1)

            if all_pd_per_loan is not None:
                all_pd_per_loan[start:end] = defaulted

            start = end

        losses = all_losses

        sorted_losses = np.sort(losses)
        n_sim_actual = len(sorted_losses)
        idx95 = int(np.ceil(0.95 * n_sim_actual)) - 1
        idx99 = int(np.ceil(0.99 * n_sim_actual)) - 1

        mc_mean_loss = float(np.mean(losses))

        return {
            'losses': losses,
            'mean_loss': mc_mean_loss,
            'std_loss': float(np.std(losses)),
            'var_95': float(sorted_losses[idx95]),
            'var_99': float(sorted_losses[idx99]),
            'es_95': float(np.mean(sorted_losses[idx95:])),
            'es_99': float(np.mean(sorted_losses[idx99:])),
            'total_exposure': total_exposure,
            'loss_rate': float(mc_mean_loss / total_exposure) if total_exposure > 0 else 0.0,
            'n_simulations': n_sim,
            'n_loans': n_loans,
            'n_defaults_mean': float(np.mean(all_defaults)),
            # -------- EL Decomposition --------
            'analytical_el': total_analytical_el,
            'pd_scenario': wavg_pd,              # EAD-weighted conditional PD
            'lgd_scenario': wavg_lgd,             # EAD-weighted dynamic LGD
            'pd_base': float(np.average(self._pd_base, weights=arr['ead'])),
            'lgd_base': float(np.average(self._lgd_base, weights=arr['ead'])),
        }

    def simulate_scenario(self, gdp_growth: float, unemployment: float,
                           house_price_change: float,
                           n_simulations: Optional[int] = None) -> Dict:
        """Simulate from macro scenario."""
        factor_means = macro_to_factors(gdp_growth, unemployment, house_price_change)
        return self.simulate(factor_means, n_simulations)

    @staticmethod
    def get_loss_histogram(losses: np.ndarray, n_bins: int = 50) -> Dict:
        """Compute histogram bins for charting."""
        hist, bin_edges = np.histogram(losses, bins=n_bins)
        return {
            'bins': bin_edges.tolist(),
            'counts': hist.tolist(),
            'bin_centers': ((bin_edges[:-1] + bin_edges[1:]) / 2).tolist(),
            'n_bins': n_bins,
        }


class VasicekSimulator:
    """Single-factor Vasicek model for quick analytical approximations.
    
    Vasicek is a special case of the multi-factor model where there is
    only one common factor Z with correlation ρ:
        A_i = √ρ·Z + √(1-ρ)·ε_i
    
    Conditional PD = Φ((Φ⁻¹(PD_base) - √ρ·Z) / √(1-ρ))
    """
    def __init__(self, portfolio_data: List[Dict]):
        self.portfolio_data = portfolio_data
        self._arrays = portfolio_to_arrays(portfolio_data)
        self._ead = self._arrays['ead']
        self._lgd_base = self._arrays['lgd']
        self._B = self._arrays['B']

    def simulate(self, rho: float = 0.2,
                 n_simulations: int = 10000,
                 factor_shift: float = 0.0,
                 seed: Optional[int] = None) -> Dict:
        rng = np.random.default_rng(seed)
        arr = self._arrays
        n_loans = arr['n']

        sqrt_rho = np.sqrt(rho)
        sqrt_one_minus_rho = np.sqrt(1.0 - rho)
        B = self._B
        ead = self._ead

        chunk_size = min(5000, n_simulations)
        losses_list = []
        defaults_list = []

        start = 0
        while start < n_simulations:
            end = min(start + chunk_size, n_simulations)
            actual = end - start

            Z = rng.normal(loc=factor_shift, scale=1.0, size=actual)
            eps = rng.normal(0, 1, size=(actual, n_loans))
            A = sqrt_rho * Z[:, np.newaxis] + sqrt_one_minus_rho * eps

            defaulted = A < B[np.newaxis, :]
            losses_list.append(np.sum(defaulted * (ead * self._lgd_base)[np.newaxis, :], axis=1))
            defaults_list.append(np.sum(defaulted, axis=1))
            start = end

        losses = np.concatenate(losses_list)
        total_defaults = np.concatenate(defaults_list)

        total_exposure = float(np.sum(ead))
        sorted_losses = np.sort(losses)
        n = len(sorted_losses)
        idx95 = int(np.ceil(0.95 * n)) - 1
        idx99 = int(np.ceil(0.99 * n)) - 1

        return {
            'losses': losses,
            'mean_loss': float(np.mean(losses)),
            'std_loss': float(np.std(losses)),
            'var_95': float(sorted_losses[idx95]),
            'var_99': float(sorted_losses[idx99]),
            'es_95': float(np.mean(sorted_losses[idx95:])),
            'es_99': float(np.mean(sorted_losses[idx99:])),
            'total_exposure': total_exposure,
            'loss_rate': float(np.mean(losses) / total_exposure) if total_exposure > 0 else 0.0,
            'n_simulations': n_simulations,
            'n_loans': n_loans,
            'n_defaults_mean': float(np.mean(total_defaults)),
        }

    def analytical_conditional_pd(self, Z: float, rho: float) -> float:
        """Conditional PD = Φ((Φ⁻¹(PD_base) - √ρ·Z) / √(1-ρ))."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            B = self._B
            numerator = B - np.sqrt(rho) * Z
            denominator = np.sqrt(1.0 - rho)
            cond_pd = norm.cdf(numerator / denominator)
        return float(np.mean(cond_pd))