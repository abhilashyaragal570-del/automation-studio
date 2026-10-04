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

Optional: set `DB_PATH` to store the database file somewhere else, for example on a hosted disk. By default it is `studio.db` in the
- `GET /export.csv` download the email history as a CSV file (needs the login)