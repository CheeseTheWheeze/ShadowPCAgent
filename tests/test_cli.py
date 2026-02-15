import argparse
from pathlib import Path

import pytest

from shadowpcagent import cli


def test_build_parser_defaults() -> None:
    parser = cli.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    args = parser.parse_args([])
    assert args.task == "Review repository and propose improvements"
    assert args.command == "git status -sb"
    assert args.approve_sensitive is False
    assert args.plan_only is False


def test_build_edit_request_requires_find_replace() -> None:
    args = cli.build_parser().parse_args(["--edit-file", "README.md"])
    with pytest.raises(ValueError, match="--edit-file requires --find and --replace"):
        cli._build_edit_request(args)


def test_build_edit_request_with_apply() -> None:
    args = cli.build_parser().parse_args(
        [
            "--edit-file",
            "README.md",
            "--find",
            "ShadowPCAgent",
            "--replace",
            "ShadowPCAgent (Draft)",
            "--apply",
        ]
    )
    request = cli._build_edit_request(args)
    assert request is not None
    assert request.path == Path("README.md")
    assert request.find_text == "ShadowPCAgent"
    assert request.replace_text == "ShadowPCAgent (Draft)"
    assert request.apply is True


def test_emit_powershell_cleanup_script(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--emit-powershell-cleanup-script"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "function Should-ExcludePath" in captured.out
    assert "[int]$MaxFiles = 0" in captured.out
