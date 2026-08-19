"""Thin command-line adapter over the RigManifest compiler."""

from __future__ import annotations

from pathlib import Path

import typer

from rigmanifest.capabilities import BUILTIN_TARGETS
from rigmanifest.compiler import compile_profile
from rigmanifest.exporters.chirp_csv import write_chirp_csv
from rigmanifest.fixtures import BUILTIN_CATALOG, BUILTIN_PROFILES
from rigmanifest.models import Severity


app = typer.Typer(
    help="Compile operator intent into capability-aware radio plans.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """RigManifest command group."""


@app.command("compile")
def compile_command(
    profile: str = typer.Argument(help="Built-in profile ID (currently: home)."),
    target: str = typer.Option(..., "--target", help="Target radio model ID."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output CSV path."),
) -> None:
    """Compile a built-in profile and export a CHIRP-compatible CSV."""

    selected_profile = BUILTIN_PROFILES.get(profile.casefold())
    if selected_profile is None:
        choices = ", ".join(sorted(BUILTIN_PROFILES))
        raise typer.BadParameter(f"unknown profile {profile!r}; choose from: {choices}")

    selected_target = BUILTIN_TARGETS.get(target.casefold())
    if selected_target is None:
        choices = ", ".join(sorted(BUILTIN_TARGETS))
        raise typer.BadParameter(f"unknown target {target!r}; choose from: {choices}")

    plan = compile_profile(BUILTIN_CATALOG, selected_profile, selected_target)
    output_path = output or Path(f"{selected_profile.id}-{selected_target.id}.csv")
    write_chirp_csv(plan, output_path)

    typer.echo(f"Profile: {selected_profile.name}")
    typer.echo(f"Target: {selected_target.model}")
    typer.echo("")
    typer.echo(f"Programmed: {len(plan.memories)}")
    typer.echo(f"Factory-provided: {plan.factory_definition_count}")
    typer.echo(f"Factory sets: {len(plan.factory_sets)}")
    typer.echo(f"Omitted: {len(plan.omitted_frequency_definitions)}")
    typer.echo(f"Warnings: {plan.warning_count}")
    typer.echo(f"Errors: {plan.error_count}")
    typer.echo("")
    for diagnostic in plan.diagnostics:
        subject_id = diagnostic.frequency_definition_id or diagnostic.frequency_set_id
        subject = f" [{subject_id}]" if subject_id else ""
        typer.echo(
            f"{diagnostic.severity.value.upper()} {diagnostic.code.value}{subject}: "
            f"{diagnostic.message}"
        )
    typer.echo("")
    typer.echo(f"CSV written: {output_path}")

    if any(item.severity is Severity.ERROR for item in plan.diagnostics):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
