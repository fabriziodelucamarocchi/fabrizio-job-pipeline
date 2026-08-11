"""Fetch remote jobs from public sources (public APIs / RSS only, no ToS-violating
scraping, no LinkedIn). Returns normalized dicts:
  key, source, id, title, company, location, salary, url, published, description, tags
"""
import html
import xml.etree.ElementTree as ET
from urllib.parse import quote
import requests
from .util import clean_html

TIMEOUT = 25
UA = {"User-Agent": "fabrizio-job-pipeline/1.0 (+github-actions)"}


def _norm(source, jid, title, company, location, salary, url, published, description, tags):
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


def _get(url, params=None):
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r


# ---------------- Aggregators ----------------

def fetch_remotive(terms):
    out, seen = [], set()
    for term in terms:
        try:
            jobs = _get("https://remotive.com/api/remote-jobs",
                        {"search": term, "limit": 50}).json().get("jobs", [])
        except Exception as e:
            print(f"[remotive] '{term}' failed: {e}"); continue
        for j in jobs:
            jid = j.get("id")
            if jid is None or jid in seen: continue
            seen.add(jid)
            out.append(_norm("remotive", jid, j.get("title"), j.get("company_name"),
                             j.get("candidate_required_location"), j.get("salary"),
                             j.get("url"), j.get("publication_date"),
                             j.get("description"), j.get("tags")))
    print(f"[remotive] {len(out)} jobs")
    return out


def fetch_remoteok():
    out = []
    try:
        data = _get("https://remoteok.com/api").json()
    except Exception as e:
        print(f"[remoteok] failed: {e}"); return out
    for j in data:
        if not isinstance(j, dict) or not j.get("id") or not j.get("position"): continue
        salary = ""
        if j.get("salary_min") or j.get("salary_max"):
            salary = f"{j.get('salary_min','')}-{j.get('salary_max','')} USD"
        out.append(_norm("remoteok", j.get("id"), j.get("position"), j.get("company"),
                         j.get("location"), salary, j.get("url"), j.get("date"),
                         j.get("description"), j.get("tags")))
    print(f"[remoteok] {len(out)} jobs")
    return out


def fetch_jobicy(geos):
    """Jobicy public API. geos e.g. ['latin-america','anywhere']."""
    out, seen = [], set()
    for geo in geos:
        try:
            jobs = _get("https://jobicy.com/api/v2/remote-jobs",
                        {"count": 50, "geo": geo}).json().get("jobs", [])
        except Exception as e:
            print(f"[jobicy] geo='{geo}' failed: {e}"); continue
        for j in jobs:
            jid = j.get("id")
            if jid is None or jid in seen: continue
            seen.add(jid)
            salary = ""
            if j.get("annualSalaryMin") or j.get("annualSalaryMax"):
                salary = f"{j.get('annualSalaryMin','')}-{j.get('annualSalaryMax','')} {j.get('salaryCurrency','')}".strip()
            out.append(_norm("jobicy", jid, j.get("jobTitle"), j.get("companyName"),
                             j.get("jobGeo"), salary, j.get("url"), j.get("pubDate"),
                             j.get("jobDescription"), [j.get("jobIndustry"), j.get("jobType")]))
    print(f"[jobicy] {len(out)} jobs")
    return out


def fetch_himalayas(terms):
    """Himalayas public search API. Defensive about field names."""
    out, seen = [], set()
    for term in terms:
        try:
            data = _get("https://himalayas.app/jobs/api/search",
                        {"query": term, "limit": 20}).json()
        except Exception as e:
            print(f"[himalayas] '{term}' failed: {e}"); continue
        jobs = data.get("jobs", data if isinstance(data, list) else [])
        for j in jobs:
            if not isinstance(j, dict): continue
            company = j.get("companyName") or (j.get("company") or {}).get("name") if isinstance(j.get("company"), dict) else j.get("company")
            url = j.get("applicationLink") or j.get("url") or j.get("guid") or j.get("link")
            jid = j.get("guid") or j.get("id") or url
            if jid is None or jid in seen: continue
            seen.add(jid)
            locs = j.get("locationRestrictions") or []
            if isinstance(locs, str): locs = [locs]
            location = ", ".join([str(x) for x in locs]) if locs else "Worldwide"
            desc = j.get("description") or j.get("excerpt") or ""
            out.append(_norm("himalayas", jid, j.get("title"), company, location, "",
                             url, j.get("pubDate") or j.get("publishedAt"), desc,
                             j.get("categories") or []))
    print(f"[himalayas] {len(out)} jobs")
    return out


def fetch_getonbrd(terms):
    """Get on Board public search (LATAM-focused). Keeps only remote roles."""
    out, seen = [], set()
    for term in terms:
        try:
            data = _get("https://www.getonbrd.com/api/v0/search/jobs",
                        {"query": term, "per_page": 50}).json()
        except Exception as e:
            print(f"[getonbrd] '{term}' failed: {e}"); continue
        for item in data.get("data", []):
            a = item.get("attributes", {}) or {}
            is_remote = a.get("remote", True)
            if not is_remote:
                continue
            jid = item.get("id")
            if jid is None or jid in seen: continue
            seen.add(jid)
            slug = a.get("slug") or jid
            url = (item.get("links") or {}).get("public_url") or f"https://www.getonbrd.com/jobs/{slug}"
            desc = " ".join(str(a.get(k, "")) for k in ("description", "functions", "benefits", "desirable"))
            salary = ""
            if a.get("min_salary") or a.get("max_salary"):
                salary = f"{a.get('min_salary','')}-{a.get('max_salary','')} USD".strip()
            out.append(_norm("getonbrd", jid, a.get("title"), a.get("company_name"),
                             "Latin America Remote", salary, url,
                             a.get("published_at"), desc, [a.get("category_name")]))
    print(f"[getonbrd] {len(out)} jobs")
    return out


def fetch_wwr_rss(feeds):
    """We Work Remotely category RSS feeds (public)."""
    out, seen = [], set()
    for feed in feeds:
        try:
            xml = _get(feed).content
            root = ET.fromstring(xml)
        except Exception as e:
            print(f"[wwr] '{feed}' failed: {e}"); continue
        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            if not link or link in seen: continue
            seen.add(link)
            raw_title = (item.findtext("title") or "").strip()
            company, title = "", raw_title
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            region = item.findtext("region") or ""
            out.append(_norm("wwr", link, title, company, region, "",
                             link, item.findtext("pubDate"),
                             item.findtext("description"), []))
    print(f"[wwr] {len(out)} jobs")
    return out


# ---------------- Per-company ATS boards ----------------

def fetch_ashby(orgs):
    out = []
    for org in orgs:
        try:
            jobs = _get(f"https://api.ashbyhq.com/posting-api/job-board/{quote(org, safe='')}",
                        {"includeCompensation": "true"}).json().get("jobs", [])
        except Exception as e:
            print(f"[ashby] '{org}' failed: {e}"); continue
        for j in jobs:
            loc = j.get("location") or ("Remote" if j.get("isRemote") else "")
            out.append(_norm("ashby", j.get("id"), j.get("title"), org, loc, "",
                             j.get("jobUrl") or j.get("applyUrl"), j.get("publishedAt"),
                             j.get("descriptionPlain") or j.get("descriptionHtml"),
                             [j.get("department"), j.get("team")]))
        print(f"[ashby] '{org}': {len(jobs)} jobs")
    return out


def fetch_greenhouse(orgs):
    out = []
    for org in orgs:
        try:
            jobs = _get(f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs",
                        {"content": "true"}).json().get("jobs", [])
        except Exception as e:
            print(f"[greenhouse] '{org}' failed: {e}"); continue
        for j in jobs:
            desc = clean_html(html.unescape(j.get("content", "")))
            loc = (j.get("location") or {}).get("name", "")
            out.append(_norm("greenhouse", j.get("id"), j.get("title"), org, loc, "",
                             j.get("absolute_url"), j.get("updated_at"), desc, []))
        print(f"[greenhouse] '{org}': {len(jobs)} jobs")
    return out


def fetch_lever(orgs):
    out = []
    for org in orgs:
        try:
            jobs = _get(f"https://api.lever.co/v0/postings/{org}", {"mode": "json"}).json()
        except Exception as e:
            print(f"[lever] '{org}' failed: {e}"); continue
        for j in jobs:
            cats = j.get("categories", {}) or {}
            loc = cats.get("location", "")
            if j.get("workplaceType"): loc = (loc + " " + j["workplaceType"]).strip()
            out.append(_norm("lever", j.get("id"), j.get("text"), org, loc, "",
                             j.get("hostedUrl"), j.get("createdAt"),
                             j.get("descriptionPlain") or j.get("description"),
                             [cats.get("team"), cats.get("commitment")]))
        print(f"[lever] '{org}': {len(jobs)} jobs")
    return out


# ---------------- Orchestration ----------------

def fetch_all(cfg):
    jobs, src = [], cfg.get("sources", {})
    if src.get("remotive_terms"):   jobs += fetch_remotive(src["remotive_terms"])
    if src.get("remoteok"):         jobs += fetch_remoteok()
    if src.get("jobicy_geos"):      jobs += fetch_jobicy(src["jobicy_geos"])
    if src.get("himalayas_terms"):  jobs += fetch_himalayas(src["himalayas_terms"])
    if src.get("getonbrd_terms"):   jobs += fetch_getonbrd(src["getonbrd_terms"])
    if src.get("wwr_feeds"):        jobs += fetch_wwr_rss(src["wwr_feeds"])
    if src.get("ashby"):            jobs += fetch_ashby(src["ashby"])
    if src.get("greenhouse"):       jobs += fetch_greenhouse(src["greenhouse"])
    if src.get("lever"):            jobs += fetch_lever(src["lever"])
    uniq = {}
    for j in jobs:
        uniq[j["key"]] = j
    return list(uniq.values())
