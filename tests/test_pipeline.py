"""Unit tests for pipeline orchestrator."""

from unittest.mock import patch
from hackingupdate.pipeline import run_step, PIPELINE_STEPS


def test_pipeline_steps_exist():
    step_names = [s[0] for s in PIPELINE_STEPS]
    assert "fetch" in step_names
    assert "extract" in step_names
    assert "rank" in step_names
    assert "report" in step_names
    assert "html" in step_names
    assert "email" in step_names


def test_run_step_unknown():
    assert run_step("non_existent_step") is False


def test_run_step_mock_success():
    with patch("hackingupdate.pipeline._execute_step", return_value=True):
        assert run_step("fetch") is True
