"""Shared JSONL transcript parsing for be-the-whole-bitch yield-back detection."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def _user_text_from_content(content: Any) -> Optional[str]:
    """Extract real operator text; skip tool_result and skill-injection payloads."""
    if isinstance(content, str) and content.strip():
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
        return None
    parts: List[str] = []
    for c in content:
        if isinstance(c, dict) and c.get("type") == "text":
            t = c.get("text") or ""
            if t.strip().startswith("Base directory for this skill:"):
                return None
            parts.append(t)
    joined = "\n".join(parts).strip()
    return joined or None


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


def last_scorable_context(path: Path) -> Tuple[Optional[AssistantTurn], str]:
    """Return (last text-bearing assistant turn, prior real user text).

    Prior user text is the last operator message that appears before the
    chosen assistant turn's first line in the transcript. Used to dampen
    yield scores when the user only asked for a plan/docs.
    """
    turns = parse_assistant_turns(path)
    target: Optional[AssistantTurn] = None
    for turn in reversed(turns):
        if turn.has_text and turn.text.strip():
            target = turn
            break
    if not target:
        return None, ""

    last_user = ""
    seen_target = False
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type")
            if rtype == "user":
                text = _user_text_from_content((rec.get("message") or {}).get("content"))
                if text:
                    last_user = text
                continue
            if rtype != "assistant":
                continue
            mid = (rec.get("message") or {}).get("id")
            if mid == target.message_id:
                seen_target = True
                break
    # last_user is whatever preceded the target (empty if no prior operator text)
    return target, last_user if seen_target or last_user else ""


def strip_code_fences(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", " ", text)
    return text


def count_shell_fences(text: str) -> int:
    """Count fenced blocks that look like shell the operator is meant to run."""
    n = 0
    for m in re.finditer(r"```([^\n`]*)\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
        lang = (m.group(1) or "").strip().lower()
        body = (m.group(2) or "").strip()
        if not body:
            continue
        if re.match(
            r"^(?:bash|sh|shell|zsh|console|terminal|powershell|pwsh|fish|cmd|bat)\b",
            lang,
        ):
            n += 1
            continue
        # Untitled / language-less fence with shell-looking first line
        if lang == "" or lang in {"text", "plaintext"}:
            first = body.splitlines()[0].strip()
            if re.match(
                r"^(?:\$\s*)?(?:"
                r"sudo|doas|ssh|kubectl|docker|podman|git|curl|wget|npm|npx|pnpm|yarn|"
                r"pip|pipx|uv|cargo|go|make|cmake|systemctl|journalctl|apt|apt-get|"
                r"brew|pacman|yum|dnf|terraform|ansible|helm|aws|gcloud|az|gh|"
                r"cd|export|source|\.|chmod|chown|mount|umount|rsync|scp|tar|"
                r"python3?|node|ruby|perl|php|bash|zsh|sh"
                r")\b",
                first,
                re.IGNORECASE,
            ):
                n += 1
    return n
