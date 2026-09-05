"""Small command-line boundary for the first reproducible vertical slice."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from repro.codegen.playwright_python import render_test
from repro.pipeline.verify import verify_generated_test
from repro.schemas import ReproIR


app = typer.Typer(no_args_is_help=True)


@app.command()
def render(
    ir_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_path: Path,
    test_name: str = "test_reproduced_bug",
) -> None:
    """Validate IR and render a deterministic Python Playwright test."""

    ir = ReproIR.model_validate_json(ir_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_test(ir, test_name), encoding="utf-8")
    typer.echo(str(output_path.resolve()))


@app.command()
def verify(
    test_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    artifact_dir: Path,
    target_mode: Annotated[Literal["buggy", "fixed"], typer.Option()] = "buggy",
    timeout_seconds: Annotated[int, typer.Option(min=1)] = 60,
) -> None:
    """Execute a generated test and classify its failure boundary."""

    result = verify_generated_test(
        test_path,
        artifact_dir,
        target_mode=target_mode,
        timeout_seconds=timeout_seconds,
    )
    typer.echo(result.model_dump_json(indent=2))

