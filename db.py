import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def save_run(run: dict):
    try:
        get_client().table("runs").upsert(run).execute()
    except Exception as e:
        print(f"[db] save_run error: {e}")


def get_runs(limit: int = 20):
    try:
        res = (
            get_client()
            .table("runs")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"[db] get_runs error: {e}")
        return []


def get_feed(limit: int = 10):
    try:
        res = (
            get_client()
            .table("runs")
            .select("run_id, repo, branch, workflow, outcome, reasoning, confidence, pr_url, error_type, timestamp")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"[db] get_feed error: {e}")
        return []
