# =============================================================================
# מודול הסקת למידת מכונה לסיווג הודעות
# קובץ זה מכיל את הלוגיקה להרצת המודל המאומן:
# - טעינת מודל scikit-learn מהקובץ השמור
# - הכנת נתונים להסקה (טקסט + מאפיינים טכניים)
# - הרצת הסקה והחזרת תוצאות עם רמת ביטחון
# - טיפול בתרחישים שונים (דאטה חסרה, שגיאות)
# =============================================================================

# ml/ml_infer.py
from __future__ import annotations
import joblib
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "models" / "text_clf.joblib"
_model = None

def load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model

def ml_predict(message_text: str, url: str, agent_result: dict | None = None):
    """
    agent_result – התוצאה שאתה כבר מחזיר מ-analyze_link (domain_age_days, ssl_valid, num_redirects, feeds_hit)
    """
    m = load_model()
    rec = {
        "text": message_text or "",
        "url": url or "",
        "domain_age_days": None,
        "ssl_valid": None,
        "num_redirects": None,
        "feeds_hit": []
    }
    if agent_result:
        for k in ("domain_age_days", "ssl_valid", "num_redirects", "feeds_hit"):
            if k in agent_result:
                rec[k] = agent_result[k]

    proba = None
    if hasattr(m, "predict_proba"):
        # נחזיר גם probability אם אפשר
        proba = m.predict_proba([rec])[0]
        label = m.classes_[proba.argmax()]
        conf = float(proba.max())
    else:
        label = m.predict([rec])[0]
        conf = None

    reasons = []
    # אפשר להוסיף בהמשך הפקת "מילות טריגר שנמצאו" וכו'

    return {
        "label": label,
        "confidence": conf,
        "proba_vector": proba.tolist() if proba is not None else None,
        "reasons": reasons
    }
