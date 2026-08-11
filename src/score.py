"""Transparent keyword scoring against Fabrizio's profile + region + exclusions."""
from .util import norm


def region_ok(location, region_allow):
    loc = norm(location)
    if not loc:
        return True
    for marker in ("worldwide", "anywhere", "global"):
        if marker in loc:
            return True
    for allow in region_allow:
        if allow in loc:
            return True
    return False


def excluded(job, exclude_titles):
    """v2: drop the job if any exclude term appears in its TITLE."""
    title = norm(job.get("title", ""))
    return any(x in title for x in exclude_titles)


def score_job(job, cfg):
    text = norm(job.get("title", "") + " " + job.get("description", "") + " " + " ".join(job.get("tags", [])))
    title = norm(job.get("title", ""))

    matched_sum = 0
    reasons = []
    for kw, w in cfg["keywords"].items():
        if kw in text:
            matched_sum += w
            reasons.append(kw)

    title_bonus = 0
    for t in cfg["target_titles"]:
        if t in title:
            title_bonus = 15
            reasons.insert(0, f"title~{t}")
            break

    raw = title_bonus + matched_sum * 3
    score = int(min(raw, 100))

    gaps = [tool for tool in cfg.get("tools_watchlist", []) if tool in text]
    return score, reasons, gaps


def evaluate(jobs, cfg):
    """Return list of (job, score, reasons, gaps) passing exclusion + region + min_match.
    Per-company ATS boards (ashby/greenhouse/lever) skip the region filter: if Fabrizio
    is monitoring that company, he wants to see all its remote roles and judge himself.
    """
    region_allow = [a.lower() for a in cfg.get("region_allow", [])]
    exclude_titles = [e.lower() for e in cfg.get("exclude_titles", [])]
    min_match = cfg["thresholds"]["min_match"]
    ats_sources = {"ashby", "greenhouse", "lever"}
    results = []
    for j in jobs:
        if excluded(j, exclude_titles):
            continue
        if j.get("source") not in ats_sources and not region_ok(j.get("location", ""), region_allow):
            continue
        score, reasons, gaps = score_job(j, cfg)
        if score < min_match:
            continue
        results.append((j, score, reasons, gaps))
    results.sort(key=lambda x: x[1], reverse=True)
    return results
