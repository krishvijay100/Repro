"""Execute a generated test and classify the boundary it reached."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from repro.schemas import RunResult


def _read_phase(path: Path) -> tuple[str | None, str | None]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return record.get("phase"), record.get("step_id")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None, None


def _classify(
    *,
    target_mode: Literal["buggy", "fixed"],
    exit_code: int,
    phase: str | None,
) -> tuple[str, str | None]:
    if exit_code == 0:
        return (
            ("unexpected_pass", None)
            if target_mode == "buggy"
            else ("fixed_pass", None)
        )
    if phase == "oracle":
        return (
            ("verified_reproduction", "oracle")
            if target_mode == "buggy"
            else ("fixed_failure", "oracle")
        )
    if phase == "action":
        return "action_failure", "action"
    if phase == "setup":
        return "setup_failure", "setup"
    return "environment_failure", "environment"


def verify_generated_test(
    test_path: Path,
    artifact_dir: Path,
    *,
    target_mode: Literal["buggy", "fixed"],
    timeout_seconds: int = 60,
) -> RunResult:
    """Run pytest in a child process and save a structured result artifact."""

    artifact_dir.mkdir(parents=True, exist_ok=True)
    phase_path = artifact_dir / "execution-phase.json"
    phase_path.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["REPRO_PHASE_FILE"] = str(phase_path.resolve())
    started = time.perf_counter()

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path.resolve()), "-q"],
            capture_output=True,
            text=True,
            env=environment,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        phase, step_id = _read_phase(phase_path)
        status, failure_kind = _classify(
            target_mode=target_mode,
            exit_code=completed.returncode,
            phase=phase,
        )
        result = RunResult(
            status=status,
            target_mode=target_mode,
            failure_kind=failure_kind,
            failed_step_id=step_id if completed.returncode else None,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        _, step_id = _read_phase(phase_path)
        result = RunResult(
            status="timeout",
            target_mode=target_mode,
            failure_kind="timeout",
            failed_step_id=step_id,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            elapsed_ms=elapsed_ms,
        )

    (artifact_dir / "run-result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    return result

