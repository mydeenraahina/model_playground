import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


DB_PATH = os.environ.get("MODELCRAFT_DB_PATH", "modelcraft.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                endpoint_url TEXT,
                api_key TEXT,
                api_version TEXT,
                default_prompt TEXT,
                capabilities_json TEXT NOT NULL,
                metadata_json TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                model_id INTEGER,
                model_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                performance_type TEXT NOT NULL,
                selected_options_json TEXT NOT NULL,
                prompt TEXT,
                input_text TEXT,
                input_file_path TEXT,
                output_text TEXT,
                output_json TEXT,
                confidence REAL,
                accuracy REAL,
                time_taken_ms INTEGER,
                success INTEGER NOT NULL,
                error_message TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(model_id) REFERENCES models(id)
            );

            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                model_name TEXT NOT NULL,
                performance_type TEXT NOT NULL,
                email TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?)",
            (username,),
        ).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


def create_user(username: str, email: str | None, password_hash: str) -> dict[str, Any]:
    created_at = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, password_hash, created_at),
        )
        user_id = cursor.lastrowid
    user = get_user_by_id(user_id)
    if not user:
        raise RuntimeError("Failed to create user")
    return user


def list_custom_models() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM models
            ORDER BY lower(name) ASC
            """
        ).fetchall()
    models = []
    for row in rows:
        item = dict(row)
        item["capabilities"] = _loads(item.pop("capabilities_json", None), [])
        item["metadata"] = _loads(item.pop("metadata_json", None), {})
        models.append(item)
    return models


def get_custom_model_by_name(name: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM models WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["capabilities"] = _loads(item.pop("capabilities_json", None), [])
    item["metadata"] = _loads(item.pop("metadata_json", None), {})
    return item


def upsert_custom_model(
    *,
    name: str,
    provider: str,
    endpoint_url: str | None,
    api_key: str | None,
    api_version: str | None,
    default_prompt: str | None,
    capabilities: list[str],
    metadata: dict[str, Any] | None,
    created_by: int | None,
) -> dict[str, Any]:
    now = utc_now()
    capabilities_json = json.dumps(capabilities)
    metadata_json = json.dumps(metadata or {})

    existing = get_custom_model_by_name(name)
    with get_connection() as conn:
        if existing:
            conn.execute(
                """
                UPDATE models
                SET provider = ?, endpoint_url = ?, api_key = ?, api_version = ?,
                    default_prompt = ?, capabilities_json = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    provider,
                    endpoint_url,
                    api_key,
                    api_version,
                    default_prompt,
                    capabilities_json,
                    metadata_json,
                    now,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO models (
                    name, provider, endpoint_url, api_key, api_version, default_prompt,
                    capabilities_json, metadata_json, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    provider,
                    endpoint_url,
                    api_key,
                    api_version,
                    default_prompt,
                    capabilities_json,
                    metadata_json,
                    created_by,
                    now,
                    now,
                ),
            )
    model = get_custom_model_by_name(name)
    if not model:
        raise RuntimeError("Failed to save model")
    return model


def create_issue(
    *,
    user_id: int | None,
    model_name: str,
    performance_type: str,
    email: str,
    description: str,
) -> dict[str, Any]:
    created_at = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO issues (user_id, model_name, performance_type, email, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, model_name, performance_type, email, description, created_at),
        )
        issue_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    issue = row_to_dict(row)
    if not issue:
        raise RuntimeError("Failed to save issue")
    return issue


def create_test_run(
    *,
    user_id: int,
    model_id: int | None,
    model_name: str,
    provider: str,
    performance_type: str,
    selected_options: list[str],
    prompt: str | None,
    input_text: str | None,
    input_file_path: str | None,
    output_text: str | None,
    output_json: dict[str, Any] | None,
    confidence: float | None,
    accuracy: float | None,
    time_taken_ms: int | None,
    success: bool,
    error_message: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    created_at = utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO test_runs (
                user_id, model_id, model_name, provider, performance_type, selected_options_json,
                prompt, input_text, input_file_path, output_text, output_json,
                confidence, accuracy, time_taken_ms, success, error_message, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                model_id,
                model_name,
                provider,
                performance_type,
                json.dumps(selected_options),
                prompt,
                input_text,
                input_file_path,
                output_text,
                json.dumps(output_json) if output_json is not None else None,
                confidence,
                accuracy,
                time_taken_ms,
                1 if success else 0,
                error_message,
                json.dumps(metadata or {}),
                created_at,
            ),
        )
        run_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,)).fetchone()
    run = row_to_dict(row)
    if not run:
        raise RuntimeError("Failed to save test run")
    run["selected_options"] = _loads(run.pop("selected_options_json", None), [])
    run["output_json"] = _loads(run.get("output_json"), None)
    run["metadata"] = _loads(run.pop("metadata_json", None), {})
    run["success"] = bool(run["success"])
    return run


def list_test_runs(user_id: int | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        if user_id is None:
            rows = conn.execute(
                """
                SELECT * FROM test_runs
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM test_runs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (user_id,),
            ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["selected_options"] = _loads(item.pop("selected_options_json", None), [])
        item["output_json"] = _loads(item.get("output_json"), None)
        item["metadata"] = _loads(item.pop("metadata_json", None), {})
        item["success"] = bool(item["success"])
        results.append(item)
    return results
