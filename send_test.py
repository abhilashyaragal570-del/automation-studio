import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
URL = "http://127.0.0.1:8000"

args = sys.argv[1:]
token = os.getenv("WEBHOOK_TOKEN", "")
if args and args[0] == "--bad-token":
    token = "wrong-token"
    args = args[1:]
text = " ".join(args) or "Hello, I would like a quote and a demo for 50 licenses. Please reply by Friday. Regards, Meera"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Webhook-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


code, data = call("POST", "/webhook/email", {"text": text})
print("webhook:", code, data)
if code != 202:
    sys.exit(1)

job_id = data["job_id"]
for _ in range(30):
    time.sleep(1)
    code, job = call("GET", "/jobs/" + str(job_id))
    print("job", job_id, "->", job["status"])
    if job["status"] in ("done", "failed"):
        print(job)
        break