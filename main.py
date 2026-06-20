"""
FastAPI backend — 8-Year Macro Cycle Credit Portfolio Simulation.
"""
import os
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List
from concurrent.futures import ProcessPoolExecutor, as_completed

from engine.portfolio import load_portfolio, generate_portfolio
from engine.factors import macro_to_factors, FactorModel
from engine.simulation import MonteCarloSimulator, VasicekSimulator
from engine.metrics import compute_loss_distribution
from engine.cache import SimulationCache
from engine.macro_cycle import MacroCycleModel, get_phase_info, get_all_phases, compute_ltr
from models import (
    ScenarioInput, ScenarioPreset, SimulationResult,
    LossHistogram, ScenarioComparison,
    MacroCyclePhase, MacroCycleResponse, LTRProjection,
    MacroSensitivityCurve, MacroSensitivityPoint,
    ScenarioPresetsResponse, HealthResponse,
)

app = FastAPI(title="Credit Portfolio Simulation API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# Load portfolio
PORTFOLIO_PATH = 'data/portfolio.json'
if os.path.exists(PORTFOLIO_PATH):
    portfolio_data = load_portfolio(PORTFOLIO_PATH)
    print(f"Loaded {len(portfolio_data)} loans")
else:
    print(f"Generating portfolio...")
    portfolio_data = generate_portfolio(40000)
    from engine.portfolio import save_portfolio
    save_portfolio(portfolio_data, PORTFOLIO_PATH)

_simulator_mc = None
_simulator_vasicek = None
_cache = SimulationCache(max_memory=64, use_disk=True)
_factor_model = FactorModel()
_macro_cycle = MacroCycleModel()

PRESETS = [
    ScenarioPreset(name="baseline", label="Baseline", gdp_growth=2.0, unemployment=4.5, house_price_change=0.0),
    ScenarioPreset(name="mild_recession", label="Mild Recession", gdp_growth=0.5, unemployment=6.0, house_price_change=-3.0),
    ScenarioPreset(name="severe_recession", label="Severe Recession", gdp_growth=-2.0, unemployment=9.0, house_price_change=-10.0),
    ScenarioPreset(name="boom", label="Boom", gdp_growth=4.0, unemployment=3.0, house_price_change=8.0),
    ScenarioPreset(name="housing_crisis", label="Housing Crisis", gdp_growth=1.0, unemployment=7.0, house_price_change=-15.0),
]

def get_mc() -> MonteCarloSimulator:
    global _simulator_mc
    if _simulator_mc is None:
        _simulator_mc = MonteCarloSimulator(portfolio_data, n_simulations=10000, seed=42)
    return _simulator_mc

def get_vasicek() -> VasicekSimulator:
    global _simulator_vasicek
    if _simulator_vasicek is None:
        _simulator_vasicek = VasicekSimulator(portfolio_data)
    return _simulator_vasicek

def _run_simulation(scenario: ScenarioInput) -> dict:
    gdp = scenario.gdp_growth
    unemp = scenario.unemployment
    hpc = scenario.house_price_change
    year = scenario.observation_year
    if year is not None:
        phase = get_phase_info(year)
        if phase:
            gdp = phase['gdp_growth']
            unemp = phase['unemployment']
            hpc = phase['house_price_change']
    factor_means = macro_to_factors(gdp, unemp, hpc)
    if scenario.method == 'vasicek':
        rho = scenario.rho if scenario.rho is not None else 0.2
        sim = get_vasicek()
        shift = float(factor_means[0])
        return sim.simulate(rho=rho, n_simulations=scenario.n_simulations, factor_shift=shift)
    else:
        sim = get_mc()
        return sim.simulate(factor_means, n_simulations=scenario.n_simulations)

def _cache_key(scenario: ScenarioInput) -> str:
    extra = {}
    if scenario.method == 'vasicek':
        extra['rho'] = scenario.rho if scenario.rho is not None else 0.2
    if scenario.observation_year:
        extra['year'] = scenario.observation_year
    return _cache.get_cache_key_for_scenario(
        method=scenario.method, gdp=scenario.gdp_growth,
        unemp=scenario.unemployment, house=scenario.house_price_change,
        n_sim=scenario.n_simulations, **extra)

def _run_cached(scenario: ScenarioInput) -> dict:
    key = _cache_key(scenario)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    result = _run_simulation(scenario)
    _cache.set(key, result)
    return result

def _build_result(scenario: ScenarioInput, raw: dict) -> SimulationResult:
    gdp = scenario.gdp_growth
    unemp = scenario.unemployment
    hpc = scenario.house_price_change
    year = scenario.observation_year
    phase_info = None
    if year is not None:
        phase_info = get_phase_info(year)
        if phase_info:
            gdp = phase_info['gdp_growth']
            unemp = phase_info['unemployment']
            hpc = phase_info['house_price_change']
    factor_means = macro_to_factors(gdp, unemp, hpc)
    _factor_model.set_factor_means(factor_means)
    hist = compute_loss_distribution(raw['losses'], n_bins=50)
    total_exp = raw['total_exposure']
    ltr_value = compute_ltr(raw['mean_loss'], total_exp)
    target_ltr = phase_info['target_ltr'] if phase_info else None
    return SimulationResult(
        mean_loss=raw['mean_loss'], std_loss=raw['std_loss'],
        var_95=raw['var_95'], var_99=raw['var_99'],
        es_95=raw['es_95'], es_99=raw['es_99'],
        total_exposure=total_exp, loss_rate=raw['loss_rate'],
        n_simulations=raw['n_simulations'], n_loans=raw['n_loans'],
        n_defaults_mean=raw['n_defaults_mean'],
        histogram=LossHistogram(**hist),
        factor_means=factor_means.tolist(), scenario_label=_factor_model.scenario_label,
        ltr=ltr_value, target_ltr=target_ltr, observation_year=year,
        phase_name_en=phase_info['phase_en'] if phase_info else None,
        phase_name_cn=phase_info['phase_cn'] if phase_info else None,
        analytical_el=raw.get('analytical_el'),
        pd_scenario=raw.get('pd_scenario'), lgd_scenario=raw.get('lgd_scenario'),
        pd_base=raw.get('pd_base'), lgd_base=raw.get('lgd_base'),
    )

# ---- Frontend (Define BEFORE static mount) ----
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
FRONTEND_FILE = os.path.join(FRONTEND_DIR, 'index.html')

@app.get("/")
async def serve_root():
    """Serve the main page (cache-cleared, fresh start)."""
    dashboard_path = os.path.join(FRONTEND_DIR, 'final.html')
    if not os.path.exists(dashboard_path):
        return {"error": "final.html not found"}
    resp = FileResponse(dashboard_path)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend")

# ---- API Endpoints ----
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", portfolio_size=len(portfolio_data), version="1.2.0")

@app.get("/presets", response_model=ScenarioPresetsResponse)
def get_presets():
    return ScenarioPresetsResponse(presets=PRESETS)

@app.get("/cache/stats")
def cache_stats():
    return _cache.stats

@app.get("/macro-cycle", response_model=MacroCycleResponse)
def get_macro_cycle():
    phases = [MacroCyclePhase(**p) for p in get_all_phases()]
    return MacroCycleResponse(phases=phases)

@app.post("/simulate", response_model=SimulationResult)
def simulate(scenario: ScenarioInput):
    if scenario.n_simulations < 100 or scenario.n_simulations > 100000:
        raise HTTPException(status_code=400, detail="n_simulations 100-100000")
    if scenario.method not in ('monte_carlo', 'vasicek'):
        raise HTTPException(status_code=400, detail="method: monte_carlo or vasicek")
    result = _run_cached(scenario)
    return _build_result(scenario, result)

@app.post("/simulate/cycle", response_model=List[LTRProjection])
def simulate_full_cycle(n_simulations: int = 5000, method: str = 'monte_carlo'):
    projections = []
    for year in range(1, 9):
        sc = ScenarioInput(
            gdp_growth=2.0, unemployment=4.5, house_price_change=0.0,
            n_simulations=n_simulations, method=method, observation_year=year)
        result = _run_cached(sc)
        phase = get_phase_info(year)
        total_exp = result['total_exposure']
        ltr_val = compute_ltr(result['mean_loss'], total_exp)
        projections.append(LTRProjection(
            year=year, phase_en=phase['phase_en'], phase_cn=phase['phase_cn'],
            simulated_ltr=ltr_val, target_ltr=phase['target_ltr'],
            mean_loss=result['mean_loss'], total_exposure=total_exp))
    return projections

@app.post("/simulate/batch", response_model=ScenarioComparison)
def simulate_batch(scenarios: List[ScenarioInput]):
    results = {}
    with ProcessPoolExecutor(max_workers=min(os.cpu_count() or 4, len(scenarios))) as executor:
        future_map = {executor.submit(_run_simulation, sc): sc for sc in scenarios}
        for future in as_completed(future_map):
            sc = future_map[future]
            try:
                res = future.result()
                fm = macro_to_factors(sc.gdp_growth, sc.unemployment, sc.house_price_change)
                _factor_model.set_factor_means(fm)
                results[_factor_model.scenario_label] = res
            except Exception as e:
                print(f"Scenario failed: {e}")
    from engine.metrics import compare_scenarios
    return ScenarioComparison(scenarios=list(results.keys()), metrics=compare_scenarios(results))

@app.post("/simulate/presets", response_model=ScenarioComparison)
def simulate_presets(n_simulations: int = 10000, method: str = 'monte_carlo'):
    scenarios = [ScenarioInput(
        gdp_growth=p.gdp_growth, unemployment=p.unemployment,
        house_price_change=p.house_price_change,
        n_simulations=n_simulations, method=method) for p in PRESETS]
    return simulate_batch(scenarios)

@app.get("/sensitivity/gdp", response_model=MacroSensitivityCurve)
def gdp_sensitivity(gdp_min: float = -4.0, gdp_max: float = 6.0, gdp_steps: int = 11,
                    unemployment: float = 4.5, house_price_change: float = 0.0,
                    n_simulations: int = 5000, method: str = 'monte_carlo'):
    gdp_values = np.linspace(gdp_min, gdp_max, int(gdp_steps)).tolist()
    points = []
    for gdp in gdp_values:
        sc = ScenarioInput(gdp_growth=gdp, unemployment=unemployment,
                           house_price_change=house_price_change,
                           n_simulations=n_simulations, method=method)
        res = _run_cached(sc)
        points.append(MacroSensitivityPoint(
            gdp_growth=gdp, mean_loss=res['mean_loss'],
            var_99=res['var_99'], loss_rate=res['loss_rate']))
    return MacroSensitivityCurve(variable="gdp_growth", points=points)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)