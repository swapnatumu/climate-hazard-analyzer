"""Pre-warm the cache for the preset AP/Telangana cities (default heatwave, 1990-2020).

Run from backend/ against a running API:
    python scripts/seed.py --api http://localhost:8000
Requests are sequential. Open-Meteo weights calls by days requested, so decades of daily
data for one cell uses a large share of the free per-minute quota: when the API answers
503 (UPSTREAM_RATE_LIMITED) the script waits and retries the same city.
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.regions import CITIES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--start", type=int, default=1990)
    ap.add_argument("--end", type=int, default=2020)
    ap.add_argument("--max-waits", type=int, default=5, help="retries per city when rate-limited")
    args = ap.parse_args()

    with httpx.Client(base_url=args.api, timeout=120) as client:
        for c in CITIES:
            params = {"lat": c["lat"], "lon": c["lon"], "start": args.start, "end": args.end}
            r = client.get("/api/hazards/heatwave", params=params)
            for _ in range(args.max_waits):
                if r.status_code != 503:
                    break
                wait = int(r.headers.get("retry-after", 60)) + 5
                print(f"{c['name']:<15} rate-limited upstream, waiting {wait}s")
                time.sleep(wait)
                r = client.get("/api/hazards/heatwave", params=params)
            status = r.json().get("cache", r.status_code) if r.is_success else r.status_code
            print(f"{c['name']:<15} {status}")


if __name__ == "__main__":
    main()
