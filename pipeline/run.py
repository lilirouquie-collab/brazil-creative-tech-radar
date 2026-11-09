"""Weekly run: new registry release (if any) -> website checks -> score -> site data.

    python -m pipeline.run                      # normal weekly run
    python -m pipeline.run --force-ingest       # rescan the registry even if already done
    python -m pipeline.run --local-data DIR --month 2026-10   # use zips already on disk
"""
import argparse
import datetime as dt
import json
import os
import sys

import yaml

from . import ai, build, enrich, ingest, score
from .receita import LocalSource, ReceitaSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "companies.json")
HISTORY = os.path.join(ROOT, "data", "history.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=0, separators=(",", ":"))
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-ingest", action="store_true")
    ap.add_argument("--skip-enrich", action="store_true")
    ap.add_argument("--build-only", action="store_true",
                    help="only rebuild the site files (after editing picks.yaml or config.yaml)")
    ap.add_argument("--local-data")
    ap.add_argument("--month")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)

    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    store = load_json(STORE, {"state": {}, "companies": {}})
    state = store.setdefault("state", {})
    today = args.today

    if args.build_only:
        score.score_all(store)
        build.build(store, cfg, ROOT, state.get("last_run") or today)
        return 0

    source = LocalSource(args.local_data, args.month) if args.local_data else ReceitaSource(cfg)
    new_companies = 0
    try:
        month = source.latest_complete_month()
    except Exception as exc:
        month = None
        print(f"WARNING: could not reach the registry this week ({exc}). "
              "Keeping last month's companies and continuing.", flush=True)
    if month is None and not store.get("companies"):
        raise SystemExit("The registry could not be reached and there is no data yet. "
                         "Try again later (Actions tab > Weekly update > Run workflow).")
    print(f"Latest registry release: {month}; last processed: {state.get('data_month')}",
          flush=True)
    if month and (args.force_ingest or month != state.get("data_month")):
        selected, report = ingest.scan(source, month, cfg)
        if not state.get("initial_load_date"):
            state["initial_load_date"] = today
        new_companies = ingest.merge(store, selected, today)
        state.update({"data_month": month, "cutoff": report["cutoff"],
                      "scanned": report["scanned"], "last_ingest_date": today})
        ingest.write_rules_report(report, os.path.join(ROOT, "data", "cnae_rules.md"))
        save_json(os.path.join(ROOT, "data", "last_scan.json"), report)
        save_json(STORE, store)  # save before the (long) website checks

    web_stats = {"checked": 0, "new_sites": 0}
    if not args.skip_enrich:
        web_stats = enrich.enrich(store, cfg, today)
        ai.describe(store, cfg, today)
    score.score_all(store)
    state["last_run"] = today
    save_json(STORE, store)
    stats = build.build(store, cfg, ROOT, today)

    history = load_json(HISTORY, [])
    history.append({"date": today, "data_month": state.get("data_month"),
                    "companies": stats["total"], "new_companies": new_companies,
                    "sites_checked": web_stats["checked"],
                    "new_sites": web_stats["new_sites"]})
    save_json(HISTORY, history[-200:])
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
