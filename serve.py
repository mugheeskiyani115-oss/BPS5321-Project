#!/usr/bin/env python3
"""Start BioTwin Singapore:  python serve.py  [--port 8000]  then open http://localhost:8000"""
import argparse

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    print(f"BioTwin Singapore → http://localhost:{args.port}")
    uvicorn.run("api.server:app", host=args.host, port=args.port, log_level="warning")
