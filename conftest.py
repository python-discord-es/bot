"""Root conftest.py.

Every module under ``comandos/`` (and ``configuration.py`` itself) calls
``Config()`` at *import time*, and ``Config.__init__`` reads ``config.toml``
from the current working directory, exiting the process if it's missing or
incomplete. ``config.toml`` is git-ignored (it holds real bot secrets), so it
won't exist in a fresh checkout or in CI.

To make the test modules importable at all, we build a throwaway
``config.toml`` plus the ``logs/`` directory it expects, and ``chdir`` into
that sandbox *before* pytest imports any test module. This has to happen as
plain module-level code (not inside a fixture) because pytest imports
conftest.py files before it collects/imports the test modules that in turn
``import comandos.flood`` etc.
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent

_SANDBOX = Path(tempfile.mkdtemp(prefix="pyes-bot-tests-"))
(_SANDBOX / "logs").mkdir()
(_SANDBOX / "config.toml").write_text(
    """
[bot]
token = "test-token"
id = 111111111111111111
log_file = "logs/bot_log.csv"

[moderation]
log_file = "logs/mod_log.csv"
channel_id = 222222222222222222
role = "Coordinacion"
muted_role = "Muted"

[server]
guild = 333333333333333333

[channels]
    [channels.eventos]
    main = 444444444444444444
    moderation = 555555555555555555
    submission = 666666666666666666
"""
)

# A couple of commands read files via relative paths at call time (not
# import time) - e.g. ping.py's "resources/llama.gif". Make sure those are
# still reachable from the sandboxed working directory.
if (_REPO_ROOT / "resources").is_dir():
    shutil.copytree(_REPO_ROOT / "resources", _SANDBOX / "resources")

os.chdir(_SANDBOX)


@pytest.fixture(scope="session")
def sandbox_dir():
    """The temporary directory tests are running from."""
    return _SANDBOX


@pytest.fixture(scope="session")
def repo_root():
    """The actual repository root, for tests that need real project files."""
    return _REPO_ROOT


@pytest.fixture
def config():
    """The (singleton) Config instance, backed by the sandboxed config.toml."""
    from configuration import Config

    return Config()


@pytest.fixture
def isolated_logs(config, tmp_path, monkeypatch):
    """Point every log file Config knows about at a fresh, empty file.

    Config is a singleton shared across the whole test session, and several
    of its log paths are appended to by the code under test (e.g.
    ``add_spam_message``). Without this, one test's writes would leak into
    the next test that also touches those files.
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    for attr, filename in [
        ("log_spam_file", "spam_log.csv"),
        ("log_image_spam_file", "image_spam_log.csv"),
        ("log_mod_file", "mod_log.csv"),
        ("log_accepted_file", "mod_log_accepted.csv"),
        ("log_rejected_file", "mod_log_rejected.csv"),
        ("log_main_file", "main_log.csv"),
        ("log_file", "bot_log.csv"),
        ("log_gdpr_file", "gdpr_erasure_log.csv"),
    ]:
        path = logs_dir / filename
        path.write_text("\n")
        monkeypatch.setattr(config, attr, path)

    return config


@pytest.fixture(autouse=True)
def patched_message_delete(monkeypatch):
    """The production code deletes messages via ``discord.Message.delete(message)``
    (an unbound call on the real class) rather than ``message.delete()``, so
    fakes that aren't real ``discord.Message`` instances need this patched to
    avoid hitting real discord.py internals/HTTP calls.
    """
    import discord
    from unittest.mock import AsyncMock

    mock_delete = AsyncMock()
    monkeypatch.setattr(discord.Message, "delete", mock_delete)
    return mock_delete
