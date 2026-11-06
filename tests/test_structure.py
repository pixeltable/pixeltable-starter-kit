"""Advertised apps have the expected file structure."""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from tests.conftest import APPS, EXPECTED_FILES, REMOVED_PATHS, ROOT

_DEPRECATED_APIS: list[tuple[str, str]] = [
    ("FrameIterator", "Use frame_iterator from pixeltable.functions.video"),
    ("openai.vision", "Use openai.chat_completions with image_url content blocks"),
    ("from pixeltable.iterators import", "Use pixeltable.functions.* iterators instead"),
    (".add_index(", "Use EmbeddingIndex on the model"),
]

_BANNED_APPLY: tuple[str, ...] = (
    "pxt serve",
    "[[tool.pixeltable.service]]",
    "tool.pixeltable.service",
    "python schema.py",
    "pxt schema update schema.py",
    "pxt.create_table",
    "setup_pixeltable",
    "add_embedding_index",
    "pxt db create",
    "add_computed_column",
    "declarative multimodal data infrastructure",
)

_PXT_SERVE_RE = re.compile(r"pxt serve(?!ice)")
_HOSTED_SERVICE_RUN_RE = re.compile(r"pxt service run[^\n]*pxt://")
_HOSTED_SERVICE_UPDATE = "pxt service update app.py pxt://"

_CONTRACT_MD_FILES: tuple[str, ...] = ("README.md", "AGENTS.md", "CONTRIBUTING.md")
_CONTRACT_MD_DIRS: tuple[str, ...] = ("chat-agent", "video-search", "openai-360")


def _contract_markdown_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    skip = {".venv", ".git", "node_modules", "tests"}
    for relpath in _CONTRACT_MD_FILES:
        path = ROOT / relpath
        if path.is_file():
            files.append(path)
    for dirname in _CONTRACT_MD_DIRS:
        folder = ROOT / dirname
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.md"):
            if skip & set(path.parts):
                continue
            files.append(path)
    return files


def _banned_apply_present(text: str, token: str) -> bool:
    if token == "pxt serve":
        return _PXT_SERVE_RE.search(text) is not None
    return token in text


class TestAppFiles:
    @pytest.mark.parametrize("app", APPS)
    def test_app_directory_exists(self, app: str) -> None:
        assert (ROOT / app).is_dir(), f"{app}/ directory missing"

    @pytest.mark.parametrize("app", APPS)
    def test_expected_files_exist(self, app: str) -> None:
        for relpath in EXPECTED_FILES[app]:
            fpath = ROOT / app / relpath
            assert fpath.is_file(), f"{app}/{relpath} missing"

    @pytest.mark.parametrize("app", APPS)
    def test_uv_lock_exists(self, app: str) -> None:
        assert (ROOT / app / "uv.lock").is_file(), f"{app}/uv.lock missing"

    @pytest.mark.parametrize("relpath", REMOVED_PATHS)
    def test_removed_paths_absent(self, relpath: str) -> None:
        assert not (ROOT / relpath).exists(), f"{relpath} should not ship"


class TestPythonSyntax:
    @pytest.mark.parametrize("app", APPS)
    def test_app_python_files_parse(self, app: str) -> None:
        for py_file in (ROOT / app).rglob("*.py"):
            if ".venv" in py_file.parts:
                continue
            source = py_file.read_text(encoding="utf-8")
            try:
                ast.parse(source, filename=str(py_file))
            except SyntaxError as exc:
                pytest.fail(f"Syntax error in {py_file.relative_to(ROOT)}: {exc}")


class TestDocumentation:
    @pytest.mark.parametrize(
        "relpath",
        ["README.md", "AGENTS.md", ".env.example"],
    )
    def test_root_docs_exist(self, relpath: str) -> None:
        assert (ROOT / relpath).is_file(), f"{relpath} missing from repo root"

    @pytest.mark.parametrize("app", APPS)
    def test_app_has_readme(self, app: str) -> None:
        assert (ROOT / app / "README.md").is_file(), f"{app}/README.md missing"


class TestApplicationFile:
    @pytest.mark.parametrize("app", APPS)
    def test_app_is_tablemodel(self, app: str) -> None:
        source = (ROOT / app / "app.py").read_text(encoding="utf-8")
        assert "model_base()" in source
        assert "FastAPIRouter" in source
        assert "__indexes__" in source
        assert "add_embedding_index" not in source
        assert "pxt.create_table" not in source
        assert "pxt.Required" not in source

    def test_chat_agent_uses_return_rows(self) -> None:
        source = (ROOT / "chat-agent" / "app.py").read_text(encoding="utf-8")
        assert "return_rows=True" in source

    @pytest.mark.parametrize("app", APPS)
    def test_no_functions_py(self, app: str) -> None:
        assert not (ROOT / app / "functions.py").is_file(), f"{app}/functions.py: UDFs stay in app.py"


class TestNoAntiPatterns:
    _BANNED_ENV_VAR = "PYTHON" + "PATH"

    def test_no_banned_env_var_references(self) -> None:
        hits: list[str] = []
        skip = {".venv", ".git", "node_modules", "tests"}
        for ext in ("*.py", "*.toml", "*.yml", "*.yaml", "*.md"):
            for f in ROOT.rglob(ext):
                if skip & set(f.parts):
                    continue
                text = f.read_text(encoding="utf-8", errors="ignore")
                if self._BANNED_ENV_VAR in text:
                    hits.append(str(f.relative_to(ROOT)))
        assert hits == [], f"{self._BANNED_ENV_VAR} found in: {hits}"

    @staticmethod
    def _is_pxt_query_decorator(node: ast.AST) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return node.func.attr == "query" and isinstance(node.func.value, ast.Name) and node.func.value.id == "pxt"
        if isinstance(node, ast.Attribute):
            return node.attr == "query" and isinstance(node.value, ast.Name) and node.value.id == "pxt"
        return False

    def test_no_sim_alias_in_pxt_query(self) -> None:
        hits: list[str] = []
        skip = {".venv", ".git", "node_modules", "tests"}
        for folder in APPS:
            for py_file in (ROOT / folder).rglob("*.py"):
                if skip & set(py_file.parts):
                    continue
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef):
                        continue
                    if not any(self._is_pxt_query_decorator(d) for d in node.decorator_list):
                        continue
                    for sub in ast.walk(node):
                        if (
                            isinstance(sub, ast.keyword)
                            and sub.arg == "sim"
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id == "sim"
                        ):
                            hits.append(f"{py_file.relative_to(ROOT)}:{node.name}")
        assert hits == [], "sim=sim in @pxt.query found:\n" + "\n".join(hits)

    def test_no_deprecated_pixeltable_apis(self) -> None:
        hits: list[str] = []
        skip = {".venv", ".git", "node_modules", "tests"}
        for folder in APPS:
            for py_file in (ROOT / folder).rglob("*.py"):
                if skip & set(py_file.parts):
                    continue
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                for token, _ in _DEPRECATED_APIS:
                    if token in text:
                        hits.append(f"{py_file.relative_to(ROOT)}: {token}")
        assert hits == [], "Deprecated Pixeltable APIs found:\n" + "\n".join(hits)

    def test_one_apply_path(self) -> None:
        hits: list[str] = []
        skip = {".venv", ".git", "node_modules", "tests"}
        scan_roots = [
            ROOT / "chat-agent",
            ROOT / "video-search",
            ROOT / "openai-360",
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "CONTRIBUTING.md",
        ]
        for root in scan_roots:
            paths = [root] if root.is_file() else list(root.rglob("*"))
            for f in paths:
                if not f.is_file() or skip & set(f.parts):
                    continue
                if f.suffix not in {".py", ".toml", ".md", ".yml", ".yaml"}:
                    continue
                text = f.read_text(encoding="utf-8", errors="ignore")
                for token in _BANNED_APPLY:
                    if _banned_apply_present(text, token):
                        hits.append(f"{f.relative_to(ROOT)}: {token}")
        assert hits == [], "Dead apply path found:\n" + "\n".join(hits)

    def test_no_hosted_pxt_service_run(self) -> None:
        hits: list[str] = []
        for f in _contract_markdown_files():
            text = f.read_text(encoding="utf-8", errors="ignore")
            for match in _HOSTED_SERVICE_RUN_RE.finditer(text):
                hits.append(f"{f.relative_to(ROOT)}: {match.group(0)}")
        assert hits == [], "pxt service run is local only:\n" + "\n".join(hits)

    def test_cloud_teaches_hosted_service_update(self) -> None:
        missing: list[str] = []
        for relpath in ("README.md", "AGENTS.md"):
            text = (ROOT / relpath).read_text(encoding="utf-8")
            if _HOSTED_SERVICE_UPDATE not in text:
                missing.append(relpath)
        assert missing == [], "Cloud copy must teach hosted pxt service update:\n" + "\n".join(missing)

    def test_no_em_dashes(self) -> None:
        hits: list[str] = []
        for f in _contract_markdown_files():
            if "\u2014" in f.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(f.relative_to(ROOT)))
        assert hits == [], f"U+2014 em dash found in: {hits}"
