"""
PDF Report Generator for Auto Finance LTR Simulation.

Uses ReportLab to generate professional-grade PDF reports with:
- Cover page with parameter snapshot and timestamp
- Key metrics summary table
- Loss distribution chart (matplotlib → PNG embed)
- 8-year cycle LTR chart
- Model limitations and disclaimer page (regulatory compliance)
"""
import os
import io
import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

# Color palette matching the dark theme
C_PRIMARY = HexColor('#38bdf8')
C_SECONDARY = HexColor('#0284c7')
C_DARK = HexColor('#0f1724')
C_CARD = HexColor('#121b2d')
C_TEXT = HexColor('#e2e8f0')
C_TEXT2 = HexColor('#8ba3c0')
C_ACCENT_GREEN = HexColor('#22c55e')
C_ACCENT_ORANGE = HexColor('#f59e0b')
C_ACCENT_RED = HexColor('#ef4444')

# ReportLab style overrides
from reportlab.lib import fonts

# Register custom styles
styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    'ReportTitle', parent=styles['Title'],
    fontSize=24, leading=30, textColor=C_PRIMARY,
    spaceAfter=6, alignment=TA_CENTER,
)

SUBTITLE_STYLE = ParagraphStyle(
    'ReportSubtitle', parent=styles['Normal'],
    fontSize=14, leading=18, textColor=C_TEXT2,
    spaceAfter=20, alignment=TA_CENTER,
)

H1_STYLE = ParagraphStyle(
    'H1', parent=styles['Heading1'],
    fontSize=16, leading=20, textColor=C_PRIMARY,
    spaceBefore=12, spaceAfter=8,
    borderWidth=0, borderColor=C_PRIMARY, borderPadding=4,
)

H2_STYLE = ParagraphStyle(
    'H2', parent=styles['Heading2'],
    fontSize=13, leading=16, textColor=C_TEXT,
    spaceBefore=8, spaceAfter=6,
)

BODY_STYLE = ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontSize=10, leading=14, textColor=HexColor('#1e293b'),
    spaceAfter=6,
)

SMALL_STYLE = ParagraphStyle(
    'Small', parent=styles['Normal'],
    fontSize=8, leading=10, textColor=HexColor('#64748b'),
    spaceAfter=4,
)

DISCLAIMER_STYLE = ParagraphStyle(
    'Disclaimer', parent=styles['Normal'],
    fontSize=8, leading=11, textColor=HexColor('#475569'),
    spaceAfter=4, alignment=TA_JUSTIFY,
    borderWidth=1, borderColor=HexColor('#cbd5e1'), borderPadding=8,
    backColor=HexColor('#f8fafc'),
)

TABLE_HEADER_STYLE = ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontSize=9, leading=11, textColor=white,
    alignment=TA_CENTER,
)

TABLE_CELL_STYLE = ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontSize=9, leading=11, textColor=HexColor('#1e293b'),
    alignment=TA_CENTER,
)

TABLE_CELL_LEFT = ParagraphStyle(
    'TableCellLeft', parent=styles['Normal'],
    fontSize=9, leading=11, textColor=HexColor('#1e293b'),
    alignment=TA_LEFT,
)

FOOTER_STYLE = ParagraphStyle(
    'Footer', parent=styles['Normal'],
    fontSize=7, leading=9, textColor=HexColor('#94a3b8'),
    alignment=TA_CENTER,
)


def _format_money(v: float) -> str:
    """Format monetary value with appropriate unit."""
    if v is None or v == 0:
        return '—'
    if v >= 1e9:
        return f'¥{v/1e9:.2f}B'
    if v >= 1e6:
        return f'¥{v/1e6:.2f}M'
    if v >= 1e4:
        return f'¥{v/1e4:.1f}万'
    return f'¥{v:.2f}'


def _format_pct(v: float) -> str:
    """Format as percentage."""
    if v is None:
        return '—'
    return f'{v*100:.3f}%'


def _format_pct_raw(v: float) -> str:
    """Format already-percentage value."""
    if v is None:
        return '—'
    return f'{v:.3f}%'


def generate_report(
    scenario_params: Dict[str, Any],
    simulation_result: Dict[str, Any],
    cycle_projections: Optional[List[Dict]] = None,
    heatmap_data: Optional[Dict] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Generate a comprehensive PDF report.

    Args:
        scenario_params: Input parameters (gdp_growth, unemployment, etc.)
        simulation_result: Single simulation result dict
        cycle_projections: Optional 8-year cycle data
        heatmap_data: Optional heatmap grid data
        output_path: If provided, save to file path

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()

    # Determine output destination
    if output_path:
        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=15*mm, bottomMargin=20*mm,
            title='Auto Finance LTR Simulation Report',
            author='LTR Simulation System v1.2',
        )
    else:
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=15*mm, bottomMargin=20*mm,
            title='Auto Finance LTR Simulation Report',
            author='LTR Simulation System v1.2',
        )

    # Build story
    story = []
    now = datetime.datetime.now()

    # ============================
    # COVER PAGE
    # ============================
    story.append(Spacer(1, 60*mm))
    story.append(HRFlowable(width='80%', thickness=2, color=C_PRIMARY, spaceAfter=10))
    story.append(Paragraph('Auto Finance LTR Simulation', TITLE_STYLE))
    story.append(Paragraph('Loss-to-Receivables Ratio Analysis Report', SUBTITLE_STYLE))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(
        f'Report Generated: {now.strftime("%Y-%m-%d %H:%M:%S")}',
        ParagraphStyle('CoverDate', parent=BODY_STYLE, fontSize=11, alignment=TA_CENTER, textColor=HexColor('#475569'))
    ))
    story.append(Paragraph(
        f'Report Version: 1.2.0 | Simulation Engine: Multi-Factor Monte Carlo',
        ParagraphStyle('CoverVersion', parent=BODY_STYLE, fontSize=9, alignment=TA_CENTER, textColor=HexColor('#64748b'))
    ))
    story.append(Spacer(1, 15*mm))

    # Parameter snapshot table on cover
    cover_data = [
        ['Parameter', 'Value', 'Unit'],
        ['GDP Growth', f'{scenario_params.get("gdp_growth", 2.0):+.1f}', '%'],
        ['Unemployment', f'{scenario_params.get("unemployment", 4.5):.1f}', '%'],
        ['House Price Change', f'{scenario_params.get("house_price_change", 0.0):+.1f}', '%'],
        ['Simulation Method', scenario_params.get('method', 'monte_carlo'), '—'],
        ['Simulations', f'{scenario_params.get("n_simulations", 10000):,}', 'runs'],
    ]
    cover_table = Table(cover_data, colWidths=[90*mm, 60*mm, 30*mm])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_SECONDARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph(
        'CONFIDENTIAL — For Internal Use Only',
        ParagraphStyle('Confidential', parent=BODY_STYLE, fontSize=9, alignment=TA_CENTER, textColor=HexColor('#94a3b8'))
    ))
    story.append(PageBreak())

    # ============================
    # SECTION 1: KEY METRICS SUMMARY
    # ============================
    story.append(Paragraph('1. Key Risk Metrics', H1_STYLE))
    story.append(HRFlowable(width='100%', thickness=1, color=C_PRIMARY, spaceAfter=8))
    story.append(Paragraph(
        'Summary of simulated loss metrics under the specified macroeconomic scenario. '
        'All values are derived from the multi-factor Merton/Probit Monte Carlo simulation with 10,000 iterations.',
        BODY_STYLE
    ))
    story.append(Spacer(1, 6*mm))

    metrics_data = [
        ['Metric', 'Value', 'Description'],
        ['Expected Loss (Mean)', _format_money(simulation_result.get('mean_loss', 0)),
         'Probability-weighted average portfolio loss'],
        ['Std Deviation', _format_money(simulation_result.get('std_loss', 0)),
         'Standard deviation of loss distribution'],
        ['VaR 95%', _format_money(simulation_result.get('var_95', 0)),
         'Loss not exceeded with 95% confidence'],
        ['VaR 99%', _format_money(simulation_result.get('var_99', 0)),
         'Loss not exceeded with 99% confidence'],
        ['ES 95%', _format_money(simulation_result.get('es_95', 0)),
         'Average loss in worst 5% of scenarios'],
        ['ES 99%', _format_money(simulation_result.get('es_99', 0)),
         'Average loss in worst 1% of scenarios'],
        ['Loss Rate', _format_pct(simulation_result.get('loss_rate', 0)),
         'Mean Loss / Total Exposure ratio'],
        ['Total Exposure', _format_money(simulation_result.get('total_exposure', 0)),
         'Sum of all loan EAD values'],
        ['Average Defaults', f'{simulation_result.get("n_defaults_mean", 0):,.0f}',
         'Expected number of defaults across portfolio'],
        ['LTR (Loss-to-Receivables)', _format_pct(simulation_result.get('ltr', 0)),
         'Loss / Average Credit Asset Balance'],
    ]

    metrics_table = Table(metrics_data, colWidths=[55*mm, 45*mm, 80*mm])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_SECONDARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
    ]))
    story.append(metrics_table)

    # EL Decomposition section
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph('EL Decomposition (PD × LGD × EAD)', H2_STYLE))
    decomp_data = [
        ['Component', 'Scenario Value', 'Base Value', 'Change'],
        ['PD (Default Probability)', _format_pct(simulation_result.get('pd_scenario', 0)),
         _format_pct(simulation_result.get('pd_base', 0)),
         f'{((simulation_result.get("pd_scenario", 0) or 0) - (simulation_result.get("pd_base", 0) or 0)) * 100:+.3f}%'],
        ['LGD (Loss Given Default)', _format_pct(simulation_result.get('lgd_scenario', 0)),
         _format_pct(simulation_result.get('lgd_base', 0)),
         f'{((simulation_result.get("lgd_scenario", 0) or 0) - (simulation_result.get("lgd_base", 0) or 0)) * 100:+.3f}%'],
        ['Analytical EL', _format_money(simulation_result.get('analytical_el', 0)),
         '—', '—'],
    ]
    decomp_table = Table(decomp_data, colWidths=[55*mm, 40*mm, 40*mm, 45*mm])
    decomp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
    ]))
    story.append(decomp_table)
    story.append(PageBreak())

    # ============================
    # SECTION 2: LOSS DISTRIBUTION CHART
    # ============================
    story.append(Paragraph('2. Loss Distribution Analysis', H1_STYLE))
    story.append(HRFlowable(width='100%', thickness=1, color=C_PRIMARY, spaceAfter=8))
    story.append(Paragraph(
        'The histogram below shows the simulated loss distribution from 10,000 Monte Carlo iterations. '
        'Vertical lines mark Expected Loss (EL, green), Value-at-Risk at 95% confidence (orange), '
        'and Value-at-Risk at 99% confidence (red).',
        BODY_STYLE
    ))
    story.append(Spacer(1, 4*mm))

    # Generate loss distribution chart
    loss_chart = _generate_loss_histogram(simulation_result)
    if loss_chart:
        story.append(loss_chart)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f'Analysis: Under the current scenario, the expected loss is {_format_money(simulation_result.get("mean_loss", 0))} '
        f'with a 99% VaR of {_format_money(simulation_result.get("var_99", 0))}. '
        f'The loss rate of {_format_pct(simulation_result.get("loss_rate", 0))} indicates '
        f'{"" if simulation_result.get("loss_rate", 0) < 0.05 else "elevated "}risk exposure.',
        BODY_STYLE
    ))
    story.append(PageBreak())

    # ============================
    # SECTION 3: 8-YEAR CYCLE PROJECTION
    # ============================
    if cycle_projections:
        story.append(Paragraph('3. Macro Cycle LTR Projection (8-Year)', H1_STYLE))
        story.append(HRFlowable(width='100%', thickness=1, color=C_PRIMARY, spaceAfter=8))
        story.append(Paragraph(
            'Projected Loss-to-Receivables (LTR) ratio across the full 8-year macroeconomic cycle. '
            'Simulated values are compared against target LTR benchmarks for each phase.',
            BODY_STYLE
        ))
        story.append(Spacer(1, 4*mm))

    # Cycle chart
    cycle_chart = _generate_cycle_chart(cycle_projections)
    if cycle_chart:
        story.append(cycle_chart)

        story.append(Spacer(1, 4*mm))

        # Cycle data table
        cycle_rows = [['Year', 'Phase', 'Simulated LTR', 'Target LTR', 'Deviation']]
        for p in cycle_projections:
            dev = p.get('simulated_ltr', 0) - p.get('target_ltr', 0)
            cycle_rows.append([
                f'Y{p.get("year", "?")}',
                p.get('phase_en', '—'),
                _format_pct(p.get('simulated_ltr', 0)),
                _format_pct(p.get('target_ltr', 0)),
                f'{dev*100:+.3f}%',
            ])

        cycle_table = Table(cycle_rows, colWidths=[20*mm, 45*mm, 40*mm, 40*mm, 35*mm])
        cycle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0284c7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
        ]))
        story.append(cycle_table)
        story.append(PageBreak())

    # ============================
    # SECTION 4: HEATMAP (if available)
    # ============================
    if heatmap_data:
        story.append(Paragraph('4. Dual-Stress Sensitivity Heatmap', H1_STYLE))
        story.append(HRFlowable(width='100%', thickness=1, color=C_PRIMARY, spaceAfter=8))
        story.append(Paragraph(
            'This heatmap visualizes the nonlinear interaction between Unemployment Rate '
            '(3%-12%) and Used Car Price Index (-20% to +10%). The contour lines mark capital '
            'adequacy thresholds. The red star indicates the current scenario position.',
            BODY_STYLE
        ))
        story.append(Spacer(1, 4*mm))

        # Static heatmap image
        hm_chart = _generate_heatmap_static(heatmap_data)
        if hm_chart:
            story.append(hm_chart)
        story.append(PageBreak())

    # ============================
    # SECTION 5: MODEL LIMITATIONS & DISCLAIMER
    # ============================
    story.append(Paragraph('5. Model Limitations & Disclaimer', H1_STYLE))
    story.append(HRFlowable(width='100%', thickness=1, color=C_ACCENT_ORANGE, spaceAfter=8))

    disclaimer_text = """
    <b>Important Notice:</b> This report is generated by the Auto Finance LTR Simulation System (v1.2) 
    for analytical and educational purposes only. It does not constitute financial advice, investment 
    recommendation, or regulatory filing.
    """
    story.append(Paragraph(disclaimer_text.strip(), DISCLAIMER_STYLE))
    story.append(Spacer(1, 3*mm))

    limitations = [
        "<b>1. Model Assumptions:</b> The simulation employs a Merton/Probit single-period credit risk model "
        "with three systematic factors (Growth, Interest Rate, Real Estate). Key assumptions include:",
        "• Asset returns follow a multivariate normal distribution (no fat tails or skewness)",
        "• Factor loadings are static and homogeneous within rating categories",
        "• No dynamic feedback effects between macro variables and credit conditions",
        "• Recovery rates are driven only by the real estate factor",
        "",
        "<b>2. Data Limitations:</b> The portfolio data is either synthetically generated or based on "
        "historical averages. Actual portfolio performance may differ materially.",
        "",
        "<b>3. Extreme Market Conditions:</b> The model does not account for:",
        "• Liquidity crises where asset sales cause price dislocations",
        "• Systemic contagion effects across asset classes",
        "• Nonlinear feedback loops (e.g., defaults → tighter credit → more defaults)",
        "• Regulatory or policy interventions that alter market dynamics",
        "",
        "<b>4. Regulatory Context:</b> While this simulation is inspired by CCAR/ICAAP frameworks, "
        "it is not a substitute for regulatory stress testing. Key differences include:",
        "• Single-period model vs. multi-period dynamic balance sheet models",
        "• Simplified LGD modeling vs. recovery waterfall analysis",
        "• No PPNR (Pre-Provision Net Revenue) or capital planning components",
        "",
        "<b>5. Validation:</b> Results should be validated against:",
        "• Historical loss experience for comparable portfolios",
        "• Alternative models (e.g., survival analysis, machine learning approaches)",
        "• Expert judgment and economic scenario analysis",
    ]

    for line in limitations:
        if line == '':
            story.append(Spacer(1, 1*mm))
        elif line.startswith('<b>'):
            story.append(Paragraph(line, ParagraphStyle('LimitationHeader', parent=BODY_STYLE,
                                                         fontSize=9, leading=12, textColor=HexColor('#334155'),
                                                         spaceBefore=6, spaceAfter=2)))
        else:
            story.append(Paragraph(line, ParagraphStyle('LimitationBody', parent=BODY_STYLE,
                                                         fontSize=8, leading=10, textColor=HexColor('#475569'),
                                                         leftIndent=15, spaceAfter=1)))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width='100%', thickness=1, color=HexColor('#cbd5e1'), spaceAfter=6))

    # Disclaimer footer
    final_disclaimer = """
    <b>Disclaimer:</b> The information contained in this report is provided "as is" without warranty of any kind, 
    express or implied. The simulation results are based on historical data patterns and mathematical models that 
    may not accurately predict future outcomes. Past performance is not indicative of future results. 
    The authors and developers assume no liability for any losses or damages arising from the use of this report 
    or the underlying simulation system. By using this report, you acknowledge these limitations and agree 
    to use the information solely for internal risk assessment purposes.
    """
    story.append(Paragraph(final_disclaimer.strip(), DISCLAIMER_STYLE))
    story.append(Spacer(1, 8*mm))

    # Footer with generation info
    story.append(HRFlowable(width='40%', thickness=0.5, color=HexColor('#cbd5e1'), spaceAfter=4))
    story.append(Paragraph(
        f'Report auto-generated on {now.strftime("%Y-%m-%d %H:%M:%S")} | '
        f'LTR Simulation Engine v1.2 | Multi-Factor Monte Carlo',
        FOOTER_STYLE
    ))
    story.append(Paragraph(
        'Auto Finance Loss-to-Receivables Simulation Platform',
        FOOTER_STYLE
    ))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue() if not output_path else None
    buffer.close()

    return pdf_bytes if not output_path else None


def _generate_loss_histogram(simulation_result: Dict) -> Optional[Image]:
    """Generate loss distribution histogram as matplotlib figure → PIL Image."""
    try:
        losses = simulation_result.get('_losses_raw', None)
        if losses is not None and len(losses) > 0:
            # Use raw losses if available
            loss_data = np.array(losses)
        else:
            # Synthesize from histogram bins
            hist_data = simulation_result.get('histogram', {})
            if not hist_data or not hist_data.get('bins'):
                return None
            bins = hist_data['bins']
            counts = hist_data['counts']
            # Reconstruct approximate data from bins
            bin_centers = [(bins[i] + bins[i+1]) / 2 for i in range(len(bins)-1)]
            loss_data = np.repeat(bin_centers, counts)

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
        fig.patch.set_facecolor('#ffffff')
        ax.set_facecolor('#f8fafc')

        n_bins = 50
        counts, bins, patches = ax.hist(loss_data, bins=n_bins, color='#38bdf8',
                                        edgecolor='#0284c7', linewidth=0.5, alpha=0.85)

        # Color bars by height
        max_count = max(counts) if len(counts) > 0 else 1
        for patch, count in zip(patches, counts):
            if count > max_count * 0.8:
                patch.set_facecolor('#ef4444')
            elif count > max_count * 0.5:
                patch.set_facecolor('#f59e0b')
            else:
                patch.set_facecolor('#38bdf8')

        # Mark lines
        mean_loss = simulation_result.get('mean_loss', 0)
        var_95 = simulation_result.get('var_95', 0)
        var_99 = simulation_result.get('var_99', 0)

        y_max = ax.get_ylim()[1]
        ax.axvline(mean_loss, color='#22c55e', linewidth=2, linestyle='-',
                   label=f'EL: ¥{mean_loss/1e6:.2f}M')
        ax.axvline(var_95, color='#f59e0b', linewidth=2, linestyle='--',
                   label=f'VaR 95%: ¥{var_95/1e6:.2f}M')
        ax.axvline(var_99, color='#ef4444', linewidth=2, linestyle='--',
                   label=f'VaR 99%: ¥{var_99/1e6:.2f}M')

        # Style
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.tick_params(colors='#64748b', labelsize=8)

        def fmt_money(x, p):
            if x >= 1e9: return f'¥{x/1e9:.1f}B'
            if x >= 1e6: return f'¥{x/1e6:.1f}M'
            return f'¥{x:.0f}'

        ax.xaxis.set_major_formatter(plt.FuncFormatter(fmt_money))
        ax.set_xlabel('Loss Amount', fontsize=9, color='#475569')
        ax.set_ylabel('Frequency', fontsize=9, color='#475569')
        ax.set_title('Simulated Loss Distribution (10,000 iterations)', fontsize=11,
                     color='#0f172a', fontweight='bold', pad=8)
        ax.legend(fontsize=7, loc='upper right', framealpha=0.9,
                  edgecolor='#cbd5e1', facecolor='#ffffff')

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return Image(buf)
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None


def _generate_cycle_chart(cycle_projections: List[Dict]) -> Optional[Image]:
    """Generate 8-year cycle chart as matplotlib figure."""
    try:
        years = [f'Y{p["year"]}' for p in cycle_projections]
        sim_ltr = [p['simulated_ltr'] * 100 for p in cycle_projections]
        target_ltr = [p['target_ltr'] * 100 for p in cycle_projections]
        phases_en = [p['phase_en'] for p in cycle_projections]

        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        fig.patch.set_facecolor('#ffffff')
        ax.set_facecolor('#f8fafc')

        x = range(len(years))
        bars = ax.bar(x, sim_ltr, width=0.5, color='#38bdf8', edgecolor='#0284c7',
                      linewidth=0.5, alpha=0.85, label='Simulated LTR', zorder=3)
        ax.plot(x, target_ltr, color='#f59e0b', linewidth=2.5, linestyle='--',
                marker='D', markersize=6, markerfacecolor='#f59e0b',
                markeredgecolor='#d97706', label='Target LTR', zorder=4)

        # Color bars by deviation
        for i, (bar, s, t) in enumerate(zip(bars, sim_ltr, target_ltr)):
            if s > t * 1.4:
                bar.set_facecolor('#ef4444')
                bar.set_edgecolor('#dc2626')
            elif s < t * 0.7:
                bar.set_facecolor('#22c55e')
                bar.set_edgecolor('#16a34a')

        # Style
        ax.set_xticks(x)
        ax.set_xticklabels(years, fontsize=8)
        ax.set_xlabel('Macro Cycle Year', fontsize=9, color='#475569')
        ax.set_ylabel('LTR (%)', fontsize=9, color='#475569')
        ax.set_title('8-Year Macro Cycle LTR Projection', fontsize=11,
                     color='#0f172a', fontweight='bold', pad=8)
        ax.legend(fontsize=8, loc='upper left', framealpha=0.9,
                  edgecolor='#cbd5e1', facecolor='#ffffff')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.tick_params(colors='#64748b', labelsize=8)
        ax.grid(axis='y', color='#e2e8f0', linewidth=0.5, zorder=0)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return Image(buf)
    except Exception as e:
        print(f"Cycle chart error: {e}")
        return None


def _generate_heatmap_static(heatmap_data: Dict) -> Optional[Image]:
    """Generate static heatmap image for PDF (interactive version is in frontend)."""
    try:
        X = np.array(heatmap_data['X'])
        Y = np.array(heatmap_data['Y'])
        Z = np.array(heatmap_data['loss_rate_matrix'])

        fig, ax = plt.subplots(figsize=(8, 6.5), dpi=150)
        fig.patch.set_facecolor('#ffffff')

        # Use a nice colormap
        pcm = ax.pcolormesh(X, Y, Z, cmap='RdYlGn_r', shading='auto', zorder=1)

        # Contour lines for capital thresholds
        contours = heatmap_data.get('contours', [])
        for contour in contours:
            level = contour['level']
            xs = contour['xs']
            ys = contour['ys']
            if len(xs) > 2:
                color = '#000000' if level == 6.0 else '#333333'
                linewidth = 1.5 if level == 8.0 else 1.0
                ax.plot(xs, ys, color=color, linewidth=linewidth,
                        linestyle='--' if level != 8.0 else '-',
                        label=f'{level:.0f}% Loss Rate', zorder=3)

        # Color bar
        cbar = fig.colorbar(pcm, ax=ax, shrink=0.8)
        cbar.set_label('Loss Rate (%)', fontsize=9, color='#475569')
        cbar.ax.tick_params(colors='#64748b', labelsize=8)

        # Labels
        ax.set_xlabel('Unemployment Rate (%)', fontsize=10, color='#475569')
        ax.set_ylabel('Used Car / House Price Change (%)', fontsize=10, color='#475569')
        ax.set_title('Dual-Stress Sensitivity: Unemployment × Asset Price',
                     fontsize=11, color='#0f172a', fontweight='bold', pad=8)

        # Star marker for current position
        current_x = heatmap_data.get('current_unemployment', None)
        current_y = heatmap_data.get('current_hp', None)
        if current_x is not None and current_y is not None:
            ax.plot(current_x, current_y, marker='*', color='red', markersize=18,
                    markeredgecolor='darkred', markeredgewidth=1.5, zorder=5)

        ax.tick_params(colors='#64748b', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')

        # Legend for contour
        if contours:
            ax.legend(fontsize=7, loc='upper left', framealpha=0.9,
                      edgecolor='#cbd5e1', facecolor='#ffffff')

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='PNG', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return Image(buf)
    except Exception as e:
        print(f"Heatmap static error: {e}")
        return None