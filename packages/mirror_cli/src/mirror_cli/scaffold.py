"""Project scaffolding helpers for the Mirror CLI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from mirror_cli.templates import _APP_FILES, _PROJECT_FILES

_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _text(*lines: str) -> str:
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class DoctorCheck:
    """Single health-check result for a generated Mirror project."""

    name: str
    passed: bool
    details: str


def _validate_name(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} cannot be empty")
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"{label} must start with a letter or underscore and contain only "
            "letters, digits, underscores, or hyphens"
        )


def _render(template: str, **replacements: str) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _write_file(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)


def create_project(name: str, *, root: Path | None = None) -> Path:
    """Create a Mirror project scaffold.

    Args:
        name: Project directory name.
        root: Optional parent directory. Defaults to the current directory.

    Returns:
        The path to the created project directory.
    """
    _validate_name(name, "Project name")
    base = Path.cwd() if root is None else root
    project_root = base / name
    if project_root.exists():
        raise FileExistsError(f"Project already exists: {project_root}")

    for relative_path, template in _PROJECT_FILES.items():
        content = _render(template, PROJECT_NAME=name)
        executable = relative_path == "manage.py"
        _write_file(project_root / relative_path, content, executable=executable)

    return project_root


def create_app(name: str, *, root: Path | None = None) -> Path:
    """Create a Mirror application scaffold inside an existing project.

    Args:
        name: Application directory name.
        root: Optional project root. Defaults to the current directory.

    Returns:
        The path to the created application package.
    """
    _validate_name(name, "App name")
    base = Path.cwd() if root is None else root
    apps_root = base / "apps"
    if not apps_root.exists():
        raise FileNotFoundError(
            f"Unable to find apps/ under {base}. Run `mirror startproject` first."
        )
    app_root = apps_root / name
    if app_root.exists():
        raise FileExistsError(f"Application already exists: {app_root}")

    for relative_path, template in _APP_FILES.items():
        content = _render(template, APP_NAME=name)
        _write_file(app_root / relative_path, content)

    return app_root


def collect_project_checks(root: Path | None = None) -> list[DoctorCheck]:
    """Inspect the current directory for a generated Mirror project."""
    base = Path.cwd() if root is None else root
    checks: list[DoctorCheck] = []

    def _exists(label: str, path: Path) -> None:
        checks.append(
            DoctorCheck(
                name=label,
                passed=path.exists(),
                details=str(path),
            )
        )

    _exists("project root", base / "manage.py")
    _exists("project settings", base / "config" / "settings.py")
    _exists("project ASGI entrypoint", base / "config" / "asgi.py")
    _exists("project WSGI entrypoint", base / "config" / "wsgi.py")
    _exists("default app", base / "apps" / "core")
    _exists("project README", base / "README.md")
    _exists("project docs", base / "docs" / "README.md")

    for module_name in ("mirror_core", "mirror_cli"):
        try:
            __import__(module_name)
        except ImportError as exc:  # specific, not blind
            checks.append(
                DoctorCheck(
                    name=f"import {module_name}",
                    passed=False,
                    details=str(exc),
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name=f"import {module_name}",
                    passed=True,
                    details="imported successfully",
                )
            )

    return checks


def format_checks(checks: list[DoctorCheck]) -> str:
    """Render doctor checks as a plain-text summary."""
    lines = ["Mirror Doctor", ""]
    for check in checks:
        status = "OK" if check.passed else "FAIL"
        lines.append(f"[{status}] {check.name}: {check.details}")
    return "\n".join(lines)


def project_is_healthy(checks: list[DoctorCheck]) -> bool:
    """Return ``True`` when all doctor checks pass."""
    return all(check.passed for check in checks)
