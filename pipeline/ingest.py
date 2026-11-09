"""Monthly ingest: scan the Receita Federal CNPJ release and keep creative-tech companies."""
import datetime as dt
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import rules
from .receita import iter_rows, load_code_table

# Column positions in the Estabelecimentos files (official layout)
E_BASICO, E_ORDEM, E_DV, E_MATRIZ, E_FANTASIA, E_SITUACAO = 0, 1, 2, 3, 4, 5
E_INICIO, E_CNAE, E_CNAE2, E_UF, E_MUNICIPIO, E_EMAIL = 10, 11, 12, 19, 20, 27


def months_back(month, n):
    y, m = map(int, month.split("-"))
    m -= n
    while m <= 0:
        m += 12
        y -= 1
    return y, m


def _prefetched(source, month, names, workdir, ahead=2):
    """Yield (name, local path) in order while downloading the next files in the
    background. At most `ahead` + 1 files sit on disk at the same time."""
    with ThreadPoolExecutor(max_workers=ahead) as pool:
        futures = {}
        for i in range(min(ahead, len(names))):
            futures[i] = pool.submit(source.download, month, names[i], workdir)
        for i, name in enumerate(names):
            path = futures.pop(i).result()
            nxt = i + ahead
            if nxt < len(names):
                futures[nxt] = pool.submit(source.download, month, names[nxt], workdir)
            yield name, path


def _cleanup(path, workdir):
    if path.startswith(workdir) and os.path.exists(path):
        os.remove(path)


def scan(source, month, cfg, workdir=None):
    window = int(cfg.get("window_months", 12))
    y, m = months_back(month, window)
    cutoff = f"{y:04d}{m:02d}01"
    own_workdir = workdir is None
    workdir = workdir or tempfile.mkdtemp(prefix="cnpj_")
    print(f"Scanning release {month}: companies opened since {cutoff}", flush=True)

    # Small reference tables
    tables = {}
    for name in ["Cnaes.zip", "Municipios.zip", "Naturezas.zip"]:
        path = source.download(month, name, workdir)
        tables[name] = load_code_table(path)
        _cleanup(path, workdir)
    cnae_desc, municipios, naturezas = (tables["Cnaes.zip"], tables["Municipios.zip"],
                                        tables["Naturezas.zip"])

    # 1. Establishments: new, active head offices with a tech or creative activity
    pre = {}
    domain_counts = Counter()
    scanned_by_month = Counter()
    scanned = 0
    names = [f"Estabelecimentos{i}.zip" for i in range(10)]
    for name, path in _prefetched(source, month, names, workdir):
        n_file = 0
        for row in iter_rows(path):
            if len(row) < 28 or row[E_MATRIZ] != "1":
                continue
            opened = row[E_INICIO]
            if opened < cutoff or row[E_SITUACAO].strip().lstrip("0") != "2":
                continue
            scanned += 1
            n_file += 1
            scanned_by_month[opened[:6]] += 1
            email = row[E_EMAIL].strip().lower()
            domain = email.split("@", 1)[1] if "@" in email else ""
            if domain:
                domain_counts[domain] += 1
            codes = [row[E_CNAE]] + [c for c in row[E_CNAE2].split(",") if c]
            if not any(rules.is_relevant_cnae(c) for c in codes):
                continue
            pre[row[E_BASICO]] = (row[E_ORDEM], row[E_DV], row[E_FANTASIA].strip(), opened,
                                  row[E_CNAE].strip(), [c.strip() for c in codes[1:]],
                                  row[E_UF].strip(), row[E_MUNICIPIO].strip(), domain)
        print(f"  {name}: {n_file:,} new active head offices", flush=True)
        _cleanup(path, workdir)
    print(f"New companies scanned: {scanned:,}; with a tech/creative activity: {len(pre):,}",
          flush=True)

    # 2. Companies: legal name, legal form, share capital
    companies = {}
    names = [f"Empresas{i}.zip" for i in range(10)]
    for name, path in _prefetched(source, month, names, workdir):
        for row in iter_rows(path):
            if len(row) >= 6 and row[0] in pre:
                try:
                    capital = float(row[4].replace(".", "").replace(",", ".") or 0)
                except ValueError:
                    capital = 0.0
                companies[row[0]] = (row[1].strip(), row[2].strip(), capital, row[5].strip())
        _cleanup(path, workdir)

    # 3. Simples Nacional file: flags micro-entrepreneurs (MEI)
    mei = set()
    path = source.download(month, "Simples.zip", workdir)
    for row in iter_rows(path):
        if len(row) >= 5 and row[0] in pre and row[4].strip().upper() == "S":
            mei.add(row[0])
    _cleanup(path, workdir)
    if own_workdir:
        shutil.rmtree(workdir, ignore_errors=True)

    # 4. Apply the selection rules
    threshold = int(cfg.get("shared_domain_threshold", 4))
    selected = {}
    matched_subclasses = Counter()
    for basico, (ordem, dv, fantasia, opened, cnae_p, cnae_s, uf, mun, domain) in pre.items():
        comp = companies.get(basico)
        if not comp or basico in mei:
            continue
        razao, natureza, capital, porte = comp
        if not natureza.startswith("2") or natureza in rules.EXCLUDED_LEGAL_NATURES:
            continue
        tech_any, creative = rules.classify_cnaes([cnae_p] + cnae_s)
        name_norm = rules.normalize(f"{razao} {fantasia}")
        name_creative = rules.creative_sectors_from_name(name_norm)
        name_tech = rules.has_tech_name(name_norm)
        inova = "INOVA SIMPLES" in name_norm
        reasons = []
        if tech_any and creative:
            reasons.append("activities")
        if (tech_any and name_creative) or (creative and name_tech):
            reasons.append("name")
        if inova and (tech_any or creative):
            reasons.append("inova")
        if not reasons:
            continue
        sectors = list(creative)
        if "name" in reasons:
            sectors += [s for s in name_creative if s not in sectors]
        if not sectors:
            sectors = ["Other startups"]
        for c in [cnae_p] + cnae_s:
            if rules.is_relevant_cnae(c):
                matched_subclasses[c] += 1
        if domain and (domain in rules.FREE_EMAIL_DOMAINS or domain_counts[domain] >= threshold
                       or any(h in domain for h in rules.SERVICE_DOMAIN_HINTS)):
            domain = ""
        cnpj = f"{basico}{ordem}{dv}"
        selected[cnpj] = {
            "cnpj": cnpj,
            "cc": "BR",
            "legal_name": razao,
            "trade_name": fantasia,
            "opened": f"{opened[:4]}-{opened[4:6]}-{opened[6:8]}",
            "uf": uf,
            "city": municipios.get(mun, ""),
            "mun": mun,
            "cnae": cnae_p,
            "cnae_desc": cnae_desc.get(cnae_p, ""),
            "cnae_secondary": cnae_s,
            "tech": tech_any or name_tech,
            "sectors": sectors,
            "reasons": reasons,
            "inova": inova,
            "legal_form": naturezas.get(natureza, natureza),
            "corporation": natureza in rules.CORPORATION_NATURES,
            "capital": capital,
            "size": porte,
            "domain": domain,
        }
    print(f"Creative-tech companies selected: {len(selected):,}", flush=True)

    report = {
        "month": month,
        "cutoff": cutoff,
        "scanned": scanned,
        "scanned_by_month": dict(sorted(scanned_by_month.items())),
        "pre_candidates": len(pre),
        "selected": len(selected),
        "matched_subclasses": {c: [n, cnae_desc.get(c, "?")]
                               for c, n in matched_subclasses.most_common()},
    }
    return selected, report


def merge(store, selected, today):
    """Keep enrichment of companies already known; add the new ones."""
    old = store.get("companies", {})
    merged = {}
    new = 0
    for cnpj, rec in selected.items():
        prev = old.get(cnpj)
        if prev:
            rec["first_seen"] = prev.get("first_seen", today)
            for key in ("web", "guess", "ai"):
                if key in prev:
                    rec[key] = prev[key]
            if prev.get("domain") and prev["domain"] != rec["domain"]:
                rec.pop("web", None)  # email changed: check the new domain
        else:
            rec["first_seen"] = today
            new += 1
        merged[cnpj] = rec
    store["companies"] = merged
    return new


def write_rules_report(report, path):
    lines = [f"# Activities matched in release {report['month']}", "",
             "Generated automatically. Check that every activity below belongs on the site;",
             "edit pipeline/rules.py to add or remove CNAE classes.", "",
             "| CNAE | Official description | Companies |", "|---|---|---|"]
    for code, (n, desc) in report["matched_subclasses"].items():
        lines.append(f"| {code} | {desc} | {n} |")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
