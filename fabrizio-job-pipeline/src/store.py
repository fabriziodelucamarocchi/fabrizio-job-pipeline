"""Persistent job state in data/jobs.json. Committed back by the GitHub Action."""
import json
import os
from .util import today, days_ago

DATA = os.path.join("data", "jobs.json")


def load():
    if not os.path.exists(DATA):
        return {}
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(store):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False, sort_keys=True)


def upsert(store, job, score, reasons, gaps):
    """Insert or update. Returns True if this key is NEW (first time seen)."""
    key = job["key"]
    if key in store:
        rec = store[key]
        rec["last_seen"] = today()
        rec["score"] = score
        rec["match_reasons"] = reasons
        rec["gaps"] = gaps
        # keep first_seen, status, cover_letter as-is
        if rec.get("status") == "stale":
            rec["status"] = "reopened"
        return False
    store[key] = {
        "key": key,
        "source": job["source"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "salary": job["salary"],
        "url": job["url"],
        "published": job["published"],
        "score": score,
        "match_reasons": reasons,
        "gaps": gaps,
        "first_seen": today(),
        "last_seen": today(),
        "status": "new",
        "cover_letter": False,
    }
    return True


def mark_stale(store, stale_after_days):
    for rec in store.values():
        if rec.get("status") in ("stale",):
            continue
        if days_ago(rec.get("last_seen", "")) > stale_after_days:
            rec["status"] = "stale"
