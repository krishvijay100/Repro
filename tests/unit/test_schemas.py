import pytest
from pydantic import ValidationError

from repro.schemas import ReproIR


def minimal_ir() -> dict:
    return {
        "start_url": "http://127.0.0.1:3000",
        "actions": [
            {
                "kind": "click",
                "target": {
                    "strategy": "role",
                    "role": "button",
                    "name": "Checkout",
                },
            }
        ],
        "oracle": {
            "kind": "url",
            "expected_value": "http://127.0.0.1:3000/#/payment",
        },
        "source_expected_behavior": "Checkout opens payment.",
    }


def test_valid_ir_is_frozen_and_locks_oracle() -> None:
    ir = ReproIR.model_validate(minimal_ir())

    assert ir.oracle_locked is True
    with pytest.raises(ValidationError):
        ir.oracle_locked = False


def test_rejects_unknown_action_fields() -> None:
    data = minimal_ir()
    data["actions"][0]["javascript"] = "stealCookies()"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReproIR.model_validate(data)


def test_rejects_invalid_locator_shape() -> None:
    data = minimal_ir()
    data["actions"][0]["target"] = {
        "strategy": "test_id",
        "role": "button",
    }

    with pytest.raises(ValidationError, match="test_id locators require value"):
        ReproIR.model_validate(data)


def test_rejects_unlocked_oracle() -> None:
    data = minimal_ir()
    data["oracle_locked"] = False

    with pytest.raises(ValidationError):
        ReproIR.model_validate(data)

