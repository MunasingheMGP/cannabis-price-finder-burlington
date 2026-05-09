"""
Pipeline scheduler for the MontKailash Cannabis Platform.

Runs the full data pipeline automatically (default: every 168 hours).
Tracks per-run and per-step status in pipeline_run_log table.
Exposes run status via the FastAPI app (see main.py).
"""

import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

#  Make pipeline/ importable regardless of cwd 
BACKEND_DIR = Path(__file__).parent
PIPELINE_DIR = BACKEND_DIR / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

#  Pipeline steps in execution order 
PIPELINE_STEPS = [
    ("fetch_stores",    "fetch_stores_agco",         "main"),
    ("enrich_contacts", "enrich_store_contacts",      "main"),
    ("scrape_products", "scrape_competitor_products", "main"),
]

#  Shared mutable state (read by API endpoints) 
pipeline_state = {
    "status":      "idle",       # idle | running | success | failed
    "started_at":  None,
    "finished_at": None,
    "steps":       [],           # list of step result dicts
    "error":       None,
}

_scheduler: BackgroundScheduler | None = None


#  DB helpers 

def _ensure_log_table(engine):
    """Create pipeline_run_log if it doesn't exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS pipeline_run_log (
        id              SERIAL PRIMARY KEY,
        run_started_at  TIMESTAMPTZ NOT NULL,
        run_finished_at TIMESTAMPTZ,
        status          TEXT NOT NULL DEFAULT 'running',
        steps_json      TEXT,
        error_message   TEXT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _save_run(engine, run_started_at, status, steps, error=None):
    import json
    finished = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO pipeline_run_log
                (run_started_at, run_finished_at, status, steps_json, error_message)
            VALUES
                (:started, :finished, :status, :steps, :error)
        """), {
            "started":  run_started_at,
            "finished": finished,
            "status":   status,
            "steps":    json.dumps(steps),
            "error":    error,
        })
    return finished


#  Core runner 

def run_pipeline(engine=None):
    """
    Execute every pipeline step in sequence.
    Updates `pipeline_state` in place so the API can stream progress.
    Persists a run record to pipeline_run_log in PostgreSQL.
    """
    global pipeline_state

    if pipeline_state["status"] == "running":
        return {"already_running": True}

    started_at = datetime.now(timezone.utc)
    pipeline_state.update({
        "status":      "running",
        "started_at":  started_at.isoformat(),
        "finished_at": None,
        "steps":       [],
        "error":       None,
    })

    # get engine from pipeline's db_config if not supplied
    if engine is None:
        from db_config import get_engine
        engine = get_engine()

    _ensure_log_table(engine)
    overall_status = "success"
    last_error     = None

    for step_key, module_name, func_name in PIPELINE_STEPS:
        step_start = time.time()
        step_info  = {
            "step":       step_key,
            "module":     module_name,
            "status":     "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_s":  None,
            "error":      None,
        }
        pipeline_state["steps"].append(step_info)

        try:
            import importlib
            mod  = importlib.import_module(module_name)
            func = getattr(mod, func_name)
            func()
            step_info["status"]    = "success"
        except Exception as exc:
            step_info["status"]  = "failed"
            step_info["error"]   = traceback.format_exc()
            overall_status       = "failed"
            last_error           = str(exc)
            pipeline_state["status"] = "failed"
            pipeline_state["error"]  = f"{step_key}: {exc}"
            # continue remaining steps even after partial failure
        finally:
            step_info["elapsed_s"] = round(time.time() - step_start, 1)

    finished_at = _save_run(engine, started_at, overall_status,
                            pipeline_state["steps"], last_error)

    pipeline_state["status"]      = overall_status
    pipeline_state["finished_at"] = finished_at.isoformat()
    return pipeline_state.copy()


#  Scheduler lifecycle 

def start_scheduler(engine, interval_hours: int = 168):
    """
    Start the APScheduler background job.
    Call this once from FastAPI's startup event.
    """
    global _scheduler

    _ensure_log_table(engine)

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(hours=interval_hours),
        id="pipeline_auto",
        name="Full data pipeline",
        replace_existing=True,
        kwargs={"engine": engine},
    )
    _scheduler.start()
    print(f"[Scheduler] Pipeline scheduled every {interval_hours}h "
          f"(next: {_scheduler.get_job('pipeline_auto').next_run_time})")
    return _scheduler


def stop_scheduler():
    """Graceful shutdown — call from FastAPI's shutdown event."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped.")


def get_last_run_from_db(engine) -> dict | None:
    """Fetch the most recent run record from pipeline_run_log."""
    try:
        import json
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT run_started_at, run_finished_at, status,
                       steps_json, error_message
                FROM pipeline_run_log
                ORDER BY id DESC LIMIT 1
            """)).fetchone()
        if not row:
            return None
        return {
            "run_started_at":  row[0].isoformat() if row[0] else None,
            "run_finished_at": row[1].isoformat() if row[1] else None,
            "status":          row[2],
            "steps":           json.loads(row[3]) if row[3] else [],
            "error_message":   row[4],
        }
    except Exception:
        return None