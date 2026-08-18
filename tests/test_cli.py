from __future__ import annotations

from typer.testing import CliRunner

from rigmanifest.cli import app


runner = CliRunner()


def test_compile_home_for_vx6r_writes_csv_and_reports_safety_error(tmp_path) -> None:
    output = tmp_path / "home.csv"

    result = runner.invoke(
        app,
        ["compile", "home", "--target", "yaesu-vx6r", "--output", str(output)],
    )

    assert result.exit_code == 1
    assert output.exists()
    assert "Included: 3" in result.stdout
    assert "Omitted: 1" in result.stdout
    assert "TX_DISABLE_NOT_REPRESENTABLE" in result.stdout
    assert output.read_text(encoding="utf-8").startswith("Location,Name,Frequency")


def test_unknown_target_is_a_usage_error() -> None:
    result = runner.invoke(app, ["compile", "home", "--target", "unknown"])

    assert result.exit_code == 2
    assert "unknown target" in result.output
