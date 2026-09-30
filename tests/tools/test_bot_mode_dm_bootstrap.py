"""Bot handoff runners must activate dependencies before probing the recipient."""

import json
import os
import subprocess
import sys
from pathlib import Path

from pm.environments import install_key, site_packages
from tools import bot_mode_dm


def test_bare_python_delivery_activates_dependencies_and_preserves_target_scope(tmp_path):
    # PM launches the gateway with store Python plus an activated dependency tree.
    # Its background child gets that bare interpreter, without the parent's sys.path.
    root = Path(bot_mode_dm.__file__).resolve().parents[1]
    home = tmp_path / ".hermes"
    state = home / "installs" / install_key(root)
    generation = state / "environments" / "test" / "venv"
    packages = site_packages(generation)
    packages.mkdir(parents=True)
    (generation / "pyvenv.cfg").write_text(
        f"version = {sys.version_info.major}.{sys.version_info.minor}.0\n", encoding="utf-8"
    )
    # Use the test environment's real dependencies through the real PM activation.
    dependency_paths = [p for p in sys.path if Path(p).name in {"site-packages", "dist-packages"}]
    assert dependency_paths
    (packages / "test-dependencies.pth").write_text("\n".join(dependency_paths) + "\n", encoding="utf-8")
    (state / "facts.json").write_text(
        json.dumps({"packages": {"venv": {"environment": str(generation)}}}), encoding="utf-8"
    )
    child = tmp_path / "recipient.py"
    child.write_text(
        "import json, os, pathlib, sys\n"
        "print(json.dumps({'home': os.environ['HERMES_HOME'], "
        "'author': json.loads(os.environ['HERMES_TURN_AUTHOR']), "
        "'message': pathlib.Path(sys.argv[-1]).read_text(encoding='utf-8')}))\n",
        encoding="utf-8",
    )
    author = {"id": "bot:sender", "name": "sender", "is_bot": True}
    env = {**os.environ, "HERMES_HOME": str(home), "HERMES_DISABLE_LAZY_INSTALLS": "1"}
    env.pop("PYTHONPATH", None)
    for index, profile in enumerate(("alpha", "beta", "alpha")):
        target = home / "profiles" / profile
        target.mkdir(parents=True, exist_ok=True)
        payload = tmp_path / f"message-{index}.txt"
        payload.write_text(f"handoff {index}", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(Path(bot_mode_dm.__file__).resolve()),
             "--run-delivery", "--author", json.dumps(author), "query-file", str(payload),
             "--profile-home", str(target), sys.executable, str(child)],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {
            "home": str(target), "author": author, "message": f"handoff {index}"
        }
        assert not payload.exists()
