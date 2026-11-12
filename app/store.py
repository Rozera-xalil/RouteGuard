"""SQLite log of every prediction, so we can later compare it with what really happened."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    order_id TEXT,
    payload TEXT NOT NULL,
    probability REAL NOT NULL,
    risk_level TEXT NOT NULL,
    predicted_late INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    actual_late INTEGER,
    feedback_ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_ts ON predictions(ts);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PredictionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def add(self, pid: str, order_id: str | None, payload: dict, res: dict) -> None:
        with closing(self._conn()) as c, c:
            c.execute(
                "INSERT INTO predictions (id, ts, order_id, payload, probability, risk_level,"
                " predicted_late, model_version) VALUES (?,?,?,?,?,?,?,?)",
                (
                    pid, _now(), order_id, json.dumps(payload, default=str),
                    res["probability"], res["risk_level"], int(res["predicted_late"]),
                    res["model_version"],
                ),
            )  # fmt: skip

    def set_actual(self, pid: str, actual_late: bool) -> bool:
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "UPDATE predictions SET actual_late=?, feedback_ts=? WHERE id=?",
                (int(actual_late), _now(), pid),
            )
            return cur.rowcount > 0

    def recent_payloads(self, limit: int = 1000) -> list[dict]:
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT payload FROM predictions ORDER BY ts DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def recent(self, limit: int = 10) -> list[dict]:
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT id, ts, order_id, probability, risk_level, predicted_late, actual_late,"
                " json_extract(payload,'$.seller_state') AS seller_state,"
                " json_extract(payload,'$.customer_state') AS customer_state"
                " FROM predictions ORDER BY ts DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def volume(self) -> dict:
        since = (datetime.now(UTC) - timedelta(hours=24)).isoformat(timespec="seconds")
        with closing(self._conn()) as c:
            total = c.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            last = c.execute("SELECT COUNT(*) FROM predictions WHERE ts>=?", (since,)).fetchone()[0]
            by = c.execute(
                "SELECT risk_level, COUNT(*) n FROM predictions WHERE ts>=? GROUP BY risk_level",
                (since,),
            ).fetchall()
        return {
            "total": total,
            "last_24h": last,
            "last_24h_by_risk": {r["risk_level"]: r["n"] for r in by},
        }

    def live_performance(self) -> dict:
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT probability, predicted_late, actual_late FROM predictions"
                " WHERE actual_late IS NOT NULL"
            ).fetchall()
        n = len(rows)
        if n == 0:
            return {"n_labeled": 0}
        y = [r["actual_late"] for r in rows]
        pred = [r["predicted_late"] for r in rows]
        tp = sum(1 for a, p in zip(y, pred, strict=True) if a and p)
        return {
            "n_labeled": n,
            "late_rate": round(sum(y) / n, 4),
            "precision": round(tp / max(sum(pred), 1), 4) if sum(pred) else None,
            "recall": round(tp / max(sum(y), 1), 4) if sum(y) else None,
            "brier": round(sum((r["probability"] - r["actual_late"]) ** 2 for r in rows) / n, 4),
        }
