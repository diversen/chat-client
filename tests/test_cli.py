import click
from click.testing import CliRunner

from chat_client.cli import cli


def test_create_user_runs_bootstrap_before_prompting_for_credentials(monkeypatch):
    def fake_emit_bootstrap_messages(*, prompt_for_initial_user: bool) -> None:
        assert prompt_for_initial_user is False
        raise click.ClickException("bootstrap blocked command")

    monkeypatch.setattr("chat_client.cli._emit_bootstrap_messages", fake_emit_bootstrap_messages)
    runner = CliRunner()
    result = runner.invoke(cli, ["create-user"])

    assert result.exit_code != 0
    assert "bootstrap blocked command" in result.output
    assert "Email:" not in result.output
    assert "Password:" not in result.output
