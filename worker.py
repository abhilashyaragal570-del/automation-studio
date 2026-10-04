import logging
import threading
import db
import core

log = logging.getLogger("worker")
_stop = threading.Event()
_thread = None


def handle(job):
    job_id = job["id"]
    log.info("job %s started (source=%s)", job_id, job["source"])
    try:
        result, mock = core.process_email(job["raw_text"])
        if result is None:
            db.finish_job(job_id, "failed", error="AI call failed or returned invalid JSON")
            log.warning("job %s failed: no valid result", job_id)
            return
        email_id = db.save_email(job["raw_text"], result, mock)
        db.finish_job(job_id, "done", email_id=email_id)
        log.info("job %s done (email %s, mock=%s)", job_id, email_id, mock)
    except core.QuotaCapReached as e:
        db.finish_job(job_id, "failed", error=str(e))
        log.warning("job %s failed: %s", job_id, e)
    except Exception as e:
        log.exception("job %s crashed", job_id)
        db.finish_job(job_id, "failed", error=(type(e).__name__ + ": " + str(e))[:300])


def run_loop():
    while not _stop.is_set():
        try:
            job = db.claim_next_job()
        except Exception:
            log.exception("could not read the job queue")
            _stop.wait(2)
            continue
        if job is None:
            _stop.wait(1)
            continue
        handle(job)


def start():
    global _thread
    db.reset_stuck_jobs()
    _stop.clear()
    _thread = threading.Thread(target=run_loop, name="job-worker", daemon=True)
    _thread.start()
    log.info("worker started")


def stop():
    _stop.set()