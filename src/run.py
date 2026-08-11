"""Orchestrator. Usage: python -m src.run --mode daily|weekly"""
import argparse
import os
import yaml

from . import fetch, score, store, digest, coverletter
from .util import today


def load_cfg():
    with open("config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_profile(cfg):
    path = cfg.get("profile_path", "data/profile.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def write_outputs(md):
    os.makedirs("data", exist_ok=True)
    with open("data/digest-latest.md", "w", encoding="utf-8") as f:
        f.write(md + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def run_daily(cfg):
    profile = load_profile(cfg)
    st = store.load()

    fetched = fetch.fetch_all(cfg)
    print(f"[run] fetched {len(fetched)} unique jobs")
    fetched_by_key = {j["key"]: j for j in fetched}

    evaluated = score.evaluate(fetched, cfg)  # passes region + min_match, sorted
    print(f"[run] {len(evaluated)} passed region + min_match")

    new_keys = []
    for job, sc, reasons, gaps in evaluated:
        is_new = store.upsert(st, job, sc, reasons, gaps)
        if is_new:
            new_keys.append(job["key"])

    # Optional cover-letter drafts for NEW high matches
    high = cfg["thresholds"]["high_match"]
    if cfg.get("cover_letters", {}).get("enabled"):
        budget = cfg["cover_letters"]["max_per_run"]
        for key in new_keys:
            if budget <= 0:
                break
            rec = st[key]
            if rec["score"] < high:
                continue
            full = fetched_by_key.get(key)
            if not full:
                continue
            text = coverletter.draft(full, profile, cfg)
            if text:
                path = coverletter.save(key, text)
                rec["cover_letter"] = True
                print(f"[cover] drafted -> {path}")
                budget -= 1

    store.mark_stale(st, cfg["digest"]["stale_after_days"])

    # Build digest lists
    new_high = [st[k] for k in new_keys if st[k]["score"] >= high]
    new_other = [st[k] for k in new_keys if st[k]["score"] < high]
    new_high.sort(key=lambda r: r["score"], reverse=True)
    new_other.sort(key=lambda r: r["score"], reverse=True)
    still_open = sorted(
        [r for r in st.values()
         if r["status"] in ("new", "reopened") and r["key"] not in new_keys],
        key=lambda r: r["score"], reverse=True,
    )

    md = digest.build_daily_md(new_high, new_other, still_open, cfg)
    write_outputs(md)
    store.save(st)

    subject = f"{cfg['digest']['title']}: {len(new_keys)} new ({today()})"
    from .email_send import send
    send(subject, md, digest.md_to_basic_html(md))
    print(f"[run] daily done. new={len(new_keys)} tracked={len(st)}")


def run_weekly(cfg):
    st = store.load()
    md = digest.build_weekly_md(st, cfg)
    write_outputs(md)
    from .email_send import send
    send(f"{cfg['digest']['title']}: weekly summary ({today()})",
         md, digest.md_to_basic_html(md))
    print("[run] weekly done.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    args = ap.parse_args()
    cfg = load_cfg()
    if args.mode == "daily":
        run_daily(cfg)
    else:
        run_weekly(cfg)


if __name__ == "__main__":
    main()
