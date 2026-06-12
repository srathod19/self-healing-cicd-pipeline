import os
import json
import re
import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from agent.tools import ALL_TOOLS
from github_integration.pr import create_pr
from drift.schema_watcher import detect_schema_drift
from agent.prompts import CLASSIFIER_PROMPT, REASONING_PROMPT

GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GEMINI_KEY,
    temperature=0.2,
    max_tokens=3000,
)
llm_with_tools = llm.bind_tools(ALL_TOOLS)


def detect_failure(state):
    """Pass logs through directly — do NOT filter them."""
    logs = state.get("raw_logs", "")

    # Check for schema drift and append if found
    drift_result = detect_schema_drift()
    if drift_result:
        logs += f"\n\n[SCHEMA DRIFT DETECTED]\n{drift_result}"

    print(f"[DETECT] logs length: {len(logs)}, preview: {logs[:200]}")
    return {"raw_logs": logs}


def classify_error(state):
    """Use Gemini to classify the error type and affected step."""
    logs = state["raw_logs"]
    msgs = [
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=f"CI logs:\n{logs[:3000]}"),
    ]
    response = llm.invoke(msgs)
    text = response.content

    error_type = "unknown"
    error_detail = text

    for t in ["schema_drift", "missing_env", "import_error", "test_failure", "lint_error", "dependency_conflict"]:
        if t in text.lower().replace(" ", "_"):
            error_type = t
            break

    print(f"[CLASSIFY] error_type: {error_type}")
    return {"error_type": error_type, "error_detail": text}


def reason_and_patch(state):
    """Use Gemini with tools to reason about root cause and produce a patch."""
    msgs = [
        SystemMessage(content=REASONING_PROMPT),
        HumanMessage(content=(
            f"Repo: {state.get('repo')}\n"
            f"Branch: {state.get('branch')}\n"
            f"Error type: {state.get('error_type')}\n"
            f"Error detail: {state.get('error_detail')}\n"
            f"Logs:\n{state['raw_logs'][:3000]}\n\n"
            "Produce a JSON response with keys: reasoning, patch, patch_file, confidence (0-1)."
        )),
    ]

    response = llm_with_tools.invoke(msgs)
    raw = response.content
    print(f"[DEBUG] Gemini raw response: {raw[:800]}")

    reasoning = raw
    patch = None
    patch_file = None
    confidence = 0.5

    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    # Try full parse first
    try:
        data = json.loads(cleaned)
        patch = data.get("patch")
        patch_file = data.get("patch_file")
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning", raw)
    except Exception:
        # Fallback: find first {...} block
        json_match = re.search(r"\{[\s\S]*?\}", cleaned)
        if json_match:
            try:
                data = json.loads(json_match.group())
                patch = data.get("patch")
                patch_file = data.get("patch_file")
                confidence = float(data.get("confidence", 0.5))
                reasoning = data.get("reasoning", raw)
            except Exception:
                reasoning = raw
                confidence = 0.4

    print(f"[REASON] confidence: {confidence}, patch_file: {patch_file}")
    return {
        "patch": patch,
        "patch_file": patch_file,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def confidence_check(state):
    """Pass-through node — routing logic lives in the graph conditional edge."""
    return state


def apply_fix(state):
    """Open a GitHub PR with the generated patch."""
    try:
        pr_url = create_pr(
            repo=state["repo"],
            branch=state["branch"],
            patch=state.get("patch", ""),
            patch_file=state.get("patch_file", ""),
            reasoning=state.get("reasoning", ""),
            run_id=state["run_id"],
        )
        return {"outcome": "fixed", "pr_url": pr_url}
    except Exception as e:
        return {"outcome": "failed", "reasoning": str(e)}


def escalate(state):
    """Send a Slack alert with the agent's analysis."""
    msg = {
        "text": (
            f":warning: *Self-healing agent escalation*\n"
            f"*Repo:* {state.get('repo')}\n"
            f"*Branch:* {state.get('branch')}\n"
            f"*Error type:* {state.get('error_type')}\n"
            f"*Confidence:* {round((state.get('confidence') or 0) * 100)}%\n"
            f"*Agent analysis:*\n{state.get('reasoning', 'N/A')[:500]}"
        )
    }
    if SLACK_WEBHOOK:
        try:
            httpx.post(SLACK_WEBHOOK, json=msg, timeout=5)
        except Exception:
            pass

    return {"outcome": "escalated"}
