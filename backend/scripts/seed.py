"""Pre-warm the cache for the preset AP/Telangana cities (default heatwave, 1990-2020).

Run from backend/ against a running API:
    python scripts/seed.py --api http://localhost:8000
Requests are sequential to stay well inside Open-Meteo's fair-use limits.
"""

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.regions import CITIES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--start", type=int, default=1990)
    ap.add_argument("--end", type=int, default=2020)
    args = ap.parse_args()

    with httpx.Client(base_url=args.api, timeout=120) as client:
        for c in CITIES:
            r = client.get("/api/hazards/heatwave",
                           params={"lat": c["lat"], "lon": c["lon"], "start": args.start, "end": args.end})
            status = r.json().get("cache", r.status_code) if r.is_success else r.status_code
            print(f"{c['name']:<15} {status}")


if __name__ == "__main__":
    main()
