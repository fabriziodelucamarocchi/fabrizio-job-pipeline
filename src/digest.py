"""Build the daily/weekly digest as Markdown + HTML."""
from .util import today


def _job_line_md(rec, note=""):
    tag = "HIGH" if rec["score"] >= 50 else "match"
    sal = f" | {rec['salary']}" if rec.get("salary") else ""
    loc = f" | {rec['location']}" if rec.get("location") else ""
    gaps = ""
    if rec.get("gaps"):
        gaps = f"\n    - tools required: {', '.join(rec['gaps'])}"
    cl = " | cover-letter draft ready" if rec.get("cover_letter") else ""
    return (f"- **[{rec['score']} {tag}] {rec['title']}** - {rec['company']}"
            f"{loc}{sal}{cl}\n"
            f"    - {rec['url']}{gaps}{note}")


def build_daily_md(new_high, new_other, still_open, cfg):
    lines = [f"# {cfg['digest']['title']} - daily digest ({today()})", ""]
    if not (new_high or new_other):
        lines.append("_No new matches today. Existing open roles below._\n")
    if new_high:
        lines.append(f"## New HIGH matches ({len(new_high)})")
        lines += [_job_line_md(r) for r in new_high]
        lines.append("")
    if new_other:
        lines.append(f"## New other matches ({len(new_other)})")
        lines += [_job_line_md(r) for r in new_other]
        lines.append("")
    if still_open:
        lines.append(f"## Still open - not yet applied ({len(still_open)})")
        lines += [_job_line_md(r) for r in still_open[: cfg['digest']['max_items']]]
        lines.append("")
    lines.append("---")
    lines.append("_Apply-ready but nothing is sent automatically. Review, then apply yourself._")
    return "\n".join(lines)


def build_weekly_md(store, cfg):
    from .util import days_ago
    new_week = [r for r in store.values() if days_ago(r.get("first_seen", "")) <= 7]
    by_status = {}
    for r in store.values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    lines = [f"# {cfg['digest']['title']} - weekly summary ({today()})", ""]
    lines.append(f"- Tracked total: **{len(store)}**")
    lines.append(f"- New this week: **{len(new_week)}**")
    lines.append("- By status: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
    lines.append("")
    top = sorted(new_week, key=lambda r: r["score"], reverse=True)[:cfg['digest']['max_items']]
    if top:
        lines.append("## Top new roles this week")
        lines += [_job_line_md(r) for r in top]
    return "\n".join(lines)


def md_to_basic_html(md):
    # minimal MD -> HTML for the email body
    import html as _h
    out = []
    for line in md.splitlines():
        s = _h.escape(line)
        if line.startswith("# "):
            out.append(f"<h2>{s[2:]}</h2>")
        elif line.startswith("## "):
            out.append(f"<h3>{s[3:]}</h3>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p style='margin:4px 0'>{s}</p>")
    return ("<div style=\"font-family:Arial,Helvetica,sans-serif;"
            "font-size:14px;color:#1b1b1b\">" + "\n".join(out) + "</div>")
