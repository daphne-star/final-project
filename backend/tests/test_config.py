"""Where the API key is allowed to live.

The key is not in this repository and never will be, so the only thing that
makes the app runnable on a fresh clone is finding a .env somewhere sensible.
Two locations are supported: the repository's own folder, and the folder it
was cloned into.

The precedence is worth a test rather than a comment. pydantic-settings
applies a sequence of env files in order and lets *later* entries win, so the
tuple reads back to front relative to the rule it implements. Reversing it is
a one-character mistake that silently makes a shared key beat a project's own.

These tests deliberately probe a dummy variable rather than PORTKEY_API_KEY.
An assertion on the real setting prints the real key into the test output on
failure, which is how a secret ends up in a CI log.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import BACKEND_DIR, PARENT_DIR, REPO_DIR, env_files

#: Stands in for the real key. Never sensitive, whatever the test does.
PROBE_VAR = "GHOSTBOARD_ENV_PROBE"


@pytest.fixture(autouse=True)
def _ignore_ambient_environment(monkeypatch):
    """Test the files, not the machine.

    A real environment variable outranks every .env file, and on a developer
    box the key is often exported globally. Without this the tests below pass
    or fail on the host's configuration rather than on the resolution order.
    """
    monkeypatch.delenv(PROBE_VAR, raising=False)


def _probe(repo_dir: Path) -> str:
    """Read the dummy variable through the real resolution order."""

    class Probe(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=env_files(repo_dir), env_file_encoding="utf-8", extra="ignore"
        )
        ghostboard_env_probe: str = "unset"

    return Probe().ghostboard_env_probe


def _layout(tmp_path: Path) -> Path:
    """A clone at <tmp>/parent/repo, mirroring the real directory shape."""
    repo = tmp_path / "parent" / "repo"
    (repo / "backend").mkdir(parents=True)
    return repo


def _write(path: Path, value: str) -> None:
    path.write_text(f"{PROBE_VAR}={value}\n", encoding="utf-8")


def test_the_two_locations_are_the_repo_and_the_folder_above(tmp_path):
    repo = _layout(tmp_path)
    assert env_files(repo) == (repo.parent / ".env", repo / ".env")


def test_a_key_in_the_folder_above_is_found(tmp_path):
    """How this checkout is configured: one shared .env outside the repo."""
    repo = _layout(tmp_path)
    _write(repo.parent / ".env", "from-above")

    assert _probe(repo) == "from-above"


def test_a_key_in_the_repo_folder_is_found(tmp_path):
    repo = _layout(tmp_path)
    _write(repo / ".env", "from-repo")

    assert _probe(repo) == "from-repo"


def test_the_repo_folder_wins_when_both_exist(tmp_path):
    """A project's own key overrides a shared one. This is the rule the tuple
    ordering implements, and the one most easily inverted."""
    repo = _layout(tmp_path)
    _write(repo.parent / ".env", "from-above")
    _write(repo / ".env", "from-repo")

    assert _probe(repo) == "from-repo"


def test_neither_file_is_not_an_error(tmp_path):
    """A fresh clone with no .env must still import and start, so the app can
    report a missing key rather than failing to load."""
    repo = _layout(tmp_path)
    assert _probe(repo) == "unset"


def test_a_real_environment_variable_still_wins(tmp_path, monkeypatch):
    """Documenting the precedence above the files, because it surprises people:
    an exported variable beats both .env files. That is what makes a container
    or a CI secret work without any file at all."""
    repo = _layout(tmp_path)
    _write(repo / ".env", "from-repo")
    monkeypatch.setenv(PROBE_VAR, "from-the-process-environment")

    assert _probe(repo) == "from-the-process-environment"


def test_the_paths_are_resolved_from_this_file_not_the_cwd():
    """pytest, uvicorn and the demo scripts all run from different places."""
    assert BACKEND_DIR.name == "backend"
    assert REPO_DIR == BACKEND_DIR.parent
    assert PARENT_DIR == REPO_DIR.parent
    assert (BACKEND_DIR / "app" / "core" / "config.py").exists()
