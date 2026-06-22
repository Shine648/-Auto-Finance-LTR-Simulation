"""Pydantic models for API request/response."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class ScenarioInput(BaseModel):
    """Macro-economic scenario input."""
    gdp_growth: float = Field(default=2.0, description="GDP growth rate in %")
    unemployment: float = Field(default=4.5, description="Unemployment rate in %")
    house_price_change: float = Field(default=0.0, description="House price change in %")
    n_simulations: int = Field(default=10000, ge=100, le=100000, description="Number of simulations")
    method: str = Field(default="monte_carlo", description="Simulation method: monte_carlo or vasicek")
    rho: Optional[float] = Field(default=None, description="Asset correlation for Vasicek model")
    observation_year: Optional[int] = Field(default=None, ge=1, le=8,
                                            description="Year in 8-year macro cycle (1-8)")


class ScenarioPreset(BaseModel):
    """Pre-defined scenario for quick comparison."""
    name: str
    label: str
    gdp_growth: float
    unemployment: float
    house_price_change: float


class LossHistogram(BaseModel):
    """Histogram bin data for charting."""
    bins: List[float]
    counts: List[int]
    bin_centers: List[float]


class SimulationResult(BaseModel):
    """Result from a single simulation run."""
    mean_loss: float
    std_loss: float
    var_95: float
    var_99: float
    es_95: float
    es_99: float
    total_exposure: float
    loss_rate: float
    n_simulations: int
    n_loans: int
    n_defaults_mean: float
    histogram: Optional[LossHistogram] = None
    factor_means: List[float]
    scenario_label: str
    # LTR (Loss-to-Receivables Ratio) specific fields
    ltr: Optional[float] = Field(default=None, description="Loss-to-Receivables Ratio")
    target_ltr: Optional[float] = Field(default=None, description="Target LTR for current cycle phase")
    observation_year: Optional[int] = Field(default=None, description="Year in macro cycle")
    phase_name_en: Optional[str] = Field(default=None, description="Cycle phase name (EN)")
    phase_name_cn: Optional[str] = Field(default=None, description="Cycle phase name (CN)")
    # EL = PD × LGD × EAD decomposition
    analytical_el: Optional[float] = Field(default=None, description="Analytical expected loss = PD × LGD × EAD")
    pd_scenario: Optional[float] = Field(default=None, description="EAD-weighted conditional PD for this scenario")
    lgd_scenario: Optional[float] = Field(default=None, description="EAD-weighted dynamic LGD for this scenario")
    pd_base: Optional[float] = Field(default=None, description="EAD-weighted base PD (rating-based)")
    lgd_base: Optional[float] = Field(default=None, description="EAD-weighted base LGD (collateral-based)")


class ScenarioComparison(BaseModel):
    """Comparison across multiple scenarios."""
    scenarios: List[str]
    metrics: List[Dict]


class MacroCyclePhase(BaseModel):
    """A single year in the 8-year macro cycle."""
    year: int
    phase_en: str
    phase_cn: str
    gdp_growth: float
    unemployment: float
    house_price_change: float
    target_ltr: float
    factor_means: List[float]


class MacroCycleResponse(BaseModel):
    """Full 8-year macro cycle definition."""
    phases: List[MacroCyclePhase]


class LTRProjection(BaseModel):
    """LTR projection for a year in the cycle."""
    year: int
    phase_en: str
    phase_cn: str
    simulated_ltr: float
    target_ltr: float
    mean_loss: float
    total_exposure: float


class MacroSensitivityPoint(BaseModel):
    """Single point on macro sensitivity curve."""
    gdp_growth: float
    mean_loss: float
    var_99: float
    loss_rate: float


class MacroSensitivityCurve(BaseModel):
    """Sensitivity of loss metrics to a macro variable."""
    variable: str
    points: List[MacroSensitivityPoint]


class ScenarioPresetsResponse(BaseModel):
    """List of available scenario presets."""
    presets: List[ScenarioPreset]


class HeatmapRequest(BaseModel):
    """Request for dual-stress sensitivity heatmap."""
    unemp_min: float = Field(default=3.0, description="Unemployment minimum (%)")
    unemp_max: float = Field(default=12.0, description="Unemployment maximum (%)")
    hp_min: float = Field(default=-20.0, description="House/used car price minimum (%)")
    hp_max: float = Field(default=10.0, description="House/used car price maximum (%)")
    grid_size: int = Field(default=20, ge=5, le=50, description="Grid points per dimension")
    gdp_growth: float = Field(default=2.0, description="Fixed GDP growth rate (%)")
    n_simulations: int = Field(default=2000, ge=100, le=20000, description="Simulations per point")


class HeatmapResponse(BaseModel):
    """Response from grid-search heatmap."""
    unemployment_range: List[float]
    hp_range: List[float]
    grid_size: int
    X: List[List[float]]
    Y: List[List[float]]
    loss_matrix: List[List[float]]
    var99_matrix: List[List[float]]
    loss_rate_matrix: List[List[float]]
    contours: List[Dict]
    safe_zone: List[List[bool]]
    capital_threshold_pct: float
    unit: str
    unit_bps: str
    current_unemployment: Optional[float] = None
    current_hp: Optional[float] = None
    current_loss_rate: Optional[float] = None


class PDFReportRequest(BaseModel):
    """Request for PDF report generation."""
    gdp_growth: float = Field(default=2.0, description="GDP growth rate in %")
    unemployment: float = Field(default=4.5, description="Unemployment rate in %")
    house_price_change: float = Field(default=0.0, description="House price change in %")
    n_simulations: int = Field(default=10000, ge=100, le=100000, description="Number of simulations")
    method: str = Field(default="monte_carlo", description="Simulation method")
    include_cycle: bool = Field(default=True, description="Include 8-year cycle projection")
    include_heatmap: bool = Field(default=False, description="Include heatmap section")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    portfolio_size: int
    version: str = "1.2.0"
