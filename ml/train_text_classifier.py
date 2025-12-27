# =============================================================================
# סקריפט אימון מודל סיווג טקסט לזיהוי פישינג
# קובץ זה מכיל את הלוגיקה לאימון המודל:
# - טעינת נתוני אימון בפורמט JSONL
# - בניית pipeline של scikit-learn עם TF-IDF ו-LogisticRegression
# - שילוב מאפיינים טקסטואליים וטכניים
# - אימון והערכת ביצועי המודל
# - שמירת המודל המאומן לקובץ joblib
# =============================================================================

# train_text_classifier.py

# 📌 מטרת הקובץ:
# קובץ זה אחראי על אימון המודל לזיהוי הודעות פישינג, התחזות או לגיטימיות.
# הוא משתמש בטקסט ההודעה ובמאפיינים טכניים של הלינק כדי ללמוד על תבניות התקפיות.
# התוצאה היא מודל מסוג Pipeline שמוכן לאינפרנס תוך שימוש ב-ml_infer.py.

import json
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from ml_features import TechnicalFeatureExtractor, extract_text, passthrough

# -----------------------------------------------------------
# 🚀 בניית ה-Pipeline שמשלב טקסט ופיצ'רים טכניים
# -----------------------------------------------------------

def get_pipeline():
    text_branch = Pipeline([
        ("extract_text", FunctionTransformer(extract_text, validate=False)),
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2)))
    ])

    tech_branch = Pipeline([
        ("extract", FunctionTransformer(passthrough, validate=False)),
        ("features", TechnicalFeatureExtractor())
    ])

    features = FeatureUnion([
        ("text", text_branch),
        ("tech", tech_branch)
    ])

    pipeline = Pipeline([
        ("features", features),
        ("scale", StandardScaler(with_mean=False)),  # נדרש עבור שילוב sparse+dense
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))
    ])

    return pipeline

# -----------------------------------------------------------
# 🧠 קריאת הדאטה והכנת קבוצות אימון/בדיקה
# -----------------------------------------------------------

def load_data(jsonl_path):
    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [json.loads(line.strip()) for line in f if line.strip()]
    X = records
    y = [r["label"] for r in records]
    return X, y

# -----------------------------------------------------------
# 🔁 פונקציית אימון ראשית
# -----------------------------------------------------------

def main():
    MODEL_PATH = Path(__file__).resolve().parent / "models" / "text_clf.joblib"
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    data_path = Path(__file__).resolve().parent.parent / "data" / "messages.jsonl"
    X, y = load_data(data_path)

    # split stratified לפי label כדי לוודא שכל כיתה מיוצגת ב-test
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)

    pipe = get_pipeline()
    pipe.fit(Xtr, ytr)

    yp = pipe.predict(Xte)

    # הצגת תוצאות: precision, recall, f1
    print("🔎 Model Performance Report:")
    print(classification_report(yte, yp, digits=3, zero_division=0))

    # שמירה של המודל המאומן
    joblib.dump(pipe, MODEL_PATH)
    print(f"✅ Model saved to: {MODEL_PATH}")

# -----------------------------------------------------------
if __name__ == "__main__":
    main()
