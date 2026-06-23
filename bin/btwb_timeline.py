"""Parse ordered user/assistant timeline from session JSONL for replay simulation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from btwb_lib import AssistantTurn, _blocks_from_record


@dataclass
class UserMessage:
    text: str
    line_no: int
    is_skill_injection: bool = False


@dataclass
class TimelineEvent:
    kind: str  # "user" | "assistant"
    index: int
    user: Optional[UserMessage] = None
    assistant: Optional[AssistantTurn] = None


def _is_real_user_content(content: Any) -> Optional[str]:
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return None
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                t = c.get("text") or ""
                if t.strip().startswith("Base directory for this skill:"):
                    return None
                parts.append(t)
        joined = "\n".join(parts).strip()
        return joined or None
    return None


def parse_timeline(path: Path) -> List[TimelineEvent]:
    """Return ordered user and assistant events as they appear in the JSONL."""
    events: List[TimelineEvent] = []
    assistant_groups: Dict[str, Dict[str, Any]] = {}
    assistant_order: List[str] = []
    user_idx = 0
    asst_idx = 0

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type")

            if rtype == "user":
                text = _is_real_user_content((rec.get("message") or {}).get("content"))
                if text is None:
                    continue
                user_idx += 1
                events.append(
                    TimelineEvent(
                        kind="user",
                        index=user_idx,
                        user=UserMessage(text=text, line_no=line_no),
                    )
                )
                continue

            if rtype != "assistant":
                continue

            msg = rec.get("message") or {}
            mid = msg.get("id")
            if not mid:
                continue

            if mid not in assistant_groups:
                assistant_groups[mid] = {
                    "texts": [],
                    "has_tool_use": False,
                    "has_text": False,
                    "stop_reason": None,
                    "line_count": 0,
                    "line_no": line_no,
                    "finalized": False,
                }
                assistant_order.append(mid)

            g = assistant_groups[mid]
            g["line_count"] += 1
            for block in _blocks_from_record(rec):
                btype = block.get("type")
                if btype == "tool_use":
                    g["has_tool_use"] = True
                elif btype == "text":
                    t = block.get("text") or ""
                    if t.strip():
                        g["has_text"] = True
                        g["texts"].append(t)
            sr = msg.get("stop_reason")
            if sr:
                g["stop_reason"] = sr
                if sr == "end_turn" and not g["finalized"]:
                    g["finalized"] = True
                    asst_idx += 1
                    events.append(
                        TimelineEvent(
                            kind="assistant",
                            index=asst_idx,
                            assistant=AssistantTurn(
                                message_id=mid,
                                texts=g["texts"][:],
                                has_tool_use=g["has_tool_use"],
                                has_text=g["has_text"],
                                stop_reason=g["stop_reason"],
                                line_count=g["line_count"],
                            ),
                        )
                    )

            # tool_use stop may continue same message id — don't emit until end_turn

    return events


def session_tags(path: Path, events: List[TimelineEvent]) -> Dict[str, bool]:
    """Heuristic session classification from path + user text."""
    p = str(path).lower()
    all_user = " ".join(e.user.text for e in events if e.kind == "user" and e.user)
    return {
        "eval_trap": bool(
            re.search(r"give me the exact commands", all_user, re.I)
            or "trigger-my-training" in p
        ),
        "has_run_imperative": bool(re.search(r"\brun the (drain|migration|apply)\b", all_user, re.I)),
        "interactive": sum(1 for e in events if e.kind == "user") >= 3,
    }