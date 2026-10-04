import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import db
import core
import worker

load_dotenv(Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
APP_USER = os.getenv("APP_USER", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
MIN_CHARS = 20
MAX_CHARS = 5000
MAX_QUEUE = 20

security = HTTPBasic(auto_error=False)


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    worker.start()
    yield
    worker.stop()


app = FastAPI(lifespan=lifespan)


class EmailIn(BaseModel):
    text: str


def require_login(credentials: HTTPBasicCredentials = Depends(security)):
    if not APP_USER or not APP_PASSWORD:
        raise HTTPException(status_code=503, detail="Login is not configured.")
    ok = (credentials is not None
          and secrets.compare_digest(credentials.username.encode(), APP_USER.encode())
          and secrets.compare_digest(credentials.password.encode(), APP_PASSWORD.encode()))
    if not ok:
        raise HTTPException(status_code=401, detail="Login required.",
                            headers={"WWW-Authenticate": "Basic"})


def login_or_token(credentials: HTTPBasicCredentials = Depends(security),
                   x_webhook_token: str = Header(default="")):
    if (WEBHOOK_TOKEN and x_webhook_token
            and secrets.compare_digest(x_webhook_token.encode(), WEBHOOK_TOKEN.encode())):
        return
    require_login(credentials)


def check_length(text):
    if len(text) < MIN_CHARS:
        raise HTTPException(status_code=400, detail="Email is too short (minimum 20 characters).")
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=400, detail="Email is too long (maximum 5000 characters).")


@app.get("/", dependencies=[Depends(require_login)])
def home():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/status", dependencies=[Depends(require_login)])
def status():
    return {"mock": core.MOCK_MODE, "calls_today": db.calls_today(), "cap": core.DAILY_CAP,
            "queued": db.queued_count()}


@app.get("/emails", dependencies=[Depends(require_login)])
def emails():
    return db.list_emails()


@app.get("/jobs", dependencies=[Depends(require_login)])
def jobs():
    return db.list_jobs()


@app.get("/jobs/{job_id}", dependencies=[Depends(login_or_token)])
def job_detail(job_id: int):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/stats", dependencies=[Depends(require_login)])
def stats():
    return db.stats()


@app.post("/process", dependencies=[Depends(require_login)])
def process(body: EmailIn):
    text = body.text.strip()
    check_length(text)
    try:
        result, mock = core.process_email(text)
    except core.QuotaCapReached as e:
        raise HTTPException(status_code=429, detail=str(e))
    if result is None:
        raise HTTPException(status_code=502, detail="The AI call failed. Try again later.")
    result["id"] = db.save_email(text, result, mock)
    result["mock"] = mock
    return result


@app.post("/webhook/email", status_code=202)
def webhook_email(body: EmailIn, x_webhook_token: str = Header(default="")):
    if not WEBHOOK_TOKEN:
        raise HTTPException(status_code=503, detail="Webhook is not configured.")
    if not secrets.compare_digest(x_webhook_token.encode(), WEBHOOK_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid webhook token.")
    text = body.text.strip()
    check_length(text)
    if db.queued_count() >= MAX_QUEUE:
        raise HTTPException(status_code=429, detail="Queue is full. Try again later.")
    job_id = db.create_job(text, "webhook")
    logging.getLogger("webhook").info("job %s queued", job_id)
    return {"job_id": job_id, "status": "queued"}