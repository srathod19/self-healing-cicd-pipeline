import os
import json

SCHEMA_SNAPSHOT_PATH = os.getenv("SCHEMA_SNAPSHOT_PATH", "schema_snapshot.json")
DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_current_schema() -> dict:
    """Fetch current DB schema as a dict {table: [columns]}."""
    if not DATABASE_URL:
        return {}
    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        schema = {}
        for table in inspector.get_table_names():
            cols = inspector.get_columns(table)
            schema[table] = [
                {"name": c["name"], "type": str(c["type"])} for c in cols
            ]
        return schema
    except Exception as e:
        print(f"[schema_watcher] error: {e}")
        return {}


def load_snapshot() -> dict:
    try:
        with open(SCHEMA_SNAPSHOT_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_snapshot(schema: dict):
    with open(SCHEMA_SNAPSHOT_PATH, "w") as f:
        json.dump(schema, f, indent=2)


def detect_schema_drift() -> str | None:
    """
    Compare current DB schema against last snapshot.
    Returns a human-readable drift report, or None if no drift.
    """
    current = get_current_schema()
    if not current:
        return None

    snapshot = load_snapshot()
    if not snapshot:
        save_snapshot(current)
        return None

    diffs = []

    for table, cols in current.items():
        if table not in snapshot:
            diffs.append(f"New table: {table}")
            continue
        snap_cols = {c["name"]: c["type"] for c in snapshot[table]}
        curr_cols = {c["name"]: c["type"] for c in cols}

        for col, typ in curr_cols.items():
            if col not in snap_cols:
                diffs.append(f"{table}.{col}: NEW column ({typ})")
            elif snap_cols[col] != typ:
                diffs.append(f"{table}.{col}: type changed {snap_cols[col]} -> {typ}")

        for col in snap_cols:
            if col not in curr_cols:
                diffs.append(f"{table}.{col}: DROPPED column")

    for table in snapshot:
        if table not in current:
            diffs.append(f"Dropped table: {table}")

    if diffs:
        save_snapshot(current)
        return "\n".join(diffs)

    return None
