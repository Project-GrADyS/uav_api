"""Unit tests for top-level command dispatch (split_command). A bare
invocation must stay an alias for `start`: systemd units run
`uav-api --config ...`."""

import pytest

from uav_api.args import split_command


def test_empty_argv_is_start():
    assert split_command([]) == ("start", [])


def test_bare_flags_are_start():
    assert split_command(["--config", "x.ini"]) == ("start", ["--config", "x.ini"])


def test_explicit_start():
    assert split_command(["start", "--simulated"]) == ("start", ["--simulated"])


def test_setup_sitl():
    assert split_command(["setup-sitl", "--vehicle", "plane"]) == ("setup-sitl", ["--vehicle", "plane"])


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        split_command(["strat"])


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_top_level_help_lists_commands(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        split_command([flag])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "start" in out and "setup-sitl" in out


def test_start_help_is_not_top_level():
    # `uav-api start --help` must reach the start parser, not the command list.
    assert split_command(["start", "--help"]) == ("start", ["--help"])
