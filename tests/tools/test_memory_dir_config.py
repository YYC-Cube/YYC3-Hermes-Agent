"""``memory.dir`` relocates the built-in MEMORY.md/USER.md store.

Contract: empty keeps ``<HERMES_HOME>/memories``; a relative value resolves under
HERMES_HOME (a profile setting cannot escape its home by accident); an absolute value
is honoured as written.
"""

from hermes_cli.config import save_config
from hermes_constants import get_hermes_home
from tools.memory_tool import get_memory_dir


def test_default_store_under_hermes_home():
    assert get_memory_dir() == get_hermes_home() / "memories"


def test_relative_dir_resolves_under_hermes_home():
    save_config({"memory": {"dir": "vault/mem"}})
    assert get_memory_dir() == get_hermes_home() / "vault" / "mem"


def test_absolute_dir_is_honoured(tmp_path):
    target = tmp_path / "elsewhere"
    save_config({"memory": {"dir": str(target)}})
    assert get_memory_dir() == target


def test_empty_dir_falls_back_to_the_default():
    save_config({"memory": {"dir": "vault/mem"}})
    assert get_memory_dir() != get_hermes_home() / "memories"
    save_config({"memory": {"dir": ""}})
    assert get_memory_dir() == get_hermes_home() / "memories"
