import re
import html
import datetime

def today():
    return datetime.date.today().isoformat()

def days_ago(iso_date):
    try:
        d = datetime.date.fromisoformat(iso_date)
    except Exception:
        return 9999
    return (datetime.date.today() - d).days

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def clean_html(text):
    if not text:
        return ""
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return _WS.sub(" ", text).strip()

def norm(text):
    return _WS.sub(" ", (text or "").lower()).strip()
