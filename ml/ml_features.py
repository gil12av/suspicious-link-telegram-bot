# =============================================================================
# מודול הפקת מאפיינים למודל למידת מכונה
# קובץ זה מכיל את הלוגיקה להפקת מאפיינים עבור המודל:
# - זיהוי מילות טריגר בעברית (פישינג והתחזות)
# - זיהוי קישורים מקוצרים
# - המרת מדדים טכניים (גיל דומיין, SSL, הפניות) למטריצה נומרית
# - מחלקה TechnicalFeatureExtractor לבניית מאפיינים משולבים
# =============================================================================

# ml/ml_features.py
from __future__ import annotations
import re
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

HE_TRIGGER_WORDS = [
    "ביט", "תשלום", "קנס", "החבילה", "דואר", "עמלה", "לאימות", "אימות", "החשבון שלך", "יחסם",
    "לחץ כאן", "עד 24 שעות", "השלם תשלום", "אשראי", "התחבר", "הזדהות"
]

URL_SHORTENERS = ("bit.ly", "tinyurl", "short.ly", "goo.gl", "t.co")

def contains_trigger_words(text: str) -> int:
    t = (text or "").lower()
    return int(any(w in t for w in HE_TRIGGER_WORDS))

def has_shortened_url(url: str) -> int:
    u = (url or "").lower()
    return int(any(s in u for s in URL_SHORTENERS))

# -----------------------------------------------------------
# ✅ פונקציות עזר (במקום lambda) — חובה כדי לאפשר שמירה עם joblib
# -----------------------------------------------------------

def extract_text(records):
    """מקבלת רשימת מילונים ומחזירה את שדה הטקסט בלבד."""
    return [r.get("text", "") for r in records]

def passthrough(records):
    """מחזירה את הרשומה כמו שהיא — עבור הפיצ'רים הטכניים."""
    return records


class TechnicalFeatureExtractor(BaseEstimator, TransformerMixin):
    """
    מקבל רשומות כבר אחרי ניתוח linkChecker (או דאטה אימון עם שדות טכניים).
    מצפה לדיקט עם המפתחות:
      - domain_age_days (int|None)
      - ssl_valid (True|False|None)
      - num_redirects (int|None)
      - feeds_hit (list[str])  -> in_feed = 1 אם לא ריק
      - text (str)
      - url (str)
    מחזיר מטריצה נומרית (np.array) בגודל [n_samples, k]
    """
    def fit(self, X, y=None): return self
    def transform(self, X):
        feats = []
        for rec in X:
            age = rec.get("domain_age_days")
            sslv = rec.get("ssl_valid")
            red  = rec.get("num_redirects")
            feeds= rec.get("feeds_hit") or []
            txt  = rec.get("text") or ""
            url  = rec.get("url") or ""

            age_n = -1 if age is None else int(age)
            ssl_n = -1 if sslv is None else (1 if sslv else 0)
            red_n = -1 if red is None else int(red)
            in_feed = 1 if len(feeds) > 0 else 0
            trig = contains_trigger_words(txt)
            short = has_shortened_url(url)

            feats.append([age_n, ssl_n, red_n, in_feed, trig, short])
        return np.array(feats, dtype=float)
