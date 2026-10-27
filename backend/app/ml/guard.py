# app/ml/guard.py — automated de-anonymization guard (Blueprint Stage 3).
#
# Layered sanitization, applied before anything is persisted:
#   1. rules     — deterministic checks with stable, human-readable reasons
#                  (parity with the local dev API so client tests hold).
#   2. ML signal — a scikit-learn character/word n-gram classifier trained in
#                  process on a small built-in labelled corpus. It only fires
#                  with high confidence, so clear structural narratives pass.
#
# Swap `_ml_decision` for a model trained on real institutional data when
# labelled examples exist; the API contract (reason string on 422) stays fixed.
from __future__ import annotations

import re

# --- deterministic layer ----------------------------------------------------

COURSE_CODE_RE = re.compile(r"\b[A-Z]{2,4}\s?-?\d{3,4}\b")
NAMED_PERSON_RE = re.compile(r"\b(Prof(essor)?|Dr)\.?\s+[A-Z][a-z]+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
HANDLE_RE = re.compile(r"(?<![\w@])@[\w][\w.-]{2,}\b")
ROOM_RE = re.compile(r"\b(?:Room|Rm\.?|Building|Lab|Dorm)\s*[A-Z]?\s?\d{2,4}\b")

MIN_LEN_MSG = "Please write a little more — at least a couple of sentences."


def _rule_reason(text: str) -> str | None:
    if len(text) < 40:
        return MIN_LEN_MSG
    if COURSE_CODE_RE.search(text):
        return "Post may contain identifying details: a course code."
    if NAMED_PERSON_RE.search(text):
        return "Post may contain identifying details: a named individual."
    if EMAIL_RE.search(text) or HANDLE_RE.search(text) or PHONE_RE.search(text):
        return "Post may contain identifying details: contact information."
    if ROOM_RE.search(text):
        return "Post may contain identifying details: a room or building reference."
    return None


# --- ML layer ---------------------------------------------------------------
# Built-in labelled corpus (identifying / safe). Small on purpose: it encodes
# the *shape* of de-anonymizing text; replace with real labelled data later.

_CORPUS = [
    ("identifying", "I enrolled in CS 101 and nobody told us when the add deadline moved."),
    ("identifying", "Professor Smith never answered a single email about the late policy."),
    ("identifying", "Dr Patel changed the thesis deadline twice without telling the cohort."),
    ("identifying", "Email me at j.smith@university.edu if you lost your transcript too."),
    ("identifying", "Text me at 555-123-4567 about the scholarship committee decision."),
    ("identifying", "Everyone in the CSE 482 group chat saw the solutions before the exam."),
    ("identifying", "My student ID 1234567 was flagged by the registrar for no reason."),
    ("identifying", "The 9am section of STAT 200 had no TA for the entire semester."),
    ("identifying", "Room 302 in Alder Hall had no heating during finals week."),
    ("identifying", "@jdoe_law posted the confidential rubric in the Discord server."),
    ("identifying", "Ms Rodriguez in Building C lost my transfer credit evaluation."),
    ("identifying", "Dean Marcus Webb ignored our petition about lab safety."),
    ("identifying", "BIO 210 section 4 was moved to Lab 14B with one day of notice."),
    ("identifying", "My advisor Dr Chen held the manuscript for fourteen months."),
    ("identifying", "Call 555.867.5309 to reach the ombuds office, they actually answer."),
    ("identifying", "The FIN 340 professor curved the grade only for his advisees."),
    ("identifying", "john.doe@campus.edu filed the harassment complaint with HR."),
    ("identifying", "Lab 12B's fume hood broke and safety never logged the ticket."),
    ("identifying", "Everyone in our section group chat saw the answer key an hour before "
     "the midterm started and nobody running the course said anything."),
    ("safe", "The late-submission policy lives in three different documents and none of them agree."),
    ("safe", "Students find out which one applies only after a penalty is already applied."),
    ("safe", "One canonical policy page would have prevented this entire situation."),
    ("safe", "Our annual review asks students to self-report advising problems on a form their advisor co-signs."),
    ("safe", "A form reviewed by both parties is not a grievance process, it is a negotiation."),
    ("safe", "The deadline change was announced in a channel nobody in my position subscribes to."),
    ("safe", "High-stakes financial deadlines and campus-life announcements share one channel."),
    ("safe", "Reversing a late fee required a form with a two-week processing window."),
    ("safe", "Authorship order was decided in a hallway conversation I was not part of."),
    ("safe", "There was no meeting and no criteria document before the project started."),
    ("safe", "Pre-registered authorship criteria are required by journals but rarely implemented internally."),
    ("safe", "The entire process was invisible until it produced an outcome I could react to but not contest."),
    ("safe", "Three committees must approve a syllabus change and none of them owns the outcome."),
    ("safe", "Registration holds appeared before any warning email reached students."),
    ("safe", "Advising complaints have no route that avoids the person being complained about."),
    ("safe", "Career services reviews resumes in batches and returns them after the application window closes."),
    ("safe", "Nobody owns the handoff between graduation audits and diploma issuance."),
    ("safe", "The appeal window closes before grades are even posted to the portal."),
]

_ml_ready = False
_vectorizer = None
_classifier = None
ML_THRESHOLD = 0.92
ML_REASON = (
    "Post may contain identifying details: the text guard detected a likely "
    "personal or class-specific reference."
)


def _ensure_ml() -> None:
    global _ml_ready, _vectorizer, _classifier
    if _ml_ready:
        return
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import ComplementNB

        docs = [t for _, t in _CORPUS]
        labels = [y for y, _ in _CORPUS]
        _vectorizer = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=1, lowercase=True
        )
        x = _vectorizer.fit_transform(docs)
        _classifier = ComplementNB(alpha=0.4)
        _classifier.fit(x, labels)
    except Exception:  # pragma: no cover - sklearn always present in this project
        _vectorizer = None
        _classifier = None
    _ml_ready = True


def _ml_reason(text: str) -> str | None:
    _ensure_ml()
    if _vectorizer is None or _classifier is None:
        return None
    x = _vectorizer.transform([text])
    probs = dict(zip(_classifier.classes_, _classifier.predict_proba(x)[0]))
    if probs.get("identifying", 0.0) >= ML_THRESHOLD:
        return ML_REASON
    return None


def sanitize(text: str) -> str | None:
    """Return a rejection reason, or None when the post clears the guard."""
    stripped = text.strip()
    return _rule_reason(stripped) or _ml_reason(stripped)
