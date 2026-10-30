"""Small persistent records and approval journal, separate from model instructions."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.app.memory.database import Base


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    due_at: Mapped[str | None]
    created_at: Mapped[str]


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(primary_key=True)
    tool: Mapped[str]
    arguments: Mapped[str] = mapped_column(Text)
    status: Mapped[str]
    result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str]


class Preference(Base):
    __tablename__ = "preferences"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Records:
    def __init__(self, engine):
        self.engine = engine
        Base.metadata.create_all(engine)
        # A server restart never replays a pending action.
        with Session(engine) as db, db.begin():
            for task in db.scalars(select(Task).where(Task.status.in_(["pending", "executing"]))):
                task.status = "expired"

    def list(self, kind: str):
        with Session(self.engine) as db:
            return [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "content": r.content,
                    "due_at": r.due_at,
                    "created_at": r.created_at,
                }
                for r in db.scalars(
                    select(Record)
                    .where(Record.kind == kind)
                    .order_by(Record.created_at.desc())
                    .limit(100)
                )
            ]

    def save(self, kind: str, content: str, due_at: str | None = None, record_id=None):
        with Session(self.engine) as db, db.begin():
            if record_id:
                record = db.get(Record, record_id)
                if not record or record.kind != kind:
                    raise ValueError("Record not found")
                record.content = content
                record.due_at = due_at
            else:
                record_id = str(uuid4())
                db.add(
                    Record(
                        id=record_id,
                        kind=kind,
                        content=content,
                        due_at=due_at,
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
        return {"id": record_id, "kind": kind, "content": content, "due_at": due_at}

    def delete(self, record_id: str):
        with Session(self.engine) as db, db.begin():
            record = db.get(Record, record_id)
            if not record:
                raise ValueError("Record not found")
            db.delete(record)
        return {"deleted": True}

    def preferences(self):
        with Session(self.engine) as db:
            return {p.key: json.loads(p.value) for p in db.scalars(select(Preference))}

    def set_preferences(self, values: dict):
        with Session(self.engine) as db, db.begin():
            for key, value in values.items():
                db.merge(Preference(key=key, value=json.dumps(value)))

    def tasks(self):
        with Session(self.engine) as db, db.begin():
            for task in db.scalars(select(Task).where(Task.status == "pending")):
                if (
                    datetime.now(UTC) - datetime.fromisoformat(task.created_at)
                ).total_seconds() > 300:
                    task.status = "expired"
            return [
                {
                    "id": t.id,
                    "tool": t.tool,
                    "arguments": json.loads(t.arguments),
                    "status": t.status,
                    "result": t.result,
                    "created_at": t.created_at,
                }
                for t in db.scalars(select(Task).order_by(Task.created_at.desc()).limit(100))
            ]
