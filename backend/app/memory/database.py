"""Consent-based conversation history. No automatic long-term memory extraction."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(40))


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)


class History:
    def __init__(self, directory: Path):
        self.engine = create_engine(
            f"sqlite:///{(directory / 'jarvis.sqlite3').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)

    def list(self):
        with Session(self.engine) as db:
            return [
                {"id": row.id, "title": row.title, "created_at": row.created_at}
                for row in db.scalars(
                    select(Conversation).order_by(Conversation.created_at.desc()).limit(100)
                )
            ]

    def get(self, conversation_id: str):
        with Session(self.engine) as db:
            if not db.get(Conversation, conversation_id):
                return None
            return [
                {"role": row.role, "content": row.content}
                for row in db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.id.desc())
                    .limit(200)
                )
            ][::-1]

    def append(self, conversation_id: str | None, user: str, assistant: str) -> str:
        with Session(self.engine) as db, db.begin():
            if conversation_id is None:
                conversation_id = str(uuid4())
                db.add(
                    Conversation(
                        id=conversation_id,
                        title=user[:80],
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
            elif not db.get(Conversation, conversation_id):
                raise ValueError("Conversation no longer exists")
            for role, content in [("user", user), ("assistant", assistant)]:
                db.add(Message(conversation_id=conversation_id, role=role, content=content))
        return conversation_id

    def delete(self, conversation_id: str):
        with Session(self.engine) as db, db.begin():
            db.execute(delete(Message).where(Message.conversation_id == conversation_id))
            return db.execute(
                delete(Conversation).where(Conversation.id == conversation_id)
            ).rowcount
