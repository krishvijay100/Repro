from repro.pipeline.verify import _classify


def test_buggy_oracle_failure_is_verified_reproduction() -> None:
    assert _classify(target_mode="buggy", exit_code=1, phase="oracle") == (
        "verified_reproduction",
        "oracle",
    )


def test_action_failure_is_not_a_reproduction() -> None:
    assert _classify(target_mode="buggy", exit_code=1, phase="action") == (
        "action_failure",
        "action",
    )


def test_same_pass_has_different_meaning_by_target() -> None:
    assert _classify(target_mode="buggy", exit_code=0, phase="passed")[0] == (
        "unexpected_pass"
    )
    assert _classify(target_mode="fixed", exit_code=0, phase="passed")[0] == (
        "fixed_pass"
    )

