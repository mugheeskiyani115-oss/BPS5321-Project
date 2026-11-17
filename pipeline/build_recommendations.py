#!/usr/bin/env python3
"""Precompute the optimiser's recommended layouts for each preset throughput.

    python -I pipeline/build_recommendations.py

Writes data/recommendations.json, stamped with a fingerprint of all model inputs. The app recomputes live if the
fingerprint no longer matches, so this file is a speed-up, not a dependency.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from biotwin import recommend  # noqa: E402
from biotwin.data import load_bundle  # noqa: E402

if __name__ == "__main__":
    b = load_bundle()
    recs = {}
    for t in recommend.TARGETS:
        t0 = time.time()
        recs[float(t)] = r = recommend.compute(b, t)
        print(f"{t:>6,} t/yr  cheapest S${r['cheapest']['net_cost_sgd_per_t']:,.0f}/t ({r['cheapest']['label']})  "
              f"options {len(r['options'])}  ({time.time() - t0:.0f}s)")
    print("wrote", recommend.save(b, recs))
