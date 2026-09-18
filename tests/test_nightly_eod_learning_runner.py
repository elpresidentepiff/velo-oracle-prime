from scripts.ops.nightly_eod_learning_runner import _exit_code_for_verdict


def test_nightly_runner_exit_code_reflects_domain_verdict():
    assert _exit_code_for_verdict("PASS") == 0
    assert _exit_code_for_verdict("FAIL") == 1
    assert _exit_code_for_verdict("FAIL_GATE_BLOCKED") == 1
