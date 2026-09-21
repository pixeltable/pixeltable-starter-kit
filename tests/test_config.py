"""TOML configuration for the two apps."""

from __future__ import annotations

import re
import tomllib

import pytest

from tests.conftest import APPS, ROOT


def _load_toml(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


class TestAppPyprojectToml:
    @pytest.mark.parametrize("app", APPS)
    def test_toml_parses(self, app: str) -> None:
        cfg = _load_toml(str(ROOT / app / "pyproject.toml"))
        assert "project" in cfg
        assert "name" in cfg["project"]

    @pytest.mark.parametrize("app", APPS)
    def test_requires_python(self, app: str) -> None:
        cfg = _load_toml(str(ROOT / app / "pyproject.toml"))
        assert cfg["project"].get("requires-python") == ">=3.11"

    @staticmethod
    def _declared_floor(app: str) -> str:
        cfg = _load_toml(str(ROOT / app / "pyproject.toml"))
        deps = cfg["project"].get("dependencies", [])
        pxt = [d for d in deps if d.startswith("pixeltable")]
        assert len(pxt) == 1, f"{app} must declare exactly one pixeltable dependency, got {pxt}"
        spec = pxt[0]
        assert ">=" in spec, f"{app} must declare a pixeltable floor, got {spec!r}"
        return spec.split(">=", 1)[1].strip().strip('"')

    @staticmethod
    def _locked_version(app: str) -> str:
        """The pixeltable version resolved in that app's uv.lock."""
        text = (ROOT / app / "uv.lock").read_text(encoding="utf-8")
        m = re.search(r'^name = "pixeltable"\nversion = "([^"]+)"', text, re.MULTILINE)
        assert m is not None, f"{app}/uv.lock does not pin a pixeltable version"
        return m.group(1)

    def test_both_apps_declare_the_same_floor(self) -> None:
        floors = {app: self._declared_floor(app) for app in APPS}
        assert len(set(floors.values())) == 1, f"apps disagree on the pixeltable floor: {floors}"

    @pytest.mark.parametrize("app", APPS)
    def test_floor_matches_lockfile(self, app: str) -> None:
        """The floor is a compatibility claim; the lock is what ships (Dockerfiles use --frozen).

        Asserting they agree means a relock without a floor bump -- or the reverse -- fails here
        rather than silently shipping a README that says one thing and an image that does another.
        """
        floor, locked = self._declared_floor(app), self._locked_version(app)
        assert floor == locked, (
            f"{app}: pyproject floor >={floor} but uv.lock pins {locked}; bump the floor and re-run `uv lock` together"
        )

    def test_chat_agent_anthropic_v1_or_later(self) -> None:
        """pixeltable>=0.7.8 imports httpx2, which only ships with anthropic>=1.3.

        An anthropic<1 pin resolves httpx 0.28.x and fails at import time inside
        pixeltable.functions.anthropic, so the floor must stay at 1.3 or above.
        """
        cfg = _load_toml(str(ROOT / "chat-agent" / "pyproject.toml"))
        deps = cfg["project"].get("dependencies", [])
        anthropic = [d for d in deps if d.startswith("anthropic")]
        assert len(anthropic) == 1, f"chat-agent must declare exactly one anthropic dependency, got {anthropic}"
        spec = anthropic[0]
        assert "<1" not in spec, f"anthropic<1 is incompatible with pixeltable>=0.7.8 (httpx2), got {spec!r}"
        m = re.search(r">=\s*(\d+)\.(\d+)", spec)
        assert m is not None, f"chat-agent must declare an anthropic floor, got {spec!r}"
        assert (int(m.group(1)), int(m.group(2))) >= (1, 3), f"anthropic floor must be >=1.3, got {spec!r}"

    def test_chat_agent_no_sampling_params(self) -> None:
        """anthropic>=1.0 removed temperature/top_p/top_k from messages.create; passing them raises TypeError."""
        source = (ROOT / "chat-agent" / "app.py").read_text(encoding="utf-8")
        for token in ("temperature", "top_p", "top_k"):
            assert token not in source, f"chat-agent/app.py passes {token}; anthropic SDK 1.x rejects it"


class TestProjectRoot:
    @pytest.mark.parametrize("app", APPS)
    def test_app_has_pixeltable_toml(self, app: str) -> None:
        text = (ROOT / app / "pixeltable.toml").read_text(encoding="utf-8")
        assert "[[pixeltable.database]]" in text


class TestBuildSystem:
    @pytest.mark.parametrize("app", APPS)
    def test_app_has_build_system(self, app: str) -> None:
        cfg = _load_toml(str(ROOT / app / "pyproject.toml"))
        assert "build-system" in cfg
        setuptools = cfg.get("tool", {}).get("setuptools", {})
        assert "app" in setuptools.get("py-modules", [])


class TestNoTomlService:
    @pytest.mark.parametrize("app", APPS)
    def test_app_has_no_service_table(self, app: str) -> None:
        cfg = _load_toml(str(ROOT / app / "pyproject.toml"))
        services = cfg.get("tool", {}).get("pixeltable", {}).get("service")
        assert not services, f"{app} still has [tool.pixeltable.service]"
