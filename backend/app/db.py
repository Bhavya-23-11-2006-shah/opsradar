"""SQLAlchemy + SQLite persistence. Findings are stored as contract JSON."""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Optional

from sqlalchemy import Float, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import DATABASE_URL


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    industry: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files_json: Mapped[str] = mapped_column(Text, default="[]")
    mapping_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overview_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    payload_json: Mapped[str] = mapped_column(Text)


class ActionRow(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    finding_id: Mapped[str] = mapped_column(String(64))
    finding_title: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(80), default="Ops manager")
    at: Mapped[str] = mapped_column(String(40), default=now_iso)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    finding_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


engine = create_engine(
    DATABASE_URL,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --------------------------------------------------------------------------- datasets


def create_dataset(
    dataset_id: str,
    *,
    industry: Optional[str],
    files: Iterable[dict],
) -> None:
    with session_scope() as session:
        session.merge(
            DatasetRow(
                id=dataset_id,
                industry=industry,
                files_json=dumps(list(files)),
                status="idle",
                percent=0.0,
            )
        )


def get_dataset(dataset_id: str) -> Optional[DatasetRow]:
    with session_scope() as session:
        return session.get(DatasetRow, dataset_id)


def update_dataset(dataset_id: str, **values: Any) -> None:
    with session_scope() as session:
        row = session.get(DatasetRow, dataset_id)
        if row is None:
            return
        for key, value in values.items():
            setattr(row, key, value)
        session.add(row)


def set_progress(
    dataset_id: str,
    *,
    status: str,
    step: Optional[str] = None,
    percent: float = 0.0,
    message: Optional[str] = None,
) -> None:
    update_dataset(dataset_id, status=status, step=step, percent=round(float(percent), 1), message=message)


# --------------------------------------------------------------------------- findings


def save_finding_payloads(dataset_id: str, payloads: Iterable[dict]) -> None:
    with session_scope() as session:
        for payload in payloads:
            existing = session.get(FindingRow, payload["id"])
            if existing is not None and existing.dataset_id == dataset_id:
                # Preserve human decisions across re-analysis.
                payload["status"] = existing.status
                existing.risk_score = float(payload.get("riskScore", 0))
                existing.payload_json = dumps(payload)
                session.add(existing)
            else:
                session.add(
                    FindingRow(
                        id=payload["id"],
                        dataset_id=dataset_id,
                        status=payload.get("status", "open"),
                        risk_score=float(payload.get("riskScore", 0)),
                        created_at=payload.get("createdAt", now_iso()),
                        payload_json=dumps(payload),
                    )
                )


def fetch_finding_payloads(dataset_id: str) -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(select(FindingRow).where(FindingRow.dataset_id == dataset_id)).all()
    payloads = [loads(row.payload_json, {}) for row in rows]
    payloads.sort(key=lambda item: float(item.get("riskScore", 0)), reverse=True)
    return payloads


def get_finding_row(dataset_id: str, finding_id: str) -> Optional[FindingRow]:
    with session_scope() as session:
        row = session.get(FindingRow, finding_id)
        if row is None or row.dataset_id != dataset_id:
            return None
        return row


def get_finding_payload(dataset_id: str, finding_id: str) -> Optional[dict]:
    row = get_finding_row(dataset_id, finding_id)
    return loads(row.payload_json, {}) if row is not None else None


def update_finding_payload(dataset_id: str, payload: dict) -> None:
    with session_scope() as session:
        row = session.get(FindingRow, payload["id"])
        if row is None or row.dataset_id != dataset_id:
            return
        row.status = payload["status"]
        row.risk_score = float(payload.get("riskScore", row.risk_score))
        row.payload_json = dumps(payload)
        session.add(row)


# --------------------------------------------------------------------------- actions


def add_action(
    dataset_id: str,
    *,
    finding_id: str,
    finding_title: str,
    decision: str,
    note: str,
    actor: str,
) -> dict:
    action_id = f"act-{uuid.uuid4().hex[:12]}"
    row = ActionRow(
        id=action_id,
        dataset_id=dataset_id,
        finding_id=finding_id,
        finding_title=finding_title,
        decision=decision,
        note=note,
        actor=actor,
        at=now_iso(),
    )
    with session_scope() as session:
        session.add(row)
    return {
        "id": action_id,
        "findingId": finding_id,
        "findingTitle": finding_title,
        "decision": decision,
        "note": note,
        "actor": actor,
        "at": row.at,
    }


def fetch_actions(dataset_id: str) -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(
            select(ActionRow).where(ActionRow.dataset_id == dataset_id).order_by(ActionRow.at.desc())
        ).all()
    return [
        {
            "id": row.id,
            "findingId": row.finding_id,
            "findingTitle": row.finding_title,
            "decision": row.decision,
            "note": row.note,
            "actor": row.actor,
            "at": row.at,
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- tasks


def add_task(dataset_id: str, *, finding_id: str, title: str) -> dict:
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    row = TaskRow(id=task_id, dataset_id=dataset_id, finding_id=finding_id, title=title, status="open")
    with session_scope() as session:
        session.add(row)
    return {
        "id": task_id,
        "findingId": finding_id,
        "title": title,
        "status": "open",
        "createdAt": row.created_at,
    }


def fetch_tasks(dataset_id: str) -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(
            select(TaskRow).where(TaskRow.dataset_id == dataset_id).order_by(TaskRow.created_at.desc())
        ).all()
    return [
        {
            "id": row.id,
            "findingId": row.finding_id,
            "title": row.title,
            "status": row.status,
            "createdAt": row.created_at,
        }
        for row in rows
    ]


def clear_findings(dataset_id: str) -> None:
    with session_scope() as session:
        session.execute(delete(FindingRow).where(FindingRow.dataset_id == dataset_id))
