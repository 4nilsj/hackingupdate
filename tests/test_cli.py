"""Unit tests for Click CLI entry point."""

from click.testing import CliRunner
from hackingupdate.cli import cli, __version__


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_steps():
    runner = CliRunner()
    result = runner.invoke(cli, ["steps"])
    assert result.exit_code == 0
    assert "Pipeline Steps" in result.output
    assert "fetch" in result.output
    assert "email" in result.output


def test_cli_init():
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Project Root" in result.output
    assert "Pipeline Settings" in result.output


def test_cli_feeds_list():
    runner = CliRunner()
    result = runner.invoke(cli, ["feeds", "list"])
    assert result.exit_code == 0
    assert "Configured feeds" in result.output
