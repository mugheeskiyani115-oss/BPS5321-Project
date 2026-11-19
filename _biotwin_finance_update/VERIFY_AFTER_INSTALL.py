"""Optional BioTwin integrated model smoke test. Run from the website root.

    py _biotwin_finance_update\VERIFY_AFTER_INSTALL.py

This uses the actual website data and model. It never modifies data files.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from api.server import app

with TestClient(app) as client:
    base = {"sites": ["S02"], "size": "C50", "gate_fee": 82.2, "sell_credits": True}
    a = client.post("/api/evaluate", json=base)
    if a.status_code != 200:
        raise SystemExit(f"Baseline API failed: HTTP {a.status_code}: {a.text[:800]}")
    baseline = a.json()
    assert baseline["finance_audit"]["status"] == "reconciled", baseline["finance_audit"]
    scenario = {**base, "advanced": {
        "continuous_crew_per_shift": 3.0,
        "biochar_price_usd": 300.0,
        "woody_share": 0.75,
        "seasonal_woody_amplitude": 0.1125,
        "woody_share_uncertainty_sd": 0.05,
    }}
    b = client.post("/api/evaluate", json=scenario)
    if b.status_code != 200:
        raise SystemExit(f"Commercial API failed: HTTP {b.status_code}: {b.text[:800]}")
    improved = b.json()
    assert improved["finance_audit"]["status"] == "reconciled"
    assert improved["metrics"]["staff"] < baseline["metrics"]["staff"], "Crew override did not reduce FTE"
    assert improved["income_per_t"].get("Biochar sales", 0) > baseline["income_per_t"].get("Biochar sales", 0)
    assert len(improved["seasonality"]["months"]) == 12
    assert improved["seasonality"]["monte_carlo_draws"] == 500
    print("PASS: baseline and commercial scenarios calculate successfully")
    print("PASS: financial reconciliation, staffing, physical product income, seasonal sensitivity")
    print(f"Base scenario NPV: S${baseline['metrics']['npv_sgd']:,.0f}")
    print(f"Commercial scenario NPV: S${improved['metrics']['npv_sgd']:,.0f}")
    print("Results are scenario estimates, not vendor-validated investment projections.")
