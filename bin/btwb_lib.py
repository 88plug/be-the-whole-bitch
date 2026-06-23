"""Shared JSONL transcript parsing for be-the-whole-bitch yield-back detection."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class AssistantTurn:
    message_id: str
    texts: List[str]
    has_tool_use: bool
    has_text: bool
    stop_reason: Optional[str]
    line_count: int

    @property
    def text(self) -> str:
        return "\n".join(t for t in self.texts if t.strip())


def _blocks_from_record(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = rec.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict)]


def parse_assistant_turns(path: Path) -> List[AssistantTurn]:
    """Parse a session JSONL and return assistant turns in file order."""
    groups: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "texts": [],
            "has_tool_use": False,
            "has_text": False,
            "stop_reason": None,
            "line_count": 0,
            "order": 0,
        }
    )
    order = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            mid = msg.get("id")
            if not mid:
                continue
            g = groups[mid]
            if g["order"] == 0:
                order += 1
                g["order"] = order
            g["line_count"] += 1
            for block in _blocks_from_record(rec):
                btype = block.get("type")
                if btype == "tool_use":
                    g["has_tool_use"] = True
                elif btype == "text":
                    text = block.get("text") or ""
                    if text.strip():
                        g["has_text"] = True
                        g["texts"].append(text)
            sr = msg.get("stop_reason")
            if sr:
                g["stop_reason"] = sr

    turns: List[AssistantTurn] = []
    for mid, g in sorted(groups.items(), key=lambda kv: kv[1]["order"]):
        turns.append(
            AssistantTurn(
                message_id=mid,
                texts=g["texts"],
                has_tool_use=g["has_tool_use"],
                has_text=g["has_text"],
                stop_reason=g["stop_reason"],
                line_count=g["line_count"],
            )
        )
    return turns


def last_scorable_turn(path: Path) -> Optional[AssistantTurn]:
    turns = parse_assistant_turns(path)
    for turn in reversed(turns):
        if turn.has_text and turn.text.strip():
            return turn
    return None


def strip_code_fences(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", " ", text)
    return text