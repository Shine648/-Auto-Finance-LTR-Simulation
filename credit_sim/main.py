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
from engine.heatmap import HeatmapEngine
from engine.pdf_report import generate_report
from engine.validation import ValidationEngine
from models import (
    ScenarioInput, ScenarioPreset, SimulationResult,
    LossHistogram, ScenarioComparison,
    MacroCyclePhase, MacroCycleResponse, LTRProjection,
    MacroSensitivityCurve, MacroSensitivityPoint,
    ScenarioPresetsResponse, HealthResponse,
    HeatmapRequest, HeatmapResponse, PDFReportRequest,
    ValidationResult, PDCurvePoint, VintageSummary, ValidationTimeSeries,
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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')
FRONTEND_FILE = os.path.join(FRONTEND_DIR, 'index.html')
CLOUDFLARE_DIR = os.path.join(BASE_DIR, 'cloudflare-pages')
TUNNEL_CONFIG_FILE = os.path.join(CLOUDFLARE_DIR, 'index.html')

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

@app.get("/tunnel-config")
async def serve_tunnel_config():
    """Serve the Cloudflare Pages Tunnel Configuration UI."""
    if os.path.exists(TUNNEL_CONFIG_FILE):
        resp = FileResponse(TUNNEL_CONFIG_FILE)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
    return {"error": "tunnel config UI not found. See cloudflare-pages/ directory."}

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

@app.post("/simulate/heatmap", response_model=HeatmapResponse)
def simulate_heatmap(req: HeatmapRequest):
    """Run grid-search heatmap for dual-stress sensitivity (Unemployment × Asset Price)."""
    engine = HeatmapEngine(portfolio_data, n_simulations=req.n_simulations)
    result = engine.grid_search(
        unemp_min=req.unemp_min, unemp_max=req.unemp_max,
        hp_min=req.hp_min, hp_max=req.hp_max,
        grid_size=req.grid_size, gdp_growth=req.gdp_growth,
        n_simulations=req.n_simulations,
    )

    # Get current scenario position from current sliders
    # Default to baseline if not specified
    current_unemp = (req.unemp_min + req.unemp_max) / 2
    current_hp = (req.hp_min + req.hp_max) / 2
    current_loss_rate = 0.0

    result['current_unemployment'] = current_unemp
    result['current_hp'] = current_hp
    result['current_loss_rate'] = current_loss_rate

    return result


@app.post("/report/pdf")
def report_pdf(req: PDFReportRequest):
    """Generate professional PDF report for current scenario."""
    from fastapi.responses import StreamingResponse
    import io
    import traceback

    try:
        # Run simulation for current scenario
        scenario = ScenarioInput(
            gdp_growth=req.gdp_growth, unemployment=req.unemployment,
            house_price_change=req.house_price_change,
            n_simulations=req.n_simulations, method=req.method,
        )
        raw_result = _run_cached(scenario)
        print(f"PDF: Simulation done, mean_loss={raw_result['mean_loss']:.2f}")

        # Get cycle projections if requested
        cycle_data = None
        if req.include_cycle:
            cycle_projections = []
            for yr in range(1, 9):
                sc = ScenarioInput(
                    gdp_growth=2.0, unemployment=4.5, house_price_change=0.0,
                    n_simulations=min(req.n_simulations, 5000),
                    method=req.method, observation_year=yr)
                res = _run_cached(sc)
                phase = get_phase_info(yr)
                total_exp = res['total_exposure']
                ltr_val = compute_ltr(res['mean_loss'], total_exp)
                cycle_projections.append({
                    'year': yr,
                    'phase_en': phase['phase_en'],
                    'phase_cn': phase['phase_cn'],
                    'simulated_ltr': ltr_val,
                    'target_ltr': phase['target_ltr'],
                    'mean_loss': res['mean_loss'],
                    'total_exposure': total_exp,
                })
            cycle_data = cycle_projections
            print(f"PDF: Cycle data generated ({len(cycle_data)} years)")

        # Build histogram data for charts
        hist = compute_loss_distribution(raw_result['losses'], n_bins=50)
        sim_result_dict = {**raw_result, 'histogram': hist}

        # Generate PDF
        scenario_params = {
            'gdp_growth': req.gdp_growth,
            'unemployment': req.unemployment,
            'house_price_change': req.house_price_change,
            'n_simulations': req.n_simulations,
            'method': req.method,
        }

        print("PDF: Generating report...")
        pdf_bytes = generate_report(
            scenario_params=scenario_params,
            simulation_result=sim_result_dict,
            cycle_projections=cycle_data,
            heatmap_data=None,
        )
        print(f"PDF: Report generated, size={len(pdf_bytes) if pdf_bytes else 0} bytes")

        if pdf_bytes is None or len(pdf_bytes) < 100:
            raise HTTPException(status_code=500, detail="PDF generation returned empty result")

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="LTR_Report_{req.gdp_growth:.0f}p_{req.unemployment:.0f}u_{req.house_price_change:.0f}h.pdf"',
                'Cache-Control': 'no-cache',
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"PDF generation error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


# ---- Validation Endpoints (real-world data comparison) ----
_validation_engine = None

def get_validator() -> ValidationEngine:
    global _validation_engine
    if _validation_engine is None:
        _validation_engine = ValidationEngine()
        _validation_engine.load()
    return _validation_engine


@app.get("/validate/scenarios", response_model=List[ValidationResult])
async def validate_all_presets(n_simulations: int = 5000):
    """Validate all preset scenarios against real-world data."""
    validator = get_validator()
    if not validator.dynamic_data:
        raise HTTPException(status_code=404, detail="dynamic_data.csv not loaded")

    results = []
    for preset in PRESETS:
        sc = ScenarioInput(
            gdp_growth=preset.gdp_growth, unemployment=preset.unemployment,
            house_price_change=preset.house_price_change,
            n_simulations=n_simulations, method='monte_carlo')
        raw = _run_cached(sc)
        pd_val = raw.get('pd_scenario', 0)
        result = validator.validate_stress_scenario(pd_val, preset.label)
        results.append(ValidationResult(**result))
    return results


@app.get("/validate/current", response_model=ValidationResult)
async def validate_current(gdp_growth: float = 2.0, unemployment: float = 4.5,
                           house_price_change: float = 0.0, n_simulations: int = 5000):
    """Validate current simulation against real-world data."""
    validator = get_validator()
    if not validator.dynamic_data:
        raise HTTPException(status_code=404, detail="dynamic_data.csv not loaded")

    sc = ScenarioInput(
        gdp_growth=gdp_growth, unemployment=unemployment,
        house_price_change=house_price_change,
        n_simulations=n_simulations, method='monte_carlo')
    raw = _run_cached(sc)
    pd_val = raw.get('pd_scenario', 0)

    # Determine scenario label
    fm = macro_to_factors(gdp_growth, unemployment, house_price_change)
    _factor_model.set_factor_means(fm)
    label = _factor_model.scenario_label

    result = validator.validate_stress_scenario(pd_val, label)
    return ValidationResult(**result)


@app.get("/validate/timeseries", response_model=ValidationTimeSeries)
async def get_validation_timeseries():
    """Get complete real-world time series for frontend visualization."""
    validator = get_validator()
    if not validator.dynamic_data:
        raise HTTPException(status_code=404, detail="dynamic_data.csv not loaded")

    ts = validator.get_time_series()
    return ValidationTimeSeries(
        delinquency_rates=ts['delinquency_rates'],
        pd_term_structure=[PDCurvePoint(**p) for p in ts['pd_term_structure']],
        vintage_summary=[VintageSummary(**v) for v in ts['vintage_summary']],
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
