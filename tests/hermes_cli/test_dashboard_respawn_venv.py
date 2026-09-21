"""A captured base-Python argv must retain the launcher's virtual environment."""
import subprocess
import sys
import time
import venv
import pytest
from pathlib import Path
from hermes_cli.main_dashboard import _respawn_dashboard_processes


@pytest.mark.parametrize("framework", [False, True])
def test_respawn_preserves_launcher_venv(tmp_path, monkeypatch, framework):
    env = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(env)
    python = env / "bin" / "python"
    launcher = tmp_path / "hermes"
    result = tmp_path / "prefix.txt"
    launcher.write_text(f"#!{python}\nimport sys\nfrom pathlib import Path\nPath({str(result)!r}).write_text(sys.prefix)\n")
    launcher.chmod(0o755)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    base = python.resolve()
    if framework:
        base = Path(sys.base_prefix) / "Resources/Python.app/Contents/MacOS/Python"
        if not base.exists():
            pytest.skip("macOS framework interpreter only")
    command = [str(base), str(launcher), "serve", "--port", "9119"]
    # Prove replaying the original captured argv loses the virtual environment.
    subprocess.run(command, check=True)
    assert result.read_text() != str(env)
    result.unlink()
    assert _respawn_dashboard_processes([command]) == []
    deadline = time.monotonic() + 10
    while not result.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert result.read_text() == str(env)
