"""Optional: one-line English descriptions written by Claude.

Switched off by default. To switch on: set ai.enabled to true in config.yaml and
add an ANTHROPIC_API_KEY secret to the GitHub repository.
"""
import json
import os

import requests

API_URL = "https://api.anthropic.com/v1/messages"


def describe(store, cfg, today):
    ac = cfg.get("ai", {})
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not ac.get("enabled") or not key:
        return 0
    todo = [r for r in store.get("companies", {}).values()
            if (r.get("web") or {}).get("status") == "live" and not r.get("ai")]
    todo.sort(key=lambda r: r.get("score", 0), reverse=True)
    done = 0
    for rec in todo[: int(ac.get("max_per_run", 40))]:
        web = rec["web"]
        prompt = (
            "You write one-line descriptions for a public list of new Brazilian companies "
            "at the crossroads of technology and the creative industries.\n"
            f"Company: {rec.get('trade_name') or rec.get('legal_name')}\n"
            f"Registered activity: {rec.get('cnae_desc')}\n"
            f"Website title: {web.get('title')}\n"
            f"Website description: {web.get('desc')}\n\n"
            "Reply with JSON only: {\"one_liner\": \"<max 20 words, plain English, factual, "
            "no hype>\"}. If the website says too little, use an empty string."
        )
        try:
            r = requests.post(API_URL, timeout=60, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01",
                "content-type": "application/json"},
                json={"model": ac.get("model", "claude-haiku-4-5"), "max_tokens": 120,
                      "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            text = r.json()["content"][0]["text"]
            line = json.loads(text[text.find("{"): text.rfind("}") + 1]).get("one_liner", "")
        except Exception as exc:
            print(f"  AI description skipped for {rec['cnpj']}: {exc}", flush=True)
            continue
        rec["ai"] = {"desc": line.strip()[:200], "date": today}
        done += 1
    print(f"AI descriptions written: {done}", flush=True)
    return done
