"""Job store (SQLite) and runner. A job = one department, one task, one gateway call."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

REPO = Path(os.environ.get("AGENT_STACK_REPO") or Path(__file__).resolve().parents[1])
DATA_DIR = REPO / "orchestrator" / "data"
LITELLM = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
MAX_OUTPUT_TOKENS = int(os.environ.get("ORCHESTRATOR_MAX_TOKENS", "4096"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_departments() -> dict[str, dict]:
    deps = {}
    common = (REPO / "agents" / "_common.md")
    footer = common.read_text(encoding="utf-8").strip() if common.exists() else ""
    for p in sorted((REPO / "agents").glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        a = yaml.safe_load(p.read_text(encoding="utf-8"))
        a["_system"] = a["system_prompt"].rstrip() + "\n\n" + footer
        deps[a["id"]] = a
    return deps


class JobStore:
    def __init__(self, path: Path | None = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path or DATA_DIR / "jobs.sqlite"
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, department TEXT, tier TEXT, model_alias TEXT, status TEXT, "
            "task TEXT, context TEXT, result TEXT, served_model TEXT, usage TEXT, error TEXT, created_at TEXT, started_at TEXT, finished_at TEXT)"
        )
        self._conn.commit()
        self._tasks: dict[str, asyncio.Task] = {}

    def create(self, department: str, task: str, context: str, tier: str, alias: str) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "department": department, "tier": tier, "model_alias": alias, "status": "queued", "task": task, "context": context, "created_at": now()}
        self._conn.execute("INSERT INTO jobs (id, department, tier, model_alias, status, task, context, created_at) VALUES (?,?,?,?,?,?,?,?)", (job["id"], department, tier, alias, "queued", task, context, job["created_at"]))
        self._conn.commit()
        return job

    def update(self, job_id: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        self._conn.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))
        self._conn.commit()

    def get(self, job_id: str) -> dict | None:
        cur = self._conn.execute("SELECT id, department, tier, model_alias, status, task, result, served_model, usage, error, created_at, started_at, finished_at FROM jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        keys = ["job_id", "department", "tier", "model_alias", "status", "task", "result", "served_model", "usage", "error", "created_at", "started_at", "finished_at"]
        d = dict(zip(keys, row))
        if d.get("usage"):
            try:
                d["usage"] = json.loads(d["usage"])
            except json.JSONDecodeError:
                pass
        return d

    def recent(self, limit: int = 20) -> list[dict]:
        cur = self._conn.execute("SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [self.get(r[0]) for r in cur.fetchall()]

    async def run(self, job_id: str, system_prompt: str) -> None:
        job = self.get(job_id)
        if not job:
            return
        self.update(job_id, status="running", started_at=now())
        user = job["task"] if not job.get("context") else f"{job['task']}\n\n<context>\n{job['context']}\n</context>"
        payload = {"model": job["model_alias"], "max_tokens": MAX_OUTPUT_TOKENS, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user}], "metadata": {"department": job["department"], "job_id": job_id, "source": "orchestrator-mcp"}}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=10.0)) as client:
                r = await client.post(f"{LITELLM}/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {MASTER_KEY}"})
            if r.status_code != 200:
                self.update(job_id, status="failed", error=f"HTTP {r.status_code}: {r.text[:500]}", finished_at=now())
                return
            body = r.json()
            text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            status = "escalate" if "ESCALATE:" in text else "done"
            self.update(job_id, status=status, result=text, served_model=body.get("model"), usage=json.dumps(body.get("usage") or {}), finished_at=now())
        except asyncio.CancelledError:
            self.update(job_id, status="cancelled", finished_at=now())
            raise
        except Exception as e:  # noqa: BLE001
            self.update(job_id, status="failed", error=f"{type(e).__name__}: {e}"[:500], finished_at=now())

    def launch(self, job_id: str, system_prompt: str) -> None:
        self._tasks[job_id] = asyncio.get_event_loop().create_task(self.run(job_id, system_prompt))

    def cancel(self, job_id: str) -> bool:
        t = self._tasks.get(job_id)
        if t and not t.done():
            t.cancel()
            return True
        return False
