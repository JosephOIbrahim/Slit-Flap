"""CLI restore safety regressions from the operations review."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from departures import cli as cli_module
from departures import db
from departures.cli import cli

from .test_backups import daily_backups, ids_in, start_board


@pytest.fixture
def ops_restore(board, monkeypatch):
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: False)

    def run(*args, input=None):
        return CliRunner().invoke(cli, ["restore", *map(str, args)], input=input)

    return run


def test_a_bare_backup_name_is_not_shadowed_by_the_working_directory(
        ops_restore, monkeypatch, tmp_path):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    elsewhere = tmp_path / "working-directory"
    elsewhere.mkdir()
    (elsewhere / backup.name).write_text("a same-named decoy, not a board", encoding="utf-8")
    monkeypatch.chdir(elsewhere)

    result = ops_restore(backup.name, "--yes")

    assert result.exit_code == 0, result.output
    assert ids_in(db.DB_PATH) == ids_in(backup)


def test_manual_restore_steps_respect_a_relocated_data_folder():
    using = Path(__file__).resolve().parent.parent / "docs" / "USING.md"
    steps = using.read_text(encoding="utf-8").split("## Restore by hand", 1)[1].split(
        "\n## ", 1
    )[0]
    assert "%DEPARTURES_HOME%" in steps
    assert "%USERPROFILE%\\.departures" in steps
    assert "$DEPARTURES_HOME" in steps
    assert "~/.departures" in steps
