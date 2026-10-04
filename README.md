# AI Automation Studio

A small web app that reads incoming emails with Gemini. For each email it picks a category and urgency, pulls out the sender, topic and deadline, writes a short summary, and drafts a reply. Emails can be pasted into the web page or sent by another system through a webhook. Webhook emails go into a job queue and a background worker processes them one at a time.

## Features

- Paste an email into the page and get the result straight away
- Webhook endpoint with a secret token
- Job queue stored in SQLite, so a restart doesn't lose jobs
- Background worker with job status: queued, processing, done, failed
- Jobs log, email history and a dashboard that refresh every 3 seconds
- Daily Gemini request cap and a mock mode that uses no Gemini requests
- Retry button for failed jobs
- CSV export of the email history
- Search box on the email history
- "Clear finished" link that removes done and failed jobs from the Jobs log
- Login for the page and its data

## Project files

| File | Purpose |
|---|---|
| core.py | Gemini call, mock mode and daily cap |
| db.py | SQLite tables and queries |
| worker.py | Background job worker |
| main.py | FastAPI app and endpoints |
| index.html | Web page |
| send_test.py | Test script that calls the webhook |

## Setup

1. Create and activate a virtual environment:

```
python -m venv venv
venv\Scripts\activate
```

2. Install the packages:

```
pip install -r requirements.txt
```

3. Create a file named `.env` in the project folder with these lines:

```
MOCK_MODE=true
WEBHOOK_TOKEN=any-long-random-text
APP_USER=admin
APP_PASSWORD=a-long-random-password
GEMINI_API_KEY=your-gemini-api-key
```

Make a random token with:

```
python -c "import secrets; print(secrets.token_hex(16))"
```

Optional: set `DB_PATH` to store the database file somewhere else, for example on a hosted disk. By default it is `studio.db` in the project folder.

Never share `.env` or commit it. `.gitignore` already excludes it.

## Run

```
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

The page asks for the username and password from `.env`. The webhook does not use them. It uses only the `X-Webhook-Token` header.

With `MOCK_MODE=true` no Gemini requests are made and the results are fake. Set `MOCK_MODE=false` and restart for real results.

## Webhook

Send a POST request to `/webhook/email` with the header `X-Webhook-Token` set to your token:

```
curl -X POST http://127.0.0.1:8000/webhook/email -H "Content-Type: application/json" -H "X-Webhook-Token: YOUR_TOKEN" -d "{\"text\": \"Hello, I would like a quote for 50 licenses. Please reply by Friday.\"}"
```

The reply is `202` with a job ID:

```
{"job_id": 1, "status": "queued"}
```

Check the job with `GET /jobs/1`, sending the same `X-Webhook-Token` header. The status becomes `done` or `failed`.

| Code | Meaning |
|---|---|
| 202 | Job queued |
| 400 | Email too short (under 20 characters) or too long (over 5000) |
| 401 | Wrong token |
| 429 | Queue is full (20 jobs waiting) |
| 503 | WEBHOOK_TOKEN is not set on the server |

## Test

With the server running, open a second terminal and run:

```
python send_test.py
python send_test.py --bad-token
```

The first should end with `done`. The second should print `401`.

## Endpoints

- `GET /` web page (needs the login)
- `GET /status` mode, requests today and queue size (needs the login)
- `GET /emails` processed emails (needs the login)
- `GET /export.csv` download the email history as a CSV file (needs the login)
- `GET /jobs` job log (needs the login)
- `GET /jobs/{id}` one job (needs the login or the webhook token)
- `GET /stats` dashboard numbers (needs the login)
- `POST /process` process one email straight away (needs the login)
- `POST /jobs/{id}/retry` put a failed job back in the queue (needs the login)
- `POST /jobs/clear` remove done and failed jobs from the job log (needs the login)
- `POST /webhook/email` queue one email (needs the webhook token)