"""Shared constants and fixtures for starter kit tests."""

from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

APPS: list[str] = ["chat-agent", "video-search", "openai-360"]

EXPECTED_FILES: dict[str, list[str]] = {
    "chat-agent": [
        "pyproject.toml",
        "pixeltable.toml",
        "app.py",
        "Dockerfile",
        "docker-compose.yml",
    ],
    "video-search": [
        "pyproject.toml",
        "pixeltable.toml",
        "app.py",
        "Dockerfile",
        "docker-compose.yml",
    ],
    "openai-360": [
        "pyproject.toml",
        "pixeltable.toml",
        "app.py",
        "seed.py",
        "Dockerfile",
        "docker-compose.yml",
    ],
}

REMOVED_PATHS: list[str] = [
    "templates",
    "backend",
    "frontend",
    "deploy",
    "docs",
    "sdk",
    "serving",
    "batch",
    "examples",
    "gallery.json",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow schema import smoke tests (needs Pixeltable + model downloads)",
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("slow") and not item.config.getoption("--run-slow"):
        pytest.skip("Slow test: pass --run-slow to enable.")
