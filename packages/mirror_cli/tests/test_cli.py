"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from mirror_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_list_capabilities() -> None:
    """The capability listing command should complete successfully."""
    result = runner.invoke(app, ["list-capabilities"])
    assert result.exit_code == 0


def test_list_providers() -> None:
    """The provider listing command should complete successfully."""
    result = runner.invoke(app, ["list-providers"])
    assert result.exit_code == 0


def test_status() -> None:
    """The status command should complete successfully."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_run_requires_pipeline() -> None:
    """The run command requires an explicit pipeline file."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 2


def test_startproject_creates_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The project scaffold command should create the expected layout."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["startproject", "demo"])
    assert result.exit_code == 0
    project_root = tmp_path / "demo"
    assert (project_root / "manage.py").exists()
    assert (project_root / "config" / "settings.py").exists()
    assert (project_root / "config" / "asgi.py").exists()
    assert (project_root / "config" / "wsgi.py").exists()
    assert (project_root / "apps" / "core" / "pipelines.py").exists()
    assert (project_root / "apps" / "core" / "workers.py").exists()
    assert (project_root / "README.md").exists()
    assert (project_root / "docs" / "README.md").exists()


def test_startapp_creates_app_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The app scaffold command should create a reusable app package."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["startproject", "demo"]).exit_code == 0
    monkeypatch.chdir(tmp_path / "demo")
    result = runner.invoke(app, ["startapp", "monitor"])
    assert result.exit_code == 0
    app_root = tmp_path / "demo" / "apps" / "monitor"
    assert (app_root / "config.py").exists()
    assert (app_root / "pipelines.py").exists()
    assert (app_root / "tasks.py").exists()
    assert (app_root / "middleware.py").exists()
    assert (app_root / "signals.py").exists()
    assert (app_root / "workers.py").exists()
    assert (app_root / "README.md").exists()


def test_doctor_reports_healthy_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The doctor command should report success for a generated project."""
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["startproject", "demo"]).exit_code == 0
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path / "demo")])
    assert result.exit_code == 0
    assert "Mirror Doctor" in result.output
    assert "[OK]" in result.output


def test_generated_manage_py_can_run_doctor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The generated manage.py should execute the doctor command."""
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    extra_site = "/opt/pyvenv/lib/python3.13/site-packages"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            *(str(src) for src in sorted((root / "packages").glob("*/src"))),
            str(root),
            extra_site,
        ]
    )
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["startproject", "demo"]).exit_code == 0
    project_root = tmp_path / "demo"
    result = subprocess.run(
        [sys.executable, "manage.py", "doctor"],
        cwd=project_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Mirror Doctor" in result.stdout
    assert "[OK]" in result.stdout


def test_worker_command_initializes_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker command should initialize a local backend."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["worker", "--backend", "sqlite"])
    assert result.exit_code == 0
    assert "Worker backend ready" in result.output


def test_worker_check_command() -> None:
    """Worker check must probe real transports and report honestly."""
    result = runner.invoke(app, ["worker-check"])
    assert result.exit_code == 0
    assert "reachable" in result.output
    assert "inline" in result.output
    assert "Worker execution transports" in result.output


def test_manifest_show_command() -> None:
    """The shared interface catalog is exposed through the CLI."""
    result = runner.invoke(app, ["manifest", "show"])
    assert result.exit_code == 0
    assert "capabilities" in result.output
