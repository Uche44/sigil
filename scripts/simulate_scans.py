"""Simulate scans from far-apart places to exercise the activity hints.

Example:
  python scripts/simulate_scans.py --batch-code abcdefghijklm --serial ABCDEFGH23456789
"""

from __future__ import annotations

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--batch-code", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument(
        "--regions",
        default="NG-LA,GH-AC,KE-NB,ZA-GP",
        help="comma separated coarse regions",
    )
    parser.add_argument("--proof", action="store_true")
    options = parser.parse_args()

    regions = [region.strip() for region in options.regions.split(",") if region.strip()]
    for region in regions:
        response = httpx.get(
            f"{options.api}/api/v1/verify/{options.batch_code}/{options.serial}",
            params={"proof": "true"} if options.proof else None,
            headers={"X-Sigil-Region": region},
            timeout=20,
        )
        if response.status_code != 200:
            print(f"{region}: HTTP {response.status_code} {response.text}")
            continue
        body = response.json()
        print(f"{region}: {body['verdict']} — {body['message']}")

    print(
        "\nOpen the producer dashboard and view this batch's activity. "
        "The code is now linked to several regions; that is a hint, not proof."
    )


if __name__ == "__main__":
    main()
