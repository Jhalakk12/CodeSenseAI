"""
Unit tests for Feature 5: Corporate ROI & Economic Impact Calculator
Validates mathematical precision of labor value, SaaS displacement, risk mitigation,
payback periods, ROI percentages, preset configurations, and executive report generation.
"""

import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pytest
except ImportError:
    pass

from scripts.roi_calculator import CorporateROICalculator


def test_startup_preset_roi():
    """Verify Startup preset calculates correct baseline economics."""
    res = CorporateROICalculator.get_preset_roi("startup")
    assert res["inputs"]["team_size"] == 15
    assert res["inputs"]["avg_hourly_rate"] == 45.0
    
    # 15 devs * 8 hrs/mo * 12 mos = 1,440 hours
    assert res["labor_metrics"]["annual_hours_reclaimed"] == 1440.0
    # 1,440 hrs * $45 = $64,800
    assert res["labor_metrics"]["annual_labor_value"] == 64800.0
    
    # Copilot: 15 * 39 * 12 = 7,020; Sweep: 480 * 12 = 5,760; Snyk: 0
    # Total SaaS: 12,780.0
    assert res["saas_displacement"]["annual_saas_displaced"] == 12780.0
    
    # Risk: 2 * 3,500 = $7,000
    assert res["risk_mitigation"]["annual_incident_savings"] == 7000.0
    
    # Gross: 64,800 + 12,780 + 7,000 = $84,580.0
    assert res["financial_summary"]["annual_gross_benefit"] == 84580.0
    
    # Net: 84,580 - 480 (TCO) = $84,100.0
    assert res["financial_summary"]["annual_net_savings"] == 84100.0
    assert res["financial_summary"]["roi_percentage"] > 1000.0
    assert res["financial_summary"]["payback_days"] < 10.0


def test_midmarket_preset_roi():
    """Verify Mid-Market preset with Snyk displacement."""
    res = CorporateROICalculator.get_preset_roi("midmarket")
    assert res["inputs"]["team_size"] == 75
    assert res["saas_displacement"]["snyk_annual"] == 75 * 120.0 * 12
    assert res["financial_summary"]["annual_net_savings"] > 500000.0
    assert res["financial_summary"]["payback_days"] < 15.0


def test_enterprise_preset_roi():
    """Verify Global Enterprise preset with 250 developers."""
    res = CorporateROICalculator.get_preset_roi("enterprise")
    assert res["inputs"]["team_size"] == 250
    assert res["labor_metrics"]["annual_hours_reclaimed"] == 250 * 12.0 * 12
    assert res["financial_summary"]["annual_net_savings"] > 2000000.0
    assert res["financial_summary"]["cost_benefit_ratio"] > 100.0


def test_custom_roi_calculations():
    """Verify custom parameter variations work with correct math."""
    res = CorporateROICalculator.calculate_roi(
        team_size=10,
        avg_hourly_rate=50.0,
        hours_saved_per_dev_month=5.0,
        prevented_incidents_per_year=1,
        avg_incident_cost=5000.0,
        displace_copilot=True,
        displace_sweep=False,
        displace_snyk=False,
        codesense_annual_tco=1000.0,
        org_name="Custom Boutique Lab"
    )
    # Labor: 10 * 5 * 12 = 600 hrs * $50 = $30,000
    assert res["labor_metrics"]["annual_hours_reclaimed"] == 600.0
    assert res["labor_metrics"]["annual_labor_value"] == 30000.0
    
    # SaaS: 10 * 39 * 12 = $4,680
    assert res["saas_displacement"]["annual_saas_displaced"] == 4680.0
    
    # Incident: $5,000
    assert res["risk_mitigation"]["annual_incident_savings"] == 5000.0
    
    # Gross: 30,000 + 4,680 + 5,000 = $39,680
    assert res["financial_summary"]["annual_gross_benefit"] == 39680.0
    assert res["financial_summary"]["annual_net_savings"] == 38680.0
    # ROI: (38,680 / 1000) * 100 = 3868.0%
    assert res["financial_summary"]["roi_percentage"] == 3868.0


def test_boundary_and_zero_guardrails():
    """Verify calculator handles zero/extreme inputs gracefully without zero-division."""
    res = CorporateROICalculator.calculate_roi(
        team_size=0,
        avg_hourly_rate=0.0,
        hours_saved_per_dev_month=0.0,
        prevented_incidents_per_year=0,
        avg_incident_cost=0.0,
        displace_copilot=False,
        displace_sweep=False,
        displace_snyk=False,
        codesense_annual_tco=0.0
    )
    # Checks min guardrails
    assert res["inputs"]["team_size"] >= 1
    assert res["inputs"]["avg_hourly_rate"] >= 1.0
    assert res["inputs"]["codesense_annual_tco"] >= 1.0
    assert res["financial_summary"]["annual_gross_benefit"] >= 0.0
    assert "payback_days" in res["financial_summary"]


def test_executive_markdown_report_generation():
    """Verify publication-grade Markdown executive report generation."""
    res = CorporateROICalculator.get_preset_roi("startup")
    md = CorporateROICalculator.generate_executive_summary_markdown(res)
    assert "# 💼 CodeSense AI — Executive Business Case & ROI Audit Report" in md
    assert "Net Annual Savings" in md
    assert "Return on Investment" in md
    assert "GitHub Copilot Enterprise" in md
    assert "Total Cost of Ownership" in md


if __name__ == "__main__":
    test_startup_preset_roi()
    test_midmarket_preset_roi()
    test_enterprise_preset_roi()
    test_custom_roi_calculations()
    test_boundary_and_zero_guardrails()
    test_executive_markdown_report_generation()
    print("All 6 ROI Calculator tests passed successfully!")

