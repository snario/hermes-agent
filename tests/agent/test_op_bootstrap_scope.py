"""Profile-local bootstrap authentication survives routed runtime scopes."""
import os
from agent import secret_scope as ss
from agent.vault_backends.onepassword import OnePasswordLoginBackend


def test_bootstrap_token_isolated_across_profile_alternation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "launch"))
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "launch-token")
    homes = [tmp_path / "a", tmp_path / "b", tmp_path / "empty"]
    for home in homes:
        home.mkdir()
    for home, value in zip(homes, ("a-token", "b-token")):
        (home / ".op.env").write_text(f"OP_SERVICE_ACCOUNT_TOKEN={value}\n")
    before = dict(os.environ)
    ss.set_multiplex_active(True)
    try:
        for home, expected in [(homes[0], "a-token"), (homes[1], "b-token"), (homes[0], "a-token"), (homes[2], None)]:
            token = ss.set_secret_scope(ss.build_profile_secret_scope(home), profile_home=str(home))
            try:
                assert ss.get_secret("OP_SERVICE_ACCOUNT_TOKEN") == expected
                assert OnePasswordLoginBackend().is_unlocked() == bool(expected)
            finally:
                ss.reset_secret_scope(token)
        assert dict(os.environ) == before
    finally:
        ss.set_multiplex_active(False)


def test_profile_env_overrides_bootstrap_and_removal_revokes_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / ".op.env").write_text("OP_SERVICE_ACCOUNT_TOKEN=bootstrap\nOP_CONNECT_TOKEN=own-connect\n")
    (tmp_path / ".env").write_text("OP_SERVICE_ACCOUNT_TOKEN=explicit\n")
    scope = ss.build_profile_secret_scope(tmp_path)
    assert scope["OP_SERVICE_ACCOUNT_TOKEN"] == "explicit"
    assert scope["OP_CONNECT_TOKEN"] == "own-connect"
    (tmp_path / ".op.env").unlink()
    (tmp_path / ".env").write_text("OP_SERVICE_ACCOUNT_TOKEN=\n")
    scope = ss.build_profile_secret_scope(tmp_path)
    assert scope["OP_SERVICE_ACCOUNT_TOKEN"] == ""
    assert "OP_CONNECT_TOKEN" not in scope
