"""
Real-world data validation engine.

Uses two CSV datasets to validate the simulation model:
1. dynamic_data.csv  — Monthly portfolio snapshots for stress scenario validation
2. static_pool_data.csv — Vintage static pool data for PD term structure validation
"""
import csv
import os
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


def _parse_csv(path: str) -> List[Dict]:
    """Parse CSV file, handling quoted numbers and Chinese headers."""
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                k = k.strip().replace('\ufeff', '')
                v = v.strip().strip('"').replace(',', '') if v else '0'
                cleaned[k] = v
            rows.append(cleaned)
    return rows


def _parse_num(val) -> float:
    """Parse numeric value, returning 0.0 if invalid."""
    try:
        return float(str(val).replace(',', '').strip().strip('"'))
    except (ValueError, AttributeError):
        return 0.0


def _parse_ym(ym_str: str) -> int:
    """Parse YYYYMM to integer year-month."""
    s = str(ym_str).strip().strip('"')
    return int(s[:6]) if len(s) >= 6 else 0


def _ym_to_label(ym: int) -> str:
    """Convert YYYYMM to label like '2021-03'."""
    s = str(ym)
    return f"{s[:4]}-{s[4:6]}"


def _ym_diff(ym_end: int, ym_start: int) -> int:
    """Months between two YYYYMM dates."""
    y1, m1 = int(str(ym_start)[:4]), int(str(ym_start)[4:6])
    y2, m2 = int(str(ym_end)[:4]), int(str(ym_end)[4:6])
    return (y2 - y1) * 12 + (m2 - m1)


# Macro cycle phase mapping by month
# Based on the 8-year cycle: Expansion→Peak→Slowing→Recession→Trough→Early Recovery→Recovery→Normal
# Each phase is ~1 year
MACRO_PHASE_MAP = {
    # Year 1-2: Expansion/Peak (2021-01 to 2022-06 roughly)
    202101: 'Expansion', 202102: 'Expansion', 202103: 'Expansion',
    202104: 'Expansion', 202105: 'Expansion', 202106: 'Peak',
    202107: 'Peak', 202108: 'Peak', 202109: 'Peak',
    202110: 'Peak', 202111: 'Peak', 202112: 'Peak',
    # Year 3-4: Slowing/Recession (2022)
    202201: 'Slowing', 202202: 'Slowing', 202203: 'Slowing',
    202204: 'Slowing', 202205: 'Recession', 202206: 'Recession',
    202207: 'Recession', 202208: 'Recession', 202209: 'Recession',
    202210: 'Recession', 202211: 'Recession', 202212: 'Recession',
    # Year 5: Trough (2023-Q1)
    202301: 'Trough', 202302: 'Trough', 202303: 'Trough',
    # Year 6-7: Early Recovery/Recovery (2023-Q2 to 2024)
    202304: 'Early Recovery', 202305: 'Early Recovery', 202306: 'Early Recovery',
    202307: 'Early Recovery', 202308: 'Early Recovery', 202309: 'Early Recovery',
    202310: 'Recovery', 202311: 'Recovery', 202312: 'Recovery',
    202401: 'Recovery', 202402: 'Recovery', 202403: 'Recovery',
    202404: 'Recovery', 202405: 'Recovery', 202406: 'Recovery',
    # Year 8: Normal (2024-Q3 to 2025)
    202407: 'Normal', 202408: 'Normal', 202409: 'Normal',
    202410: 'Normal', 202411: 'Normal', 202412: 'Normal',
    202501: 'Normal', 202502: 'Normal', 202503: 'Normal',
    202504: 'Normal', 202505: 'Normal',
}

# Target LTR for each phase (from macro_cycle.py)
PHASE_TARGET_LTR = {
    'Expansion': 0.0080,
    'Peak': 0.0050,
    'Slowing': 0.0095,
    'Recession': 0.0210,
    'Trough': 0.0350,
    'Early Recovery': 0.0180,
    'Recovery': 0.0110,
    'Normal': 0.0075,
}


class ValidationEngine:
    """
    Validates simulation results against real-world data.

    Two types of validation:
    1. Stress scenario validation (dynamic_data)
       - Compute actual delinquency rates per month
       - Compare with simulated PD under corresponding macro conditions
    2. PD term structure validation (static_pool_data)
       - Compute vintage-level cumulative default rates
       - Compare with simulated PD migration patterns
    """

    def __init__(self, dynamic_path: str = None, static_path: str = None):
        self.dynamic_path = dynamic_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'dynamic_data.csv')
        self.static_path = static_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'static_pool_data.csv')
        self.dynamic_data = None
        self.static_data = None
        self.portfolio_data = None  # Will be set externally

    def load(self) -> bool:
        """Load both CSV files."""
        try:
            if os.path.exists(self.dynamic_path):
                self.dynamic_data = _parse_csv(self.dynamic_path)
                print(f"Loaded dynamic_data: {len(self.dynamic_data)} months")
            else:
                print(f"Warning: {self.dynamic_path} not found")

            if os.path.exists(self.static_path):
                self.static_data = _parse_csv(self.static_path)
                print(f"Loaded static_pool_data: {len(self.static_data)} rows")
            else:
                print(f"Warning: {self.static_path} not found")

            return self.dynamic_data is not None or self.static_data is not None
        except Exception as e:
            print(f"Validation data load error: {e}")
            return False

    # ============================================================
    # STRESS SCENARIO VALIDATION (dynamic_data)
    # ============================================================

    def compute_actual_delinquency_rates(self) -> List[Dict]:
        """
        Compute actual delinquency rates from dynamic_data.

        Calculates:
        - Total delinquency rate = (D1-30 + D31-60 + D61-90 + D91-120 + D120+) / 期初金额
        - 30+ delinquency rate (worse indicator) = (D31-60 + D61-90 + D91-120 + D120+) / 期初金额
        - 90+ delinquency rate (close to default) = (D91-120 + D120+) / 期初金额
        """
        if not self.dynamic_data:
            return []

        results = []
        for row in self.dynamic_data:
            ym = _parse_ym(row.get('报告期末', '0'))
            if ym == 0:
                continue

            init_amt = _parse_num(row.get('期初金额(万元)', 0))
            if init_amt <= 0:
                continue

            d1_30 = _parse_num(row.get('拖欠1-30天金额(万元)', 0))
            d31_60 = _parse_num(row.get('拖欠31-60天金额(万元)', 0))
            d61_90 = _parse_num(row.get('拖欠61-90天金额(万元)', 0))
            d91_120 = _parse_num(row.get('拖欠91-120天金额(万元)', 0))
            d120p = _parse_num(row.get('拖欠120天以上金额(万元)', 0))

            total_delinq = d1_30 + d31_60 + d61_90 + d91_120 + d120p
            delinq_30p = d31_60 + d61_90 + d91_120 + d120p
            delinq_90p = d91_120 + d120p

            phase = MACRO_PHASE_MAP.get(ym, 'Unknown')

            results.append({
                'year_month': ym,
                'label': _ym_to_label(ym),
                'phase': phase,
                'target_ltr': PHASE_TARGET_LTR.get(phase, None),
                'init_amount_wan': init_amt,
                'total_delinquency_rate': total_delinq / init_amt,
                'delinquency_30p_rate': delinq_30p / init_amt,
                'delinquency_90p_rate': delinq_90p / init_amt,
                'd1_30_rate': d1_30 / init_amt,
                'd31_60_rate': d31_60 / init_amt,
                'd61_90_rate': d61_90 / init_amt,
                'd91_120_rate': d91_120 / init_amt,
                'd120p_rate': d120p / init_amt,
            })

        return results

    def validate_stress_scenario(self, scenario_pd: float,
                                  scenario_label: str,
                                  actual_month: int = None) -> Dict:
        """
        Validate a simulated PD against actual data.

        Args:
            scenario_pd: Simulated PD for the scenario
            scenario_label: Scenario name (used to find matching months)
            actual_month: Optional specific month to compare

        Returns:
            Comparison dict with simulated vs actual metrics
        """
        actual_rates = self.compute_actual_delinquency_rates()

        if not actual_rates:
            return {'error': 'No actual data loaded'}

        # Find matching months
        if actual_month:
            matches = [r for r in actual_rates if r['year_month'] == actual_month]
            label = _ym_to_label(actual_month)
        else:
            # Find months matching the scenario's macro phase
            phase_map = {
                'Baseline': 'Expansion',
                'Mild Recession': 'Slowing',
                'Severe Recession': 'Recession',
                'Boom': 'Peak',
                'Housing Crisis': 'Recession',
                'Recession': 'Recession',
                'Trough': 'Trough',
                'Expansion': 'Expansion',
                'Peak': 'Peak',
                'Slowing': 'Slowing',
                'Early Recovery': 'Early Recovery',
                'Recovery': 'Recovery',
                'Normal': 'Normal',
            }
            phase = phase_map.get(scenario_label, 'Unknown')
            matches = [r for r in actual_rates if r['phase'] == phase]
            label = f"{phase} phase ({len(matches)} months)"

        if not matches:
            return {
                'scenario': scenario_label,
                'simulated_pd': scenario_pd,
                'actual_delinquency_rate': None,
                'comparison': 'No matching months found',
            }

        actual_mean = np.mean([m['total_delinquency_rate'] for m in matches])
        actual_30p = np.mean([m['delinquency_30p_rate'] for m in matches])
        actual_90p = np.mean([m['delinquency_90p_rate'] for m in matches])

        return {
            'scenario': scenario_label,
            'matching_period': label,
            'month_count': len(matches),
            'simulated_pd': scenario_pd,
            'simulated_pd_pct': scenario_pd * 100 if scenario_pd else None,
            'actual_delinquency_rate': actual_mean,
            'actual_delinquency_pct': actual_mean * 100,
            'actual_30p_delinquency': actual_30p,
            'actual_30p_delinquency_pct': actual_30p * 100,
            'actual_90p_delinquency': actual_90p,
            'actual_90p_delinquency_pct': actual_90p * 100,
            'ratio_sim_to_actual': (scenario_pd / actual_mean) if actual_mean > 0 else None,
            'model_accuracy': max(0, 1 - abs(scenario_pd - actual_mean) / max(actual_mean, 1e-10)),
            'target_ltr': matches[0].get('target_ltr') if matches else None,
        }

    # ============================================================
    # PD TERM STRUCTURE VALIDATION (static_pool_data)
    # ============================================================

    def compute_vintage_pd_curves(self) -> Dict:
        """
        Compute PD term structure curves from static pool data.

        For each vintage, computes cumulative default rate by month since origination.
        Default is proxied by 90+ days delinquency (D91-120 + D120+).
        """
        if not self.static_data:
            return {}

        # Group by vintage (静态池期末)
        vintages = {}
        for row in self.static_data:
            vintage = _parse_ym(row.get('静态池期末', '0'))
            if vintage == 0:
                continue
            if vintage not in vintages:
                vintages[vintage] = []
            vintages[vintage].append(row)

        curves = {}
        for vintage, rows in sorted(vintages.items()):
            # Sort by report date
            rows.sort(key=lambda r: _parse_ym(r.get('报告期末', '0')))

            points = []
            for row in rows:
                report_ym = _parse_ym(row.get('报告期末', '0'))
                if report_ym == 0 or report_ym < vintage:
                    continue

                # Month since origination
                months_on_book = _ym_diff(report_ym, vintage)
                init_amt = _parse_num(row.get('期初金额(万元)', 0))

                if init_amt <= 0:
                    continue

                # Calculate surviving balance and default proxies
                d91_120 = _parse_num(row.get('拖欠91-120天金额(万元)', 0))
                d120p = _parse_num(row.get('拖欠120天以上金额(万元)', 0))
                d61_90 = _parse_num(row.get('拖欠61-90天金额(万元)', 0))
                d31_60 = _parse_num(row.get('拖欠31-60天金额(万元)', 0))
                d1_30 = _parse_num(row.get('拖欠1-30天金额(万元)', 0))

                total_delinq = d1_30 + d31_60 + d61_90 + d91_120 + d120p
                default_proxy = d91_120 + d120p  # 90+ delinquency ≈ default

                points.append({
                    'month_on_book': months_on_book,
                    'init_amount_wan': init_amt,
                    'delinquency_rate': total_delinq / init_amt if init_amt > 0 else 0,
                    'default_rate_90p': default_proxy / init_amt if init_amt > 0 else 0,
                    'report_ym': report_ym,
                })

            if len(points) >= 3:
                curves[_ym_to_label(vintage)] = points

        return curves

    def compute_pd_term_structure(self) -> List[Dict]:
        """
        Compute average PD term structure across all vintages.

        Returns a curve showing average default rate by month on book (1-60 months).
        """
        curves = self.compute_vintage_pd_curves()
        if not curves:
            return []

        # Aggregate by month_on_book
        by_month = {}
        for vintage, points in curves.items():
            for p in points:
                mob = p['month_on_book']
                if mob < 0:
                    continue
                if mob not in by_month:
                    by_month[mob] = {'delinq_rates': [], 'default_rates': []}
                by_month[mob]['delinq_rates'].append(p['delinquency_rate'])
                by_month[mob]['default_rates'].append(p['default_rate_90p'])

        result = []
        for mob in sorted(by_month.keys()):
            data = by_month[mob]
            result.append({
                'month_on_book': mob,
                'avg_delinquency_rate': float(np.mean(data['delinq_rates'])),
                'avg_delinquency_pct': float(np.mean(data['delinq_rates'])) * 100,
                'avg_default_rate_90p': float(np.mean(data['default_rates'])),
                'avg_default_rate_90p_pct': float(np.mean(data['default_rates'])) * 100,
                'sample_count': len(data['default_rates']),
            })

        return result

    def get_vintage_summary(self) -> List[Dict]:
        """Get summary of all vintages for display."""
        curves = self.compute_vintage_pd_curves()
        summary = []
        for vintage, points in sorted(curves.items()):
            if points:
                max_mob = max(p['month_on_book'] for p in points)
                final_default = max(p['default_rate_90p'] for p in points) if points else 0
                summary.append({
                    'vintage': vintage,
                    'month_count': len(points),
                    'max_month_on_book': max_mob,
                    'final_default_rate_90p': final_default,
                    'final_default_rate_90p_pct': final_default * 100,
                })
        return summary

    def compare_simulated_vs_actual(self, simulation_result: Dict) -> Dict:
        """
        Full comparison: simulated metrics vs real-world data.

        Args:
            simulation_result: Dict from MonteCarloSimulator.simulate()

        Returns:
            Dict with validation metrics
        """
        pd_scenario = simulation_result.get('pd_scenario', 0)
        loss_rate = simulation_result.get('loss_rate', 0)
        mean_loss = simulation_result.get('mean_loss', 0)

        # Find the most stressful actual month for comparison
        actual_rates = self.compute_actual_delinquency_rates()
        if not actual_rates:
            return {'error': 'No actual data'}

        # Overall stats
        all_delinq = [r['total_delinquency_rate'] for r in actual_rates if r['total_delinquency_rate'] > 0]
        all_delinq_90p = [r['delinquency_90p_rate'] for r in actual_rates]

        return {
            'simulated': {
                'pd': pd_scenario,
                'pd_pct': pd_scenario * 100 if pd_scenario else 0,
                'loss_rate': loss_rate,
                'loss_rate_pct': loss_rate * 100 if loss_rate else 0,
                'mean_loss': mean_loss,
            },
            'actual': {
                'avg_total_delinquency': float(np.mean(all_delinq)) if all_delinq else 0,
                'avg_total_delinquency_pct': float(np.mean(all_delinq)) * 100 if all_delinq else 0,
                'max_total_delinquency': float(np.max(all_delinq)) if all_delinq else 0,
                'avg_delinquency_90p': float(np.mean(all_delinq_90p)),
                'max_delinquency_90p': float(np.max(all_delinq_90p)),
                'months_analyzed': len(all_delinq),
            },
            'analysis': {
                'pd_vs_actual': f"Sim PD {pd_scenario*100:.3f}% vs actual avg delinquency {float(np.mean(all_delinq))*100:.3f}%",
                'loss_rate_vs_delinquency_90p': f"Sim loss rate {loss_rate*100:.3f}% vs actual 90+ delinqu {float(np.mean(all_delinq_90p))*100:.3f}%",
            }
        }

    # ============================================================
    # TIME SERIES FOR FRONTEND
    # ============================================================

    def get_time_series(self) -> Dict:
        """Get complete time series data for frontend visualization."""
        return {
            'delinquency_rates': self.compute_actual_delinquency_rates(),
            'pd_term_structure': self.compute_pd_term_structure(),
            'vintage_summary': self.get_vintage_summary(),
        }