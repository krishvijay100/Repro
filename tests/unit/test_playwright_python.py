import json
from pathlib import Path

import pytest

from repro.codegen.playwright_python import render_test
from repro.schemas import ReproIR


def load_example() -> ReproIR:
    data = json.loads(Path("examples/apple_juice.ir.json").read_text())
    return ReproIR.model_validate(data)


def test_renders_scoped_locator_and_locked_oracle() -> None:
    source = render_test(load_example(), "test_apple_juice")

    assert (
        "page.get_by_role('article', exact=True)"
        ".filter(has_text='Apple Juice (1000ml)')"
        ".get_by_role('button', name='Add to Basket', exact=True).click()"
    ) in source
    assert "expect(page.get_by_role('button', name='Show the shopping cart'" in source
    assert ".to_contain_text('1')" in source
    assert "mark_phase('action', 'action-004')" in source
    assert "mark_phase('oracle', 'oracle')" in source
    assert source.index("mark_phase('oracle'") < source.index(".to_contain_text('1')")


def test_rendering_is_deterministic() -> None:
    ir = load_example()

    assert render_test(ir) == render_test(ir)


def test_python_strings_are_escaped_not_executed() -> None:
    data = load_example().model_dump(mode="json")
    data["actions"][1]["value"] = "'); __import__('os').system('bad') #"
    ir = ReproIR.model_validate(data)

    source = render_test(ir)

    compile(source, "generated_test.py", "exec")
    assert "fill(\"'); __import__('os').system('bad') #\")" in source


def test_rejects_invalid_test_name() -> None:
    with pytest.raises(ValueError, match="valid pytest test identifier"):
        render_test(load_example(), "test_bad; import os")
