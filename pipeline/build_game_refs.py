#!/usr/bin/env python3
"""Precompute the optimiser ("AI") reference results for every game mission.

    python -I pipeline/build_game_refs.py

Writes data/game/mission_refs.json, stamped with a fingerprint of all model inputs. The app recomputes live if the
fingerprint no longer matches (e.g. after a parameter change), so this file is a speed-up, not a dependency.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from biotwin import game  # noqa: E402
from biotwin.data import load_bundle  # noqa: E402

if __name__ == "__main__":
    b = load_bundle()
    refs = {}
    for mid, m in game.MISSIONS.items():
        t0 = time.time()
        refs[mid] = game.compute_reference(b, m)
        r = refs[mid]
        print(f"{m.icon} {m.title:<15} best cost S${r['best_cost_sgd_t']:,.1f}/t  best credits "
              f"{r['best_credit_t']:,.0f} tCO2e/yr  front {len(r['front'])} pts  ({time.time() - t0:.0f}s)")
    print("wrote", game.save_references(b, refs))
