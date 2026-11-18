"""Six PWC sector *synthetic* scenario from the team's Word document (18 Nov 2026).

NEA's 232,000 t 2025 national horticultural waste figure is observed; the six sector
percentages are NOT operator measurements. Reconciliation to the national value is
mass balance, not an independent validation of the spatial allocation.

The six PWC sectors are distinct from the five URA planning regions. Planning-area
crosswalk assignments are approximate (some areas straddle PWC boundaries).
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

SCENARIO_FILE = Path(__file__).resolve().parents[1] / 'data' / 'pwc_scenario_2025.csv'
BASIS_ORIGINAL = 'vegetation_proxy'
BASIS_SIX = 'six_sector_scenario'
BASIS = (BASIS_ORIGINAL, BASIS_SIX)


def load_sector_scenario(path: Path | None = None) -> pd.DataFrame:
    df = pd.read_csv(path or SCENARIO_FILE)
    required = {'pwc_sector', 'share', 'annual_t', 'woody_t', 'leafy_t', 'year', 'source_status'}
    if not required.issubset(df.columns):
        raise ValueError(f'Six-sector scenario missing columns {sorted(required - set(df.columns))}')
    if len(df) != 6 or df.pwc_sector.duplicated().any():
        raise ValueError('Six-sector scenario requires six distinct PWC sectors')
    if (df[['share', 'annual_t', 'woody_t', 'leafy_t']] < 0).any().any():
        raise ValueError('Six-sector values cannot be negative')
    if not np.isclose(df.share.sum(), 1., atol=1e-10):
        raise ValueError('Sector shares must sum to one')
    if not np.isclose(df.annual_t.sum(), 232000., atol=1e-6):
        raise ValueError('Document synthetic tonnes do not reconcile to 232,000 t')
    if not np.allclose(df.annual_t, df.woody_t + df.leafy_t, atol=1e-6):
        raise ValueError('Woody and leafy quantities do not reconcile')
    if df.source_status.ne('synthetic_sector_proxy').any():
        raise ValueError('Document values must remain labelled synthetic_sector_proxy')
    return df


def allocate_to_planning_areas(areas: pd.DataFrame, national_t: float = 232000.,
                               scenario: pd.DataFrame | None = None) -> np.ndarray:
    """Spread six synthetic sector targets within each sector using original vegetation proxy weights.

    This holds the national total constant for comparability. No operator measurement is inferred.
    Leaves the original input data unchanged and aligns outputs to areas row order.
    """
    d = load_sector_scenario() if scenario is None else scenario
    if not np.isclose(national_t, float(d.annual_t.sum()), atol=1e-6):
        raise ValueError('Six-sector scenario applies to the 2025 national baseline of 232,000 t')
    if 'pwc_sector' not in areas or 'estimated_t' not in areas:
        raise ValueError('Planning areas need pwc_sector and estimated_t')
    if areas.pwc_sector.isna().any():
        raise ValueError('A planning area has no PWC sector crosswalk')
    found = set(areas.pwc_sector)
    expected = set(d.pwc_sector)
    if found != expected:
        raise ValueError(f'Sector crosswalk mismatch; missing: {sorted(expected-found)}, extra: {sorted(found-expected)}')
    shares = areas.estimated_t.to_numpy(dtype=float)
    if not np.isfinite(shares).all() or (shares < 0).any():
        raise ValueError('Vegetation proxy values must be nonnegative')
    result = np.zeros(len(areas), float)
    for row in d.itertuples():
        mask = areas.pwc_sector.eq(row.pwc_sector).to_numpy()
        w = shares[mask]
        if not mask.any() or w.sum() <= 0:
            raise ValueError(f'No positive planning area weights in {row.pwc_sector}')
        result[mask] = float(row.annual_t) * w / w.sum()
    if not np.isclose(result.sum(), national_t, atol=1e-6):
        raise RuntimeError('Sector scenario failed national mass balance')
    return result


def comparison(areas: pd.DataFrame) -> list[dict]:
    d = load_sector_scenario()
    original = areas.groupby('pwc_sector').estimated_t.sum()
    rows = []
    for r in d.itertuples():
        base = float(original.get(r.pwc_sector, 0.))
        rows.append({'pwc_sector': r.pwc_sector, 'word_share_pct': 100 * float(r.share),
                     'synthetic_t': float(r.annual_t), 'original_proxy_t': base,
                     'difference_t': float(r.annual_t) - base,
                     'woody_scenario_t': float(r.woody_t), 'leafy_scenario_t': float(r.leafy_t),
                     'source_status': 'synthetic_sector_proxy'})
    return rows
