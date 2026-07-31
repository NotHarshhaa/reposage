"""Durable JSON persistence for saved chat conversations."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from models.schemas import Conversation, ConversationMessage

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{6,64}$")


class ConversationStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, repository_id: str, messages: list[ConversationMessage], title: str | None = None) -> Conversation:
        now = datetime.now(UTC)
        first_question = next((message.content for message in messages if message.role == "user"), "Saved conversation")
        conversation = Conversation(
            id=uuid.uuid4().hex[:16], repository_id=repository_id,
            title=(title or first_question).strip()[:200] or "Saved conversation",
            created_at=now, updated_at=now, message_count=len(messages), messages=messages,
        )
        destination = self.directory / f"{conversation.id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(conversation.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)
        return conversation

    def load(self, conversation_id: str) -> Conversation | None:
        if not _SAFE_ID.match(conversation_id):
            return None
        source = self.directory / f"{conversation_id}.json"
        if not source.exists():
            return None
        try:
            return Conversation.model_validate_json(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def list(self, repository_id: str | None = None) -> list[Conversation]:
        conversations: list[Conversation] = []
        for source in self.directory.glob("*.json"):
            try:
                conversation = Conversation.model_validate_json(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if repository_id and conversation.repository_id != repository_id:
                continue
            conversations.append(conversation)
        return sorted(conversations, key=lambda item: item.updated_at, reverse=True)

    def delete(self, conversation_id: str) -> bool:
        if not _SAFE_ID.match(conversation_id):
            return False
        target = self.directory / f"{conversation_id}.json"
        if not target.exists():
            return False
        target.unlink()
        return True

    def count(self) -> int:
        return sum(1 for _ in self.directory.glob("*.json"))


def conversation_to_markdown(conversation: Conversation) -> str:
    lines = [
        f"# {conversation.title}",
        "",
        f"- Repository: `{conversation.repository_id}`",
        f"- Saved: {conversation.updated_at.isoformat()}",
        f"- Messages: {conversation.message_count}",
        "",
    ]
    for message in conversation.messages:
        lines.append(f"## {'Question' if message.role == 'user' else 'Answer'}")
        lines.append("")
        lines.append(message.content.strip())
        lines.append("")
        if message.sources:
            lines.append("### Sources")
            lines.extend(
                f"- `{source.path}` lines {source.start_line}-{source.end_line} (score {source.score})"
                for source in message.sources
            )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
