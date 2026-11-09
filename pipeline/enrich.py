"""Weekly enrichment: look for each company's website, Instagram and LinkedIn page.

Only public company websites are visited. LinkedIn itself is never scraped:
LinkedIn links are taken from the company's own website, and the site offers a
one-click LinkedIn search for the rest.
"""
import datetime as dt
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from . import rules

USER_AGENT = ("Mozilla/5.0 (compatible; BrazilCreativeTechRadar/1.0; "
              "open-data research project)")
MAX_BYTES = 600_000

# Always mean "no real website yet"
PARKED_STRONG = [
    "domain for sale", "domain is for sale", "dominio a venda", "domínio à venda",
    "parked domain", "domain parking", "welcome to nginx", "apache2 ubuntu default page",
    "apache2 debian default page", "default web site page", "index of /",
    "domínio registrado", "dominio registrado", "website is ready",
    "account suspended", "conta suspensa", "this domain has been registered",
]
# Only count on short pages (a real shop can announce a collection "em breve")
PARKED_WEAK = [
    "em construção", "em construcao", "under construction", "coming soon", "em breve",
    "manutenção", "manutencao", "opening soon", "hospedagem de sites", "plesk",
    "cpanel", "hostgator", "locaweb", "this domain", "lançamento em breve",
]
SOCIAL_HOSTS = {"instagram.com", "www.instagram.com", "linktr.ee", "www.linktr.ee",
                "facebook.com", "www.facebook.com", "wa.me", "api.whatsapp.com"}
IG_RE = re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{2,30})/?", re.I)
IG_SKIP = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "instagram",
           "about", "developer", "legal", "direct"}
LI_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(company|school)/([^/?#\"'\s<>]+)",
                   re.I)


_local = threading.local()


def _session():
    if getattr(_local, "session", None):
        return _local.session
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT,
                      "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                      "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
    _local.session = s
    return s


def _get(session, url, timeout):
    r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
    body = b""
    for chunk in r.iter_content(65536):
        body += chunk
        if len(body) > MAX_BYTES:
            break
    r.close()
    enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else None
    try:
        html = body.decode(enc or "utf-8", errors="replace")
    except LookupError:
        html = body.decode("utf-8", errors="replace")
    return r, html


def parse_page(html, final_url):
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    desc = ""
    for attrs in ({"name": "description"}, {"property": "og:description"},
                  {"name": "twitter:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            desc = tag["content"].strip()
            break
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    links = " ".join(a.get("href", "") for a in soup.find_all("a")) + " " + html[:200000]
    instagram = ""
    for m in IG_RE.finditer(links):
        if m.group(1).lower() not in IG_SKIP:
            instagram = f"https://www.instagram.com/{m.group(1)}/"
            break
    linkedin = ""
    m = LI_RE.search(links)
    if m:
        linkedin = f"https://www.linkedin.com/{m.group(1).lower()}/{m.group(2)}/"
    host = urlparse(final_url).netloc.lower()
    if host in SOCIAL_HOSTS and "instagram.com" in host and not instagram:
        m = IG_RE.search(final_url)
        if m and m.group(1).lower() not in IG_SKIP:
            instagram = f"https://www.instagram.com/{m.group(1)}/"
    low = (title + " " + text[:3000]).lower()
    short = len(text) < 600
    script_app = len(html) > 3000 and bool(title)  # JavaScript sites render little text
    if host in SOCIAL_HOSTS:
        status = "social"
    elif any(h in low for h in PARKED_STRONG) or (short and any(h in low for h in PARKED_WEAK)):
        status = "soon"
    elif len(text) < 150 and not script_app:
        status = "soon"
    else:
        status = "live"
    return {
        "status": status,
        "url": final_url,
        "title": title[:160],
        "desc": desc[:300],
        "instagram": instagram,
        "linkedin": linkedin,
        "_text": text[:4000],
    }


def check_domain(session, domain, timeout):
    last_error = "unreachable"
    for url in (f"https://{domain}", f"https://www.{domain}", f"http://{domain}"):
        try:
            r, html = _get(session, url, timeout)
        except requests.RequestException as exc:
            last_error = type(exc).__name__
            continue
        if r.status_code >= 400:
            last_error = f"HTTP {r.status_code}"
            continue
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and not html.lstrip().startswith("<"):
            last_error = "not html"
            continue
        return parse_page(html, r.url)
    return {"status": "down", "error": last_error}


def _cnpj_on_page(cnpj, text):
    digits = re.sub(r"\D", "", text)
    formatted = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj in digits or formatted in text


_SUFFIXES = re.compile(r"\b(LTDA|ME|EPP|EIRELI|S A|SA|SLU|INOVA SIMPLES I S|INOVA SIMPLES|"
                       r"SOCIEDADE|UNIPESSOAL|LIMITADA|COMERCIO|SERVICOS|DE|DA|DO|E)\b")


def guess_domains(rec):
    """Candidate domains built from the trade name (verified later via the CNPJ)."""
    out = []
    for name in (rec.get("trade_name"), rec.get("legal_name")):
        slug = _SUFFIXES.sub(" ", rules.normalize(name or ""))
        slug = re.sub(r"[^A-Z0-9]", "", slug).lower()
        if 4 <= len(slug) <= 30 and re.search(r"[a-z]{3}", slug):
            for tld in (".com.br", ".com"):
                if slug + tld not in out:
                    out.append(slug + tld)
    return out[:4]


def _days_since(date_str, today):
    if not date_str:
        return 10_000
    return (today - dt.date.fromisoformat(date_str)).days


def _work_item(rec, timeout, kind):
    session = _session()
    if kind == "domain":
        return rec["cnpj"], kind, check_domain(session, rec["domain"], timeout)
    for domain in guess_domains(rec):
        res = check_domain(session, domain, timeout)
        if res["status"] in ("live", "soon") and _cnpj_on_page(rec["cnpj"], res.get("_text", "")):
            res["guessed"] = True
            return rec["cnpj"], kind, res
    return rec["cnpj"], kind, None


def enrich(store, cfg, today):
    ec = cfg.get("enrich", {})
    timeout = (8, float(ec.get("timeout_seconds", 12)))
    today_d = dt.date.fromisoformat(today)
    companies = store.get("companies", {})
    todo = []
    for rec in companies.values():
        web = rec.get("web")
        if rec.get("domain"):
            wait = ec.get("recheck_days_site", 56) if web and web.get("status") in (
                "live", "social") else ec.get("recheck_days_no_site", 28)
            if not web or _days_since(web.get("checked"), today_d) >= wait:
                todo.append((rec, "domain"))
        elif ec.get("guess_domains", True) and not (web and web.get("status") in ("live", "social")):
            guess = rec.get("guess", {})
            if _days_since(guess.get("checked"), today_d) >= ec.get("recheck_days_guess", 56):
                todo.append((rec, "guess"))
    # newest companies first
    todo.sort(key=lambda t: t[0].get("opened", ""), reverse=True)
    limit_domain = int(ec.get("max_sites_per_run", 2500))
    limit_guess = int(ec.get("max_guesses_per_run", 800))
    selected, nd, ng = [], 0, 0
    for rec, kind in todo:
        if kind == "domain" and nd < limit_domain:
            selected.append((rec, kind)); nd += 1
        elif kind == "guess" and ng < limit_guess:
            selected.append((rec, kind)); ng += 1
    print(f"Website checks this run: {nd} known domains, {ng} name-based guesses", flush=True)

    stats = {"checked": 0, "live": 0, "new_sites": 0}
    with ThreadPoolExecutor(max_workers=int(ec.get("concurrency", 24))) as pool:
        futures = [pool.submit(_work_item, rec, timeout, kind)
                   for rec, kind in selected]
        for fut in as_completed(futures):
            try:
                cnpj, kind, res = fut.result()
            except Exception as exc:  # never let one site break the run
                print(f"  enrichment error: {exc}", flush=True)
                continue
            rec = companies[cnpj]
            stats["checked"] += 1
            if kind == "guess":
                rec["guess"] = {"checked": today}
                if not res:
                    continue
            prev = rec.get("web") or {}
            res.pop("_text", None)
            res["checked"] = today
            online = res["status"] in ("live", "social")
            res["found"] = prev.get("found") or (today if online else "")
            res["was"] = prev.get("status", "")  # status at the previous check
            if online and not prev.get("found"):
                stats["new_sites"] += 1
            if online:
                stats["live"] += 1
            if kind == "guess" and res.get("url"):
                rec["domain_guessed"] = urlparse(res["url"]).netloc
            rec["web"] = res
    print(f"Sites checked: {stats['checked']}, online: {stats['live']}, "
          f"newly found: {stats['new_sites']}", flush=True)
    return stats
