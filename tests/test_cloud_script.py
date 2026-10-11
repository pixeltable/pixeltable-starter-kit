"""Exercise the Cloud script without Cloud credentials, network calls, or polling delays."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import APPS, ROOT

URI = "pxt://test-org:main"
CLAIM_URL = "https://example.invalid/claim/test-trial"
RunResult = tuple[subprocess.CompletedProcess[str], list[list[Any]]]


@pytest.fixture
def run_cloud_script(tmp_path: pathlib.Path) -> Callable[..., RunResult]:
    container = tmp_path / ".devcontainer"
    container.mkdir()
    shutil.copy(ROOT / ".devcontainer" / "cloud.sh", container / "cloud.sh")
    for app in APPS:
        (tmp_path / app).mkdir()
        (tmp_path / app / "pixeltable.toml").write_text("", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent(r"""
            import json
            import os
            import pathlib
            import sys
            import types

            config = json.loads(os.environ["PXT_TEST_CONFIG"])
            log = pathlib.Path(os.environ["PXT_TEST_LOG"])

            def record(call):
                with log.open("a") as f:
                    f.write(json.dumps(call) + "\n")

            assert sys.argv[1:3] == ["run", "--quiet"]
            args = sys.argv[3:]
            if args[0] == "pxt":
                command = args[1:]
                record(command)
                if command[:2] == config.get("fail_command"):
                    sys.exit("Simulated CLI failure")
                if command[0] == "new":
                    print(json.dumps({"org": "test-org", "db": "main", "claim_url": config.get("claim_url")}))
                elif command[:2] == ["db", "status"]:
                    polls = sum(json.loads(line)[:2] == ["db", "status"] for line in log.read_text().splitlines())
                    states = config.get("states", ["AVAILABLE"])
                    print(json.dumps({"current": {"state": states[min(polls - 1, len(states) - 1)]}}))
                elif command[:2] == ["service", "list"]:
                    print(json.dumps([
                        {"name": name, "endpoint": "https://example.invalid/service"}
                        for name in ("agent", "videointel")
                    ]))
                elif command[0] == "whoami":
                    print(json.dumps({"api_url": "https://example.invalid/api"}))
            elif args[0] == "python":
                def response(status, body):
                    return types.SimpleNamespace(
                        status_code=status, is_success=200 <= status < 300,
                        text=json.dumps(body), json=lambda: body,
                    )

                class Client:
                    def __init__(self, **kwargs):
                        pass

                    def post(self, path, *, json):
                        self.doc = json
                        record(["http", "post", path, json])
                        return response(config.get("insert_status", 200), {"uuid": "test-document"})

                    def get(self, path, *, params):
                        record(["http", "get", path, params])
                        rows = config.get("search_rows", [{"text": self.doc["body"]}])
                        return response(config.get("search_status", 200), {"rows": rows})

                httpx = types.ModuleType("httpx")
                httpx.Client = Client
                sys.modules["httpx"] = httpx
                sys.modules["pixeltable"] = types.ModuleType("pixeltable")
                service = types.ModuleType("pixeltable.service")
                service.session_cache = types.SimpleNamespace(load_credential=lambda url: None)
                sys.modules["pixeltable.service"] = service
                sys.argv = args[1:]
                exec(compile(sys.stdin.read(), "<cloud smoke test>", "exec"))
            else:
                sys.exit(f"Unexpected uv command: {args}")
            """).lstrip(),
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    fake_sleep = bin_dir / "sleep"
    fake_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_sleep.chmod(0o755)

    def run(app: str = "chat-agent", uri: str | None = None, **config: Any) -> RunResult:
        log = tmp_path / "calls.jsonl"
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "ANTHROPIC_API_KEY": config.get("anthropic_key", ""),
            "PIXELTABLE_API_KEY": config.get("api_key", "test-api-key"),
            "PXT_TEST_CONFIG": json.dumps({"claim_url": CLAIM_URL, **config}),
            "PXT_TEST_LOG": str(log),
        }
        args = ["bash", str(container / "cloud.sh"), app]
        if uri is not None:
            args.append(uri)
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30, check=False)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls

    return run


@pytest.mark.parametrize("uri", [None, URI])
def test_key_reaches_database_before_schema(run_cloud_script: Callable[..., RunResult], uri: str | None) -> None:
    result, calls = run_cloud_script(uri=uri, anthropic_key="test-anthropic-key")
    assert result.returncode == 0, result.stderr
    update = calls.index(["db", "update", URI, "-f"])
    secret = calls.index(["secret", "set", "pxt://test-org", "ANTHROPIC_API_KEY=test-anthropic-key"])
    restart = calls.index(["db", "restart", URI])
    schema = calls.index(["schema", "update", "app.py", URI, "-f"])
    assert update < secret < restart < schema


@pytest.mark.parametrize("app,key", [("chat-agent", ""), ("video-search", "test-anthropic-key")])
def test_no_secret_restart_when_unneeded(run_cloud_script: Callable[..., RunResult], app: str, key: str) -> None:
    result, calls = run_cloud_script(app=app, anthropic_key=key)
    assert result.returncode == 0, result.stderr
    assert not any(call[0] == "secret" or call[:2] == ["db", "restart"] for call in calls)


@pytest.mark.parametrize("state", ["PROVISIONING", "FAILED", "STOPPED"])
def test_unready_database_never_deploys(run_cloud_script: Callable[..., RunResult], state: str) -> None:
    result, calls = run_cloud_script(states=[state], anthropic_key="test-anthropic-key")
    assert result.returncode != 0
    assert not any(call[:2] in (["db", "update"], ["db", "restart"]) or call[0] == "secret" for call in calls)
    assert not any(call[0] in {"schema", "service", "http"} for call in calls)
    if state == "PROVISIONING":
        assert "provisioning timed out" in result.stderr
        assert sum(call[:2] == ["db", "status"] for call in calls) == 60
    else:
        assert f"is {state}" in result.stderr


@pytest.mark.parametrize("pending_polls", [1, 59])
def test_provisioning_can_finish_on_last_poll(run_cloud_script: Callable[..., RunResult], pending_polls: int) -> None:
    result, calls = run_cloud_script(states=["PROVISIONING"] * pending_polls + ["AVAILABLE"])
    assert result.returncode == 0, result.stderr
    assert sum(call[:2] == ["db", "status"] for call in calls) == pending_polls + 1


@pytest.mark.parametrize(
    "failure",
    [{"fail_command": ["db", "update"]}, {"insert_status": 503}, {"search_status": 503}, {"api_key": ""}],
)
def test_claim_link_survives_deployment_and_smoke_failures(
    run_cloud_script: Callable[..., RunResult], failure: dict[str, Any]
) -> None:
    result, _ = run_cloud_script(**failure)
    assert result.returncode != 0
    assert CLAIM_URL in result.stdout
    assert result.stdout.index(CLAIM_URL) < result.stdout.index("Uploading")


@pytest.mark.parametrize("rows", [[], [{"text": "An unrelated document."}]])
def test_search_must_return_inserted_document(
    run_cloud_script: Callable[..., RunResult], rows: list[dict[str, str]]
) -> None:
    result, calls = run_cloud_script(search_rows=rows)
    assert result.returncode != 0
    assert "Search did not return the inserted document" in result.stderr
    inserted_body = next(call[3]["body"] for call in calls if call[:2] == ["http", "post"])
    search = next(call for call in calls if call[:2] == ["http", "get"])
    assert search[3]["query_text"] == inserted_body


def test_failed_insert_stops_before_search(run_cloud_script: Callable[..., RunResult]) -> None:
    result, calls = run_cloud_script(insert_status=503)
    assert result.returncode != 0
    assert not any(call[:2] == ["http", "get"] for call in calls)


def test_trial_without_claim_link(run_cloud_script: Callable[..., RunResult]) -> None:
    result, _ = run_cloud_script(claim_url=None)
    assert result.returncode == 0, result.stderr
    assert "Claim this trial" not in result.stdout
