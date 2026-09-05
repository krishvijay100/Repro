"""Tiny runtime hook used by generated tests to expose their current phase."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal


Phase = Literal["setup", "action", "oracle", "passed"]


def mark_phase(phase: Phase, step_id: str | None = None) -> None:
    """Persist only execution progress; never page data or credentials."""

    journal_path = os.environ.get("REPRO_PHASE_FILE")
    if journal_path is None:
        return
    Path(journal_path).write_text(
        json.dumps({"phase": phase, "step_id": step_id}),
        encoding="utf-8",
    )

