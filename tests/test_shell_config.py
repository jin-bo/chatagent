"""The shell configuration surface: the rule label, the shell block, and the one record.

PR-3 of the PowerShell ladder. ``TOOL-02``, ``CFG-01``, ``CFG-02``, ``CFG-03`` and
``LADDER-02`` are defined once each in ``docs/design/powershell-support-spec.zh.md`` §2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentao.capabilities.shell_spec import ShellDialect
from agentao.embedding.permission_loader import (
    PermissionConfig,
    PermissionConfigError,
    load_permission_config,
)
from agentao.permissions import (
    rule_matches_dialect,
    unspecified_shell_rules,
    validate_permission_rules,
)


def write_config(root: Path, document: dict) -> Path:
    (root / "permissions.json").write_text(json.dumps(document), encoding="utf-8")
    return root


# ------------------------------------------------------------------ TOOL-02


@pytest.mark.parametrize("dialect", ["posix", "cmd", "powershell", "*"])
def test_the_four_labels_are_accepted(dialect):
    assert validate_permission_rules([{"tool": "run_shell_command", "action": "allow",
                                       "dialect": dialect}]) == []


def test_an_unknown_label_is_refused_rather_than_ignored():
    """A misspelled label that fell through would silently apply the rule everywhere."""
    errors = validate_permission_rules(
        [{"tool": "run_shell_command", "action": "allow", "dialect": "bash"}]
    )
    assert errors and "unknown dialect" in errors[0][1]


def test_the_label_names_a_dialect_and_not_a_rung():
    """TOOL-02: `posix` covers the Git Bash rung and the system shell alike.

    What a regular expression can read is decided by the syntax, not by which interpreter
    was selected, so labelling by rung would split one answer across two names.
    """
    rule = {"tool": "run_shell_command", "action": "allow", "dialect": "posix"}
    assert rule_matches_dialect(rule, "posix") is True
    assert rule_matches_dialect(rule, "powershell") is False


def test_an_unlabelled_rule_still_matches_everything():
    """Every rule written before the label existed keeps working exactly as it did."""
    assert rule_matches_dialect({"tool": "*", "action": "allow"}, "powershell") is True
    assert rule_matches_dialect({"tool": "*", "action": "allow", "dialect": "*"}, "cmd") is True


def test_an_unlabelled_command_rule_is_unspecified_rather_than_universal():
    """TOOL-02's other half, and the reason the permissiveness above is safe.

    A rule matching on `args.command` was written against some shell's syntax and does not
    record which. On PowerShell there is no safe reading: applying it applies a pattern to a
    language it was not written for, and skipping it drops a rule its author relies on. So
    the rung refuses to exist rather than picking one of those.
    """
    rules = [
        {"tool": "run_shell_command", "action": "deny", "args": {"command": "rm -rf"}},
        {"tool": "run_shell_command", "action": "deny", "args": {"command": "dd"},
         "dialect": "posix"},
        {"tool": "web_fetch", "action": "allow"},
    ]
    offenders = unspecified_shell_rules(rules)
    assert [index for index, _ in offenders] == [0]


# ------------------------------------------------------------------ CFG-02


def test_a_complete_shell_block_loads(tmp_path):
    root = write_config(tmp_path, {
        "rules": [],
        "shell": {"path": "C:/pwsh/pwsh.exe", "dialect": "powershell", "allow_git_bash": True},
    })
    config = load_permission_config(project_root=root, user_root=root)
    assert config.shell is not None
    assert config.shell.dialect is ShellDialect.POWERSHELL
    assert config.shell.allow_git_bash is True


@pytest.mark.parametrize(
    "block,missing",
    [({"dialect": "powershell"}, "path"), ({"path": "C:/pwsh/pwsh.exe"}, "dialect")],
)
def test_half_a_shell_block_is_refused_and_names_the_missing_half(tmp_path, block, missing):
    """CFG-02: neither half can be derived from the other.

    A renamed launcher says nothing about its syntax, and naming `powershell` does not say
    which edition and so does not settle which rung. Two sources each supplying half a spec
    produce a configuration nobody can read back.
    """
    root = write_config(tmp_path, {"rules": [], "shell": block})
    with pytest.raises(PermissionConfigError) as exc:
        load_permission_config(project_root=root, user_root=root)
    assert missing in str(exc.value)


@pytest.mark.parametrize("raw,expected", [(True, True), (False, False)])
def test_the_ladder_flip_is_readable_from_the_user_file(tmp_path, raw, expected):
    """G09-02: LADDER-04's replacement gate wants a way back that is not a release."""
    root = write_config(tmp_path, {"rules": [], "shell": {"ladder": raw}})
    config = load_permission_config(project_root=root, user_root=root)
    assert config.shell is not None and config.shell.ladder is expected


def test_an_absent_ladder_key_stays_unset_rather_than_off(tmp_path):
    """``None`` and ``False`` are different answers, and the difference is load-bearing.

    Reading an absent key as ``False`` would make every unconfigured host opt out of the flip
    on the day it ships — the release would reach nobody, and nothing would say why.
    """
    root = write_config(tmp_path, {"rules": [], "shell": {"allow_git_bash": True}})
    config = load_permission_config(project_root=root, user_root=root)
    assert config.shell is not None and config.shell.ladder is None


def test_rung_is_not_a_configuration_field(tmp_path):
    """CFG-02: it is derived from the dialect, the target platform and the image's identity.

    Accepting it would let a configuration name a rung whose launcher was never checked,
    which is the one thing the derivation exists to prevent.
    """
    root = write_config(tmp_path, {"rules": [], "shell": {"rung": "pwsh"}})
    with pytest.raises(PermissionConfigError, match="rung"):
        load_permission_config(project_root=root, user_root=root)


def test_allow_git_bash_defaults_to_false(tmp_path):
    """LADDER-02: the switch is off unless someone turned it on."""
    root = write_config(tmp_path, {"rules": [], "shell": {}})
    config = load_permission_config(project_root=root, user_root=root)
    assert config.shell is not None and config.shell.allow_git_bash is False


# ------------------------------------------------------------------ CFG-01 / CFG-03


def test_a_workspace_shell_block_is_not_read(tmp_path):
    """CFG-01: shell configuration is user-level or host, never the workspace.

    That is a trust boundary rather than a filing convention: a block checked into a
    repository would let the repository choose the interpreter the agent runs.
    """
    project = tmp_path / "project"
    (project / ".agentao").mkdir(parents=True)
    (project / ".agentao" / "permissions.json").write_text(
        json.dumps({"rules": [], "shell": {"path": "/evil/sh", "dialect": "posix"}}),
        encoding="utf-8",
    )
    config = load_permission_config(project_root=project, user_root=None)
    assert config.shell is None


def test_the_config_is_one_record_carrying_all_three(tmp_path):
    """CFG-03: rules, sources and the shell block travel together through every root.

    The block previously had no route through any root at all, which is why this is a record
    and not a third return value: a tuple that grows a member is a shape every caller has to
    be edited to keep up with.
    """
    root = write_config(tmp_path, {
        "rules": [{"tool": "web_fetch", "action": "allow"}],
        "shell": {"path": "/usr/bin/bash", "dialect": "posix"},
    })
    config = load_permission_config(project_root=root, user_root=root)
    assert isinstance(config, PermissionConfig)
    assert len(config.rules) == 1
    assert config.sources and config.sources[0].startswith("user:")
    assert config.shell is not None


def test_every_composition_root_reads_the_same_record():
    """CFG-03: three roots reading three shapes is how a key ends up honoured on one path.

    Checked by reading the source rather than by driving all three, because two of them build
    an ACP session; what matters is that none of them still calls the older rule-only loader.
    """
    import agentao.acp.session_load as session_load
    import agentao.acp.session_new as session_new
    import agentao.embedding.factory as factory

    for module in (factory, session_new, session_load):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "load_permission_config" in text, module.__name__
        assert "load_permission_rules(" not in text, module.__name__

# ------------------------------------------------------------------ PR-7a: it reaches the runtime


def test_the_block_changes_what_the_local_executor_reports():
    """The whole point of PR-7a: the key had a parser and no consumer.

    ``shell.ladder`` validated, loaded and reached nothing — the escape hatch existed in
    configuration and not in the process. Off Windows the ladder answers ``Exhausted``,
    because a Windows target needs the native oracle; what matters here is that the two
    answers *differ*, which is what a value with a consumer looks like.
    """
    from agentao.capabilities import LocalShellExecutor
    from agentao.capabilities.shell_spec import Exhausted, ShellBlock, ShellSpec

    unset = LocalShellExecutor().shell_spec
    on = LocalShellExecutor(shell_block=ShellBlock(ladder=True)).shell_spec
    off = LocalShellExecutor(shell_block=ShellBlock(ladder=False)).shell_spec

    assert isinstance(unset, ShellSpec)
    assert isinstance(off, ShellSpec) and off.rung is unset.rung
    assert isinstance(on, Exhausted), on


def test_the_executor_reports_one_spec_object_per_call(monkeypatch):
    """SPEC-07b: a call holds one spec until re-resolution swaps it.

    Minting a fresh one per read would also re-run the ladder per read, which on Windows
    means a fresh ``AccessCheck`` walk to the volume root on every shell call.
    """
    from agentao.capabilities import LocalShellExecutor

    executor = LocalShellExecutor()
    assert executor.shell_spec is executor.shell_spec


def test_the_factory_gives_the_executor_the_block_it_loaded(tmp_path, monkeypatch):
    """CFG-03: the block travels with the rules, and now it lands somewhere.

    Asserted through the factory rather than by calling the loader and the constructor in
    sequence, because composing them by hand is a restatement of the code rather than a test
    of it — the question is whether the composition root actually does it.
    """
    from unittest.mock import Mock, patch

    from agentao.capabilities import LocalShellExecutor
    from agentao.embedding import build_from_environment

    # The loader reads the *user* scope, which is ``~/.agentao``, so the file has to land
    # where ``user_root()`` will look rather than beside the project.
    user_dir = tmp_path / ".agentao"
    user_dir.mkdir()
    write_config(user_dir, {"rules": [], "shell": {"ladder": True}})
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    with patch("agentao.agent.LLMClient") as mock_llm_cls:
        mock_llm = Mock()
        mock_llm.logger = Mock()
        mock_llm.model = "gpt-test"
        mock_llm.api_key = "test-key"
        mock_llm.base_url = "https://api.example.com/v1"
        mock_llm.temperature = 0.2
        mock_llm_cls.return_value = mock_llm
        agent = build_from_environment(working_directory=tmp_path)

    assert isinstance(agent.shell, LocalShellExecutor)
    assert agent.shell._shell_block is not None
    assert agent.shell._shell_block.ladder is True
