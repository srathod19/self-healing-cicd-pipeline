import subprocess
import os
import httpx
from langchain_core.tools import tool

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


@tool
def read_log(log_text: str, max_lines: int = 100) -> str:
    """Extract the most relevant lines from a CI log — last N lines plus any ERROR/FAIL lines."""
    lines = log_text.splitlines()
    error_lines = [l for l in lines if any(k in l.upper() for k in ["ERROR", "FAIL", "EXCEPTION", "TRACEBACK", "FATAL"])]
    tail = lines[-max_lines:]
    combined = error_lines + ["---tail---"] + tail
    return "\n".join(combined[:200])


@tool
def git_diff(repo: str, base_sha: str, head_sha: str) -> str:
    """Fetch the diff between two commits on a GitHub repo."""
    url = f"https://api.github.com/repos/{repo}/compare/{base_sha}...{head_sha}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.diff"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text[:3000]
    except Exception as e:
        return f"git_diff error: {e}"


@tool
def run_cmd(command: str) -> str:
    """Run a safe diagnostic shell command (no write operations allowed)."""
    blocked = ["rm", "mv", "dd", "mkfs", "shutdown", "reboot", "curl", "wget", "pip install", "npm install"]
    if any(b in command for b in blocked):
        return "Command blocked for safety."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        return (result.stdout + result.stderr)[:1000]
    except Exception as e:
        return f"run_cmd error: {e}"


ALL_TOOLS = [read_log, git_diff, run_cmd]
