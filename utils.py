# =============================================================================
# כלי עזר כלליים לעיבוד קישורים וניהול נתונים
# קובץ זה מכיל פונקציות שירות לבוט:
# - זיהוי והוצאת קישורים מהודעות טקסט
# - נורמליזציה של קישורים (הוספת סכימה, טיפול ב-IDN)
# - הרחבת קישורים מקוצרים
# - הורדת ועדכון מסדי איומים (OpenPhish, URLhaus)
# - בדיקה מקומית מול מסדי איומים שהורדו
# =============================================================================

# utils.py
import os, time, csv, requests, re
from urllib.parse import urlsplit, urlunsplit


# זיהוי והוצאת לינקים מהודעה – גם בלי http/https
BARE_URL_RE = re.compile(
    r'(?ix)\b('
    r'(?:https?://|ftp://|file://|//)?'          # סכימה אופציונלית (או //)
    r'(?:www\.)?'                                # www. אופציונלי
    r'(?:[a-z0-9-]{1,63}\.)+[a-z]{2,63}'         # דומיין
    r'(?:/[^\s<>"]*)?'                           # נתיב אופציונלי
    r')'
)

_SCHEME_RE = re.compile(r'^(?i)(?:[a-z][a-z0-9+\-.]*:)?//')

FEEDS_DIR = os.path.join(os.path.dirname(__file__), "feeds")
OPENPHISH_URL = "https://openphish.com/feed.txt"
URLHAUS_URL   = "https://urlhaus.abuse.ch/downloads/csv/"
TTL_SECONDS   = 60 * 30   # רענון כל חצי שעה

os.makedirs(FEEDS_DIR, exist_ok=True)
OPENPHISH_PATH = os.path.join(FEEDS_DIR, "openphish.txt")
URLHAUS_PATH   = os.path.join(FEEDS_DIR, "urlhaus.csv")

def _fresh(path: str, ttl: int) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path) < ttl)

def refresh_openphish(ttl: int = TTL_SECONDS) -> str:
    if not _fresh(OPENPHISH_PATH, ttl):
        r = requests.get(OPENPHISH_URL, timeout=15)
        r.raise_for_status()
        with open(OPENPHISH_PATH, "w", encoding="utf-8") as f:
            f.write(r.text)
    return OPENPHISH_PATH

def refresh_urlhaus(ttl: int = TTL_SECONDS) -> str:
    if not _fresh(URLHAUS_PATH, ttl):
        r = requests.get(URLHAUS_URL, timeout=20)
        r.raise_for_status()
        with open(URLHAUS_PATH, "w", encoding="utf-8", newline="") as f:
            f.write(r.text)
    return URLHAUS_PATH

def is_url(text: str) -> bool:
    return bool(extract_urls(text))

def extract_urls(text: str) -> list[str]:
    # מסיר תווים עוטפים נפוצים <>"" ומחזיר רשימת מועמדים
    candidates = [m.group(1).strip('<>"') for m in BARE_URL_RE.finditer(text)]
    # מסנן טוקנים שמכילים רווחים/תוים בעייתיים
    return [c for c in candidates if ' ' not in c]


def normalize_url(raw: str, default_scheme: str = "https") -> str:
    if not raw:
        return raw
    raw = raw.strip().strip('<>"\'')
    # אם מתחיל ב-// – נצרף סכימה
    if raw.startswith("//"):
        raw = f"{default_scheme}:{raw}"
    # אם אין סכימה בכלל – נוסיף
    if not _SCHEME_RE.match(raw):
        raw = f"{default_scheme}://{raw}"

    # פירוק והרכבה כדי לטפל ב-IDN
    parts = urlsplit(raw)
    netloc = parts.netloc.encode("idna").decode("ascii") if parts.netloc else parts.netloc
    # הורדת נקודות/סלאשים כפולים מיותרים ב-path
    path = re.sub(r"/{2,}", "/", parts.path or "")
    return urlunsplit((parts.scheme, netloc, path, parts.query, parts.fragment))


def expand_url(url: str, timeout: float = 5.0, max_redirects: int = 5):
    """
    מחזיר (final_url, num_redirects). לא זורק חריגות – במקרה תקלה מחזיר (url, 0)
    """
    try:
        session = requests.Session()
        session.max_redirects = max_redirects
        # נתחיל ב-HEAD כדי לא למשוך תוכן מיותר
        r = session.head(url, allow_redirects=True, timeout=timeout)
        final = r.url
        redirects = len(r.history)
        # אם לא היו רידיירקטים ובכל זאת זה שירות קיצור, ננסה GET קצר
        if redirects == 0 and any(s in url.lower() for s in ("bit.ly", "tinyurl", "t.co", "goo.gl", "ow.ly", "buff.ly")):
            r = session.get(url, allow_redirects=True, timeout=timeout, stream=True)
            final = r.url
            redirects = len(r.history)
        return final, redirects
    except Exception:
        return url, 0


def check_in_openphish(url: str) -> bool:
    path = refresh_openphish()
    norm = normalize_url(url)
    # OpenPhish הוא רשימת URLים מלאים – נשווה גם על בסיס התחלה (יש לפעמים query שונים)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            u = line.strip()
            if not u:
                continue
            u_norm = normalize_url(u)
            if norm == u_norm or norm.startswith(u_norm):
                return True
    return False


def check_in_urlhaus(url: str) -> bool:
    path = refresh_urlhaus()
    norm = normalize_url(url)
    # URLhaus CSV – עמודה "url" לרוב בעמודה 2/3 (הפורמט משתנה, נטפל גמיש)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            # נסה למצוא עמודה שנראית כמו URL
            candidates = [c for c in row if c.startswith("http://") or c.startswith("https://")]
            for c in candidates:
                if norm == normalize_url(c) or norm.startswith(normalize_url(c)):
                    return True
    return False


def check_local_feeds(url: str):
    """מחזיר רשימת מקורות שבהם נמצא ה-URL (אם בכלל)"""
    hits = []
    try:
        if check_in_openphish(url):
            hits.append("OpenPhish")
    except Exception:
        pass
    try:
        if check_in_urlhaus(url):
            hits.append("URLhaus")
    except Exception:
        pass
    return hits
