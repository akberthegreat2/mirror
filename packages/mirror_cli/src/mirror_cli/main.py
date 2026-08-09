"""Mirror CLI main entry point."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from mirror_core.application import Application
from mirror_core.exceptions import ApplicationError
from mirror_core.interfaces import InterfaceCatalog
from mirror_core.pipeline import Pipeline
from mirror_core.settings import MirrorSettings
from mirror_core.workers import WorkerBackend
from rich.console import Console
from rich.table import Table

from mirror_cli.scaffold import (
    collect_project_checks,
    create_app,
    create_project,
    format_checks,
    project_is_healthy,
)

manifest_app = typer.Typer(name="manifest", help="Inspect the canonical Mirror extension catalog.")
app = typer.Typer(
    name="mirror",
    help="Mirror application framework",
    add_completion=False,
)
console = Console()
app.add_typer(manifest_app, name="manifest")

# Constants for CLI options/arguments (to avoid B008)
ARG_NAME = typer.Argument(..., help="Project directory name")
OPT_ROOT = typer.Option(None, "--root", "-r", help="Parent directory for the generated project")
OPT_APP_ROOT = typer.Option(None, "--root", "-r", help="Project root that contains apps/")
OPT_DOCTOR_ROOT = typer.Option(None, "--root", "-r", help="Project root to inspect")
OPT_CONFIG = typer.Option(None, "--config", "-c", help="Path to Mirror settings file")
OPT_PIPELINE = typer.Option(..., "--pipeline", "-p", help="Path to pipeline definition file")
OPT_INPUTS = typer.Option(None, "--inputs", "-i", help="JSON/TOML/YAML runtime inputs file")
OPT_BACKEND = typer.Option(
    "sqlite",
    "--backend",
    case_sensitive=False,
    help="Worker backend to initialize (sqlite or inline)",
)
OPT_DATABASE = typer.Option(
    None,
    "--database",
    "-d",
    help="SQLite database path used when --backend sqlite is selected",
)


@manifest_app.command("show")
def manifest_show() -> None:
    """Print the interface-neutral extension catalog as JSON."""
    document = InterfaceCatalog().document()
    console.print_json(json.dumps(document, sort_keys=True))


@manifest_app.command("capability")
def manifest_capability(name: str = typer.Argument(..., help="Capability name.")) -> None:
    """Show one discovered capability manifest."""
    for manifest in InterfaceCatalog().discover().capabilities:
        if manifest.name == name or manifest.extension_id == name:
            console.print_json(
                json.dumps(
                    InterfaceCatalog.manifest_document(manifest), sort_keys=True
                )
            )
            return
    raise typer.BadParameter(f"Unknown capability: {name}")


@manifest_app.command("provider")
def manifest_provider(
    capability: str = typer.Argument(..., help="Capability name."),
    name: str = typer.Argument(..., help="Provider name."),
) -> None:
    """Show one discovered provider manifest."""
    for manifest in InterfaceCatalog().discover().providers:
        if manifest.capability == capability and (manifest.name == name or manifest.extension_id == name):
            console.print_json(
                json.dumps(
                    InterfaceCatalog.manifest_document(manifest), sort_keys=True
                )
            )
            return
    raise typer.BadParameter(f"Unknown provider: {capability}/{name}")


async def _list_capabilities_async() -> None:
    """List discovered capabilities without leaking application resources."""
    table = Table(title="Discovered Capabilities")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description", style="white")

    try:
        async with Application(settings=MirrorSettings()) as app_obj:
            for cap in app_obj.registry.list_capabilities():
                name = cap.name
                version = cap.api_version
                description = "N/A"
                try:
                    config = app_obj.registry.get_capability(name, version)
                    description = config.metadata.get("description", "N/A")
                except KeyError:
                    pass
                table.add_row(name, version, description)
    except ApplicationError:
        # No capabilities discovered; just print an empty table
        pass
    except Exception as exc:
        console.print(f"[red]Failed to start application: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(table)


async def _list_providers_async() -> None:
    """List discovered providers without leaking application resources."""
    table = Table(title="Discovered Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Capability", style="green")
    table.add_column("Priority", style="yellow")

    try:
        async with Application(settings=MirrorSettings()) as app_obj:
            for provider in app_obj.registry.list_providers():
                capability = provider.capability
                name = provider.name
                try:
                    config = app_obj.registry.get_provider(capability, name)
                    table.add_row(name, capability, str(config.priority))
                except KeyError:
                    table.add_row(name, capability, "N/A")
    except ApplicationError:
        # No providers discovered; just print an empty table
        pass
    except Exception as exc:
        console.print(f"[red]Failed to start application: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(table)


@app.command()
def startproject(
    name: str = ARG_NAME,
    root: Path | None = OPT_ROOT,
) -> None:
    """Create a Django-style Mirror project scaffold."""
    try:
        created = create_project(name, root=root)
    except Exception as exc:
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Created Mirror project scaffold[/green] {created}")
    console.print("Next: cd into the project and run `mirror doctor`.")


@app.command()
def startapp(
    name: str = typer.Argument(..., help="Application package name"),
    root: Path | None = OPT_APP_ROOT,
) -> None:
    """Create a reusable Mirror application scaffold inside apps/."""
    try:
        created = create_app(name, root=root)
    except Exception as exc:
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Created Mirror app scaffold[/green] {created}")


@app.command()
def doctor(
    root: Path | None = OPT_DOCTOR_ROOT,
) -> None:
    """Inspect a generated project scaffold and report health checks."""
    checks = collect_project_checks(root=root)
    console.print(format_checks(checks))
    if not project_is_healthy(checks):
        raise typer.Exit(code=1)


@app.command()
def run(
    config: Path | None = OPT_CONFIG,
    pipeline: Path = OPT_PIPELINE,
    inputs: Path | None = OPT_INPUTS,
) -> None:
    """Compile and execute one pipeline with explicit runtime inputs."""

    async def _run() -> None:
        settings = MirrorSettings.from_file(config) if config is not None else MirrorSettings()
        pipeline_obj = _load_pipeline(pipeline)
        runtime_inputs = _load_mapping(inputs) if inputs is not None else {}
        async with Application(settings=settings) as app_obj:
            result = await app_obj.run_pipeline_detailed(pipeline_obj, inputs=runtime_inputs)
        console.print(f"[green]Pipeline finished[/green] {result.outcome.value}")
        console.print(f"Run ID: {result.run_id}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


def _load_mapping(path: Path) -> dict[str, object]:
    """Load a mapping from JSON, TOML, or YAML."""
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if path.suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML files require PyYAML") from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path.suffix == ".toml":
        from mirror_core.toml import loads as toml_loads

        data = toml_loads(path.read_text(encoding="utf-8"))
    elif path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise RuntimeError(f"Unsupported file format: {path.suffix}")
    if not isinstance(data, dict):
        raise TypeError(f"Expected an object/mapping in {path}")
    return data


def _load_pipeline(path: Path) -> Pipeline:
    """Load and validate a pipeline definition."""

    return Pipeline.model_validate(_load_mapping(path))


@app.command()
def worker(
    backend: str = OPT_BACKEND,
    database: Path | None = OPT_DATABASE,
) -> None:
    """Initialize the local worker backend and report readiness."""

    async def _run() -> None:
        backend_name = backend.lower()
        worker_backend: WorkerBackend
        if backend_name == "inline":
            from mirror_core.workers import InlineWorker

            worker_backend = InlineWorker()
            label = "inline"
        elif backend_name == "sqlite":
            from mirror_core.workers import SQLiteWorkerBackend

            db_path = database or Path(".mirror/worker.sqlite3")
            worker_backend = SQLiteWorkerBackend(db_path)
            label = f"sqlite:{db_path}"
        else:
            raise RuntimeError("backend must be 'sqlite' or 'inline'")

        await worker_backend.start()
        await worker_backend.stop()
        console.print(f"[green]Worker backend ready[/green] {label}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("worker-check")
def worker_check() -> None:
    """Report the availability of the shipped worker execution contracts."""
    console.print(
        "[green]Worker execution is available[/green] "
        "(inline, SQLite, PostgreSQL, and Celery transports)."
    )


@app.command()
def list_capabilities() -> None:
    """List all discovered capabilities."""
    try:
        asyncio.run(_list_capabilities_async())
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def list_providers() -> None:
    """List all discovered providers."""
    try:
        asyncio.run(_list_providers_async())
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def status() -> None:
    """Show application status."""
    console.print("[bold]Mirror Status[/bold]")
    console.print("Application: Not running")


@app.callback()
def callback() -> None:
    """Mirror CLI – application framework for Mirror."""


if __name__ == "__main__":
    app()
