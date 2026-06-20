# Auto Finance LTR Simulation | 汽车金融损失率模拟

**8-Year Macro Cycle Credit Portfolio Simulator**

A multi-factor Monte Carlo simulation engine for auto finance loss forecasting, featuring an 8-year macroeconomic cycle framework with LTR (Loss-to-Receivables Ratio) as the primary risk metric.

## Features

- **8-Year Macro Cycle** — Expansion → Peak → Slowing → Recession → Trough → Early Recovery → Recovery → Normal
- **Monte Carlo Simulation** — Multi-factor Vasicek-Merton model with 3 systematic risk factors (Growth, Interest Rate, Real Estate)
- **LTR Analytics** — Simulated vs Target LTR, deviation tracking, VaR 95%/99%
- **Custom Exposure** — User-configurable total portfolio exposure
- **Interactive Dashboard** — Dark theme ECharts UI with bilingual support (EN/中文)
- **Caching** — MD5-hash + joblib disk cache for instant repeat queries
- **Fast API** — FastAPI backend with parallel batch processing

## Quick Start

```bash
# 1. Install dependencies
pip install fastapi uvicorn numpy pandas scipy joblib

# 2. Generate sample portfolio (5,000 synthetic loans)
python data/generate_sample_portfolio.py

# 3. Copy portfolio to working directory
copy data\portfolio.json portfolio.json

# 4. Start server
python main.py

# 5. Open browser
open http://localhost:8000
```

Or simply double-click `start.bat`.

## Project Structure

```
credit_sim/
├── main.py                         # FastAPI server (port 8000)
├── models.py                       # Pydantic request/response schemas
├── start.bat                       # One-click launcher
├── requirements.txt                # Python dependencies
├── engine/
│   ├── __init__.py
│   ├── portfolio.py                # Portfolio I/O & NumPy conversion
│   ├── factors.py                  # 3-factor model + macro mapping
│   ├── simulation.py               # Monte Carlo & Vasicek engines
│   ├── metrics.py                  # VaR, ES, loss distribution
│   ├── cache.py                    # MD5 hash + joblib cache
│   └── macro_cycle.py              # 8-year cycle definition & scaling
├── frontend/
│   └── index.html                  # ECharts dashboard (standalone)
└── data/
    ├── load_real_portfolio.py      # CSV → JSON converter
    ├── generate_sample_portfolio.py# Demo synthetic portfolio generator
    └── portfolio.json              # (generated, gitignored)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/macro-cycle` | GET | 8-year cycle definition |
| `/simulate` | POST | Run single-year simulation |
| `/simulate/cycle` | POST | Run full 8-year cycle |
| `/simulate/presets` | POST | Compare preset scenarios |
| `/sensitivity/gdp` | GET | GDP-Loss sensitivity curve |
| `/cache/stats` | GET | Cache hit/miss statistics |

## 8-Year Macro Cycle

| Year | Phase | GDP | Unemployment | Target LTR |
|------|-------|-----|-------------|------------|
| 1 | Expansion | 6.0% | 4.2% | 0.80% |
| 2 | Peak | 6.5% | 3.5% | 0.50% |
| 3 | Slowing | 5.0% | 4.5% | 0.95% |
| 4 | **Recession** | **3.0%** | **6.0%** | **2.10%** |
| 5 | **Trough** | **1.5%** | **7.5%** | **3.50%** |
| 6 | Early Recovery | 4.0% | 5.5% | 1.80% |
| 7 | Recovery | 5.2% | 4.8% | 1.10% |
| 8 | Normal | 5.8% | 4.3% | 0.75% |

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, NumPy, SciPy, joblib
- **Frontend**: HTML5, ECharts 5, vanilla JS
- **Model**: Merton-Vasicek multi-factor framework
- **Cache**: MD5 key hashing, memory + disk (joblib)

## License

MIT