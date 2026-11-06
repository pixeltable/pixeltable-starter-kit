"""Schema import smoke tests.

These tests require Pixeltable (embedded Postgres) and download embedding models.
They are marked `slow` and skipped in fast CI runs. Run with:

    uv run pytest tests/test_schema.py -v --run-slow
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import ROOT

pytestmark = pytest.mark.slow

_SCHEMA_TARGETS: list[tuple[str, str]] = [
    (str(ROOT / "chat-agent"), 'import app; print("OK")'),
    (str(ROOT / "video-search"), 'import app; print("OK")'),
    (str(ROOT / "openai-360"), 'import app; print("OK")'),
]


def _python_command(cwd: str) -> list[str]:
    venv_python = Path(cwd) / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return [str(venv_python)]
    if shutil.which("uv") and (Path(cwd) / "pyproject.toml").is_file():
        return ["uv", "run", "python"]
    return [sys.executable]


def _run_import(cwd: str, code: str, home: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        _python_command(cwd) + ["-c", code],
        cwd=cwd,
        env={**os.environ, "PIXELTABLE_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestSchemaImports:
    def test_all_schemas_import_cleanly(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        for index, (cwd, code) in enumerate(_SCHEMA_TARGETS):
            home = tmp_path_factory.mktemp(f"pxt-smoke-{index}")
            result = _run_import(cwd, code, home)
            label = Path(cwd).relative_to(ROOT)
            assert result.returncode == 0, f"{label} import failed:\n{result.stderr}"
            assert "OK" in result.stdout, f"{label} import did not print OK:\n{result.stdout}"
