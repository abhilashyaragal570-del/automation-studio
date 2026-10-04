import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import db

load_dotenv(Path(__file__).parent / ".env")

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
MODEL = os.getenv("MODEL", "models/gemini-3.6-flash")
DAILY_CAP = int(os.getenv("DAILY_CAP", "15"))
FENCE = chr(96) * 3

CATEGORIES = ["support", "sales", "billing", "spam", "other"]
URGENCIES = ["low", "medium", "high"]

_client = None


class QuotaCapReached(Exception):
    pass


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=60000),
        )
    return _client


def mock_result(text):
    t = text.lower()
    if any(w in t for w in ["winner", "free money", "click here", "lottery"]):
        category = "spam"
    elif any(w in t for w in ["invoice", "payment", "refund", "charge"]):
        category = "billing"
    elif any(w in t for w in ["pricing", "quote", "demo", "buy", "purchase"]):
        category = "sales"
    elif any(w in t for w in ["error", "broken", "not working", "help", "issue"]):
        category = "support"
    else:
        category = "other"
    urgent = any(w in t for w in ["urgent", "asap", "immediately", "today"])
    first_line = text.strip().splitlines()[0][:60] if text.strip() else ""
    return {
        "category": category,
        "urgency": "high" if urgent else "low",
        "sender_name": "Unknown (mock)",
        "topic": first_line,
        "deadline": "today" if "today" in t else "",
        "summary": "Mock summary: keyword-based result, no AI used.",
        "reply": "Hello,\n\nThank you for your message. We will get back to you soon.\n\nBest regards",
    }


def call_gemini(prompt):
    for attempt in range(3):
        if db.calls_today() >= DAILY_CAP:
            raise QuotaCapReached("Daily request cap reached.")
        db.log_call()
        try:
            response = get_client().models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            if response and response.text:
                return response.text
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print(f"Gemini attempt {attempt + 1} failed: {msg[:300]}")
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                raise QuotaCapReached("Google's free quota is used up. Try later.")
            time.sleep(3)
    return None


def clean(r):
    def s(key):
        return str(r.get(key) or "").strip()
    category = s("category").lower()
    urgency = s("urgency").lower()
    return {
        "category": category if category in CATEGORIES else "other",
        "urgency": urgency if urgency in URGENCIES else "low",
        "sender_name": s("sender_name"),
        "topic": s("topic"),
        "deadline": s("deadline"),
        "summary": s("summary"),
        "reply": s("reply"),
    }


def process_email(text):
    if MOCK_MODE:
        return clean(mock_result(text)), True

    prompt = f"""You are an email assistant. Read the email and reply with ONLY valid JSON in this format:
{{"category": "support|sales|billing|spam|other", "urgency": "low|medium|high", "sender_name": "", "topic": "", "deadline": "", "summary": "one sentence", "reply": "a short polite draft reply"}}

Rules:
- Use only information written in the email. If something is missing, use an empty string.
- Write the reply in the same language as the email.

EMAIL:
{text}"""

    raw = call_gemini(prompt)
    if not raw:
        return None, False
    raw = raw.strip().removeprefix(FENCE + "json").removeprefix(FENCE).removesuffix(FENCE).strip()
    try:
        return clean(json.loads(raw)), False
    except json.JSONDecodeError:
        return None, False