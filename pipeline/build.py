"""Write the public JSON files the website reads (no personal data)."""
import datetime as dt
import json
import os
import re
from collections import Counter, defaultdict

import yaml

from . import geo
from .rules import SECTORS

_SMALL = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "of", "the", "and"}
_LEGAL_SUFFIX = re.compile(
    r"\b(LTDA\.?|LIMITADA|S/?A|S\.A\.|ME|EPP|EIRELI|SLU|SOCIEDADE UNIPESSOAL|"
    r"INOVA SIMPLES \(I\.S\.\)|INOVA SIMPLES)\s*$", re.I)


def nice_case(text):
    words = (text or "").strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i and lw in _SMALL:
            out.append(lw)
        elif len(w) <= 3 and w.isalpha() and w.isupper() and lw not in _SMALL and i:
            out.append(w)  # keep short acronyms (TV, IA, 3D...)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def display_name(rec):
    for raw in (rec.get("trade_name"), rec.get("legal_name")):
        name = re.sub(r"^\d{2}\.?\d{3}\.?\d{3}\s*", "", raw or "").strip()
        for _ in range(3):
            name = _LEGAL_SUFFIX.sub("", name).strip(" -,.")
        if len(name) >= 2 and name.upper() not in ("********", "INOVA SIMPLES"):
            return nice_case(name)
    c = rec["cnpj"]
    return f"Inova Simples startup {c[:2]}.{c[2:5]}.{c[5:8]}" if rec.get("inova") else nice_case(
        rec.get("legal_name", c))


def public_record(rec, today_d, initial, latest_opened):
    web = rec.get("web") or {}
    first_seen = rec.get("first_seen", "")
    week_ago = (today_d - dt.timedelta(days=7)).isoformat()
    is_new = first_seen >= week_ago and (
        first_seen != initial or rec["opened"] >= (latest_opened - dt.timedelta(days=30)).isoformat())
    site_new = (web.get("found") and web.get("found") == web.get("checked")
                and web.get("found") >= week_ago and web.get("was") in ("down", "soon"))
    desc = (rec.get("ai") or {}).get("desc") or web.get("desc") or web.get("title") or ""
    cc = rec.get("cc", "BR")
    where = geo.locate(cc, rec.get("mun"), rec.get("city"), rec.get("uf"))
    return {
        "id": rec["cnpj"],
        "cc": cc,
        "lat": where[0] if where else None,
        "lon": where[1] if where else None,
        "n": display_name(rec),
        "ln": rec.get("legal_name", ""),
        "o": rec["opened"],
        "uf": rec.get("uf", ""),
        "c": nice_case(rec.get("city", "")),
        "s": rec.get("sectors", []),
        "r": rec.get("reasons", []),
        "a": rec.get("cnae_desc", ""),
        "inv": bool(rec.get("inova")),
        "cap": rec.get("capital", 0),
        "sa": bool(rec.get("corporation")),
        "w": web.get("url", "") if web.get("status") in ("live", "soon", "social") else "",
        "ws": web.get("status", ""),
        "ig": web.get("instagram", ""),
        "li": web.get("linkedin", ""),
        "d": desc,
        "sc": rec.get("score", 0),
        "nw": bool(is_new),
        "sn": bool(site_new),
    }


def build(store, cfg, root, today):
    state = store.setdefault("state", {})
    today_d = dt.date.fromisoformat(today)
    companies = list(store.get("companies", {}).values())
    latest_opened = max((dt.date.fromisoformat(r["opened"]) for r in companies),
                        default=today_d)
    initial = state.get("initial_load_date", "")
    records = [public_record(r, today_d, initial, latest_opened) for r in companies]
    records.sort(key=lambda r: (r["sc"], r["o"]), reverse=True)

    by_month = defaultdict(Counter)
    for r in records:
        for s in r["s"][:1]:  # count each company once, under its first sector
            by_month[r["o"][:7]][s] += 1
    months = sorted(by_month)
    stats = {
        "months": months,
        "sectors": SECTORS,
        "by_month": {m: dict(by_month[m]) for m in months},
        "by_sector": dict(Counter(s for r in records for s in r["s"])),
        "by_state": dict(Counter(r["uf"] for r in records).most_common(12)),
        "total": len(records),
        "online": sum(1 for r in records if r["ws"] in ("live", "social")),
        "soon": sum(1 for r in records if r["ws"] == "soon"),
        "inova": sum(1 for r in records if r["inv"]),
        "new_week": sum(1 for r in records if r["nw"]),
        "new_sites_week": sum(1 for r in records if r["sn"]),
        "located": sum(1 for r in records if r["lat"] is not None),
        "scanned": state.get("scanned", 0),
        "partial_month": state.get("data_month", ""),
    }
    picks_path = os.path.join(root, "picks.yaml")
    picks = {}
    if os.path.exists(picks_path):
        with open(picks_path, encoding="utf-8") as fh:
            picks = yaml.safe_load(fh) or {}
    site = cfg.get("site", {})
    meta = {
        "title": site.get("title", "Brazil Creative Tech Radar"),
        "tagline": site.get("tagline", ""),
        "author": site.get("author", ""),
        "author_link": site.get("author_link", ""),
        "updated": today,
        "data_month": state.get("data_month", ""),
        "cutoff": state.get("cutoff", ""),
        "window_months": cfg.get("window_months", 12),
        "countries": sorted({r["cc"] for r in records}) or ["BR"],
    }
    out = os.path.join(root, "site", "data")
    os.makedirs(out, exist_ok=True)
    for name, payload in (("companies.json", records), ("stats.json", stats),
                          ("meta.json", meta), ("picks.json", picks)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Site data written: {len(records)} companies", flush=True)
    return stats
