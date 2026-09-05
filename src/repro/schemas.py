"""Strict, language-neutral contracts for a reproducible browser test."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    """Reject unknown fields so malformed model output cannot slip through."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Viewport(StrictModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=240, le=4320)


class LocatorSpec(StrictModel):
    """Data describing an allowed durable Playwright locator."""

    strategy: Literal["role", "label", "test_id", "text"]
    role: str | None = None
    name: str | None = None
    value: str | None = None
    exact: bool = True
    has_text: str | None = None
    scope: LocatorSpec | None = None

    @model_validator(mode="after")
    def validate_strategy_fields(self) -> LocatorSpec:
        if self.strategy == "role":
            if not self.role:
                raise ValueError("role locators require role")
            if self.value is not None:
                raise ValueError("role locators cannot contain value")
        else:
            if not self.value:
                raise ValueError(f"{self.strategy} locators require value")
            if self.role is not None or self.name is not None:
                raise ValueError(
                    f"{self.strategy} locators cannot contain role or name"
                )
        return self


class ClickAction(StrictModel):
    kind: Literal["click"]
    target: LocatorSpec


class FillAction(StrictModel):
    kind: Literal["fill"]
    target: LocatorSpec
    value: str


class PressAction(StrictModel):
    kind: Literal["press"]
    target: LocatorSpec
    key: str = Field(min_length=1)


class SelectAction(StrictModel):
    kind: Literal["select"]
    target: LocatorSpec
    value: str


class ScrollAction(StrictModel):
    kind: Literal["scroll"]
    delta_x: int = 0
    delta_y: int


Action = Annotated[
    ClickAction | FillAction | PressAction | SelectAction | ScrollAction,
    Field(discriminator="kind"),
]


class VisibilityOracle(StrictModel):
    kind: Literal["visible", "hidden"]
    target: LocatorSpec


class TextOracle(StrictModel):
    kind: Literal["text"]
    target: LocatorSpec
    expected_value: str
    match: Literal["exact", "contains"] = "exact"


class ValueOracle(StrictModel):
    kind: Literal["value"]
    target: LocatorSpec
    expected_value: str


class UrlOracle(StrictModel):
    kind: Literal["url"]
    expected_value: str = Field(min_length=1)


Oracle = Annotated[
    VisibilityOracle | TextOracle | ValueOracle | UrlOracle,
    Field(discriminator="kind"),
]


class ReproIR(StrictModel):
    """Validated input to deterministic code generation."""

    schema_version: Literal["1"] = "1"
    start_url: HttpUrl
    viewport: Viewport = Viewport(width=1440, height=900)
    setup_actions: tuple[Action, ...] = ()
    actions: tuple[Action, ...] = Field(min_length=1)
    oracle: Oracle
    source_expected_behavior: str = Field(min_length=1)
    oracle_locked: Literal[True] = True


class RunResult(StrictModel):
    """A deterministic classification of one generated-test execution."""

    status: Literal[
        "verified_reproduction",
        "unexpected_pass",
        "fixed_pass",
        "fixed_failure",
        "setup_failure",
        "action_failure",
        "environment_failure",
        "timeout",
    ]
    target_mode: Literal["buggy", "fixed"]
    failure_kind: Literal["setup", "action", "oracle", "environment", "timeout"] | None
    failed_step_id: str | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: int = Field(ge=0)
