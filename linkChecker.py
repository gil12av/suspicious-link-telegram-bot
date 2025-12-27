# =============================================================================
# מנוע ניתוח קישורים לבדיקת אבטחה
# קובץ זה מכיל את הלוגיקה לבדיקת אבטחת קישורים:
# - חישוב גיל דומיין באמצעות WHOIS
# - בדיקת תקפות תעודת SSL
# - ספירת הפניות מחדש (redirects)
# - הרחבת קישורים מקוצרים
# - בדיקה מול מסדי איומים מקומיים
# - יצירת המלצות אבטחה מבוססות כללים
# =============================================================================

import datetime, socket, ssl, requests, os
from urllib.parse import urlparse
import whois
from utils import check_local_feeds, normalize_url, expand_url
from requests.exceptions import SSLError as RequestsSSLError, ConnectionError, Timeout

REQUEST_TIMEOUT = 10

def extract_domain(url: str) -> str:
    p = urlparse(url if "://" in url else "http://" + url)
    return p.hostname or p.path.split("/")[0]

def get_domain_age_days(domain: str):
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = next((d for d in creation_date if d), None)
        if not creation_date:
            return None
        if getattr(creation_date, "tzinfo", None):
            creation_date = creation_date.replace(tzinfo=None)
        return (datetime.datetime.now() - creation_date).days
    except Exception:
        return None

def check_ssl_valid(domain: str):
    """
    בדיקת SSL אמינה באמצעות בקשת HTTPS אמיתית עם אימות תעודה (certifi).
    מחזיר:
      True  – החיבור בוצע בהצלחה עם אימות תעודה
      False – יש תעודה לא תקפה / כשל אימות
      None  – לא ניתן לבדוק (Timeout/רשת/חסימה)
    """
    try:
        # HEAD לא תמיד מותר, אז נשתמש ב‑GET קטן עם stream כדי לא להוריד תוכן
        r = requests.get(f"https://{domain}", timeout=REQUEST_TIMEOUT,
                         allow_redirects=True, headers={"User-Agent": "OneClickSafe/1.0"},
                         stream=True)
        r.close()
        return True
    except (RequestsSSLError, requests.exceptions.SSLError):
        return False
    except (Timeout, ConnectionError):
        return None
    except Exception:
        return None

def count_redirects(url: str):
    try:
        r = requests.get(url, allow_redirects=True, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "OneClickSafe/1.0"})
        return len(r.history)
    except Exception:
        return None

def analyze_link(url: str):
    # נרמול הלינק והרחבת קיצור אם יש
    url_norm = normalize_url(url)
    final_url, redirects_from_expand = expand_url(url_norm)

    domain = extract_domain(final_url)
    age_days = get_domain_age_days(domain)
    ssl_ok = check_ssl_valid(domain)
    # אם ההרחבה כבר ספרה רידיירקטים – נשתמש בזה, אחרת נבדוק כרגיל
    redirects = redirects_from_expand or count_redirects(final_url)
    feed_hits = check_local_feeds(final_url)

    # ניסוח המלצה בצורה בטוחה ל-None
    flags = []
    
    if age_days is None:
        flags.append("Domain age is unknown")
    elif age_days < 30:
        flags.append("This is an new domain")

    if ssl_ok is False:
        flags.append("SSL is invalid/does not exist")
    elif ssl_ok is None:
        flags.append("SSL condition is unknown")

    if redirects is None:
        flags.append("Redircet number is unknown")
    elif redirects >= 3:
        flags.append(f"Too many redirects({redirects})")

    if feed_hits:
        flags.append(f"find in phising data {', '.join(feed_hits)}")

    if not flags:
        recommendation = "✅ The link looking good according to existing tests." 
    else:
        recommendation = "⚠️ " + " · ".join(flags) + ", It is recommended to take precautions."

    return {
        "domain": domain,
        "normalized_url": normalize_url(url),
        "domain_age_days": age_days,
        "ssl_valid": ssl_ok,
        "num_redirects": redirects,
        "feeds_hit": feed_hits,        # רשימת מקורות אם נמצאה התאמה
        "recommendation": recommendation
    }
