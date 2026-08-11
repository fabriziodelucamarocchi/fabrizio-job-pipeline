"""Fetch remote jobs from public sources. Returns normalized dicts.

Normalized job shape:
  key, source, id, title, company, location, salary, url, published, description, tags
"""
import html
from urllib.parse import quote
import requests
from .util import clean_html

TIMEOUT = 25
UA = {"User-Agent": "fabrizio-job-pipeline/1.0 (+github-actions)"}


def _norm_job(source, jid, title, company, location, salary, url, published, description, tags):
    return {
        "key": f"{source}:{jid}",
        "source": source,
        "id": str(jid),
        "title": title or "",
        "company": company or "",
        "location": location or "",
        "salary": salary or "",
        "url": url or "",
        "published": published or "",
        "description": clean_html(description)[:6000],
        "tags": [t for t in (tags or []) if t],
    }


# ---------------- Aggregators ----------------

def fetch_remotive(terms):
    out, seen = [], set()
    for term in terms:
        try:
            r = requests.get("https://remotive.com/api/remote-jobs",
                             params={"search": term, "limit": 50}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"[remotive] '{term}' failed: {e}")
            continue
        for j in jobs:
            jid = j.get("id")
            if jid is None or jid in seen:
                continue
            seen.add(jid)
            out.append(_norm_job("remotive", jid, j.get("title"), j.get("company_name"),
                                 j.get("candidate_required_location"), j.get("salary"),
                                 j.get("url"), j.get("publication_date"),
                                 j.get("description"), j.get("tags")))
    print(f"[remotive] {len(out)} jobs")
    return out


def fetch_remoteok():
    out = []
    try:
        r = requests.get("https://remoteok.com/api", headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[remoteok] failed: {e}")
        return out
    for j in data:
        if not isinstance(j, dict) or not j.get("id") or not j.get("position"):
            continue
        salary = ""
        if j.get("salary_min") or j.get("salary_max"):
            salary = f"{j.get('salary_min','')}-{j.get('salary_max','')} USD"
        out.append(_norm_job("remoteok", j.get("id"), j.get("position"), j.get("company"),
                             j.get("location"), salary, j.get("url"), j.get("date"),
                             j.get("description"), j.get("tags")))
    print(f"[remoteok] {len(out)} jobs")
    return out


# ---------------- Per-company ATS boards ----------------

def fetch_ashby(orgs):
    out = []
    for org in orgs:
        try:
            slug = quote(org, safe="")
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                             params={"includeCompensation": "true"}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"[ashby] '{org}' failed: {e}")
            continue
        for j in jobs:
            loc = j.get("location") or ""
            if j.get("isRemote"):
                loc = (loc + " Remote").strip()
            out.append(_norm_job("ashby", j.get("id"), j.get("title"), org, loc, "",
                                 j.get("jobUrl") or j.get("applyUrl"), j.get("publishedAt"),
                                 j.get("descriptionPlain") or j.get("descriptionHtml"),
                                 [j.get("department"), j.get("team")]))
        print(f"[ashby] '{org}': {len(jobs)} jobs")
    return out


def fetch_greenhouse(orgs):
    out = []
    for org in orgs:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs",
                             params={"content": "true"}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"[greenhouse] '{org}' failed: {e}")
            continue
        for j in jobs:
            # content is HTML-entity-encoded HTML -> unescape first, then strip tags
            desc = clean_html(html.unescape(j.get("content", "")))
            loc = (j.get("location") or {}).get("name", "")
            out.append(_norm_job("greenhouse", j.get("id"), j.get("title"), org, loc, "",
                                 j.get("absolute_url"), j.get("updated_at"), desc, []))
        print(f"[greenhouse] '{org}': {len(jobs)} jobs")
    return out


def fetch_lever(orgs):
    out = []
    for org in orgs:
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{org}",
                             params={"mode": "json"}, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            jobs = r.json()
        except Exception as e:
            print(f"[lever] '{org}' failed: {e}")
            continue
        for j in jobs:
            cats = j.get("categories", {}) or {}
            loc = cats.get("location", "")
            if j.get("workplaceType"):
                loc = (loc + " " + j["workplaceType"]).strip()
            out.append(_norm_job("lever", j.get("id"), j.get("text"), org, loc, "",
                                 j.get("hostedUrl"), j.get("createdAt"),
                                 j.get("descriptionPlain") or j.get("description"),
                                 [cats.get("team"), cats.get("commitment")]))
        print(f"[lever] '{org}': {len(jobs)} jobs")
    return out


# ---------------- Orchestration ----------------

def fetch_all(cfg):
    jobs = []
    src = cfg.get("sources", {})
    if src.get("remotive_terms"):
        jobs += fetch_remotive(src["remotive_terms"])
    if src.get("remoteok"):
        jobs += fetch_remoteok()
    if src.get("ashby"):
        jobs += fetch_ashby(src["ashby"])
    if src.get("greenhouse"):
        jobs += fetch_greenhouse(src["greenhouse"])
    if src.get("lever"):
        jobs += fetch_lever(src["lever"])
    uniq = {}
    for j in jobs:
        uniq[j["key"]] = j
    return list(uniq.values())
