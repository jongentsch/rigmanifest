from __future__ import annotations

from typer.testing import CliRunner

from rigmanifest.cli import app


runner = CliRunner()


def test_compile_home_for_vx6r_uses_factory_weather_set(tmp_path) -> None:
    output = tmp_path / "home.csv"

    result = runner.invoke(
        app,
        ["compile", "home", "--target", "yaesu-vx6r", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert "Programmed: 3" in result.stdout
    assert "Factory-provided: 10" in result.stdout
    assert "Factory sets: 1" in result.stdout
    assert "Omitted: 0" in result.stdout
    assert "FACTORY_SET_AVAILABLE" in result.stdout
    assert output.read_text(encoding="utf-8").startswith("Location,Name,Frequency")


def test_unknown_target_is_a_usage_error() -> None:
    result = runner.invoke(app, ["compile", "home", "--target", "unknown"])

    assert result.exit_code == 2
    assert "unknown target" in result.output
