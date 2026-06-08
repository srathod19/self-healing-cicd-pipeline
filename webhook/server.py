import os
import json
import hashlib
import hmac
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from agent.graph import agent_graph
from db import save_run, get_runs, get_feed

app = FastAPI(title="Self-Healing CI/CD Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, sig_header: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


async def run_agent(state: dict):
    try:
        result = await agent_graph.ainvoke(state)
        save_run({
            "run_id": state["run_id"],
            "repo": state["repo"],
            "branch": state["branch"],
            "workflow": state["workflow"],
            "outcome": result.get("outcome"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "pr_url": result.get("pr_url"),
            "error_type": result.get("error_type"),
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        save_run({
            "run_id": state["run_id"],
            "repo": state["repo"],
            "branch": state["branch"],
            "workflow": state["workflow"],
            "outcome": "agent_error",
            "reasoning": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        })


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event != "workflow_run":
        return JSONResponse({"status": "ignored", "event": event})

    payload = json.loads(body)
    wf = payload.get("workflow_run", {})

    if wf.get("conclusion") != "failure":
        return JSONResponse({"status": "ignored", "conclusion": wf.get("conclusion")})

    state = {
        "run_id": str(wf.get("id", uuid.uuid4())),
        "repo": payload.get("repository", {}).get("full_name", ""),
        "branch": wf.get("head_branch", ""),
        "workflow": wf.get("name", ""),
        "raw_logs": json.dumps(wf),
        "error_type": None,
        "error_detail": None,
        "patch": None,
        "patch_file": None,
        "confidence": None,
        "reasoning": None,
        "outcome": None,
        "pr_url": None,
        "messages": [],
    }

    background_tasks.add_task(run_agent, state)
    return JSONResponse({"status": "processing", "run_id": state["run_id"]})


@app.get("/runs")
def list_runs(limit: int = 20):
    return get_runs(limit)


@app.get("/feed")
def agent_feed(limit: int = 10):
    return get_feed(limit)


@app.get("/health")
def health():
    return {"status": "ok"}
