"""Optional Claude-drafted cover letters. No-op unless ANTHROPIC_API_KEY is set.

Note: this uses the Anthropic API (console.anthropic.com), which is billed per token
and is SEPARATE from a Claude.ai subscription. Without a key, the pipeline still runs
and simply skips drafting.
"""
import os

COVER_DIR = os.path.join("data", "cover-letters")


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        print("[cover] anthropic package not installed; skipping")
        return None
    return anthropic.Anthropic(api_key=key)


def draft(job_full, profile_text, cfg):
    """job_full is the freshly fetched job (with full description). Returns text or None."""
    client = _client()
    if client is None:
        return None
    prompt = f"""Write a short, specific cover letter for this candidate and role.

CANDIDATE PROFILE:
{profile_text}

JOB:
Title: {job_full.get('title','')}
Company: {job_full.get('company','')}
Location: {job_full.get('location','')}
Description:
{job_full.get('description','')[:4500]}

Requirements:
- First person, as Fabrizio.
- Max 190 words. Professional, direct, no clichis, no "I am writing to apply".
- Tie 2-3 concrete strengths from the profile to what this role needs.
- English. Output ONLY the letter body, no salutation placeholders like [Name]."""
    try:
        msg = client.messages.create(
            model=cfg["cover_letters"]["model"],
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        print(f"[cover] draft failed for {job_full.get('key')}: {e}")
        return None


def save(job_key, text):
    os.makedirs(COVER_DIR, exist_ok=True)
    safe = job_key.replace(":", "_").replace("/", "_")
    path = os.path.join(COVER_DIR, f"{safe}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return path
