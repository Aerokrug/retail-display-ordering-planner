import pytest

from src.learning import (
    compute_all_bias_corrections,
    compute_bias_correction,
    fit_elasticity,
    load_results,
    log_result,
)
from src.models import ResultRecord


def make_record(**overrides):
    defaults = dict(
        display_id="test_display",
        variety_name="Chocolate",
        run_date="2025-01-01",
        forecast_units=100.0,
        actual_units=100.0,
        discount_pct=0.0,
        elasticity_coefficient=-1.5,
        growth_target_pct=0.0,
        tie_in=False,
        notes="",
    )
    defaults.update(overrides)
    return ResultRecord(**defaults)


def test_log_result_creates_db_and_is_queryable(tmp_path):
    db_path = tmp_path / "results.db"
    log_result(make_record(), db_path=str(db_path))
    assert db_path.exists()
    rows = load_results(db_path=str(db_path))
    assert len(rows) == 1
    assert rows[0]["variety_name"] == "Chocolate"


def test_load_results_empty_when_no_file(tmp_path):
    db_path = tmp_path / "does_not_exist.db"
    assert load_results(db_path=str(db_path)) == []


def test_bias_correction_defaults_to_one_with_insufficient_history(tmp_path):
    db_path = tmp_path / "results.db"
    log_result(make_record(forecast_units=100, actual_units=150), db_path=str(db_path))
    # Only 1 record logged; min_history default is 2
    result = compute_bias_correction("Chocolate", db_path=str(db_path))
    assert result == 1.0


def test_bias_correction_averages_ratios_once_enough_history(tmp_path):
    db_path = tmp_path / "results.db"
    # distinct run_date per call - these represent two separate past
    # runs, not the same event logged twice (which would correctly
    # collapse to one row under the UNIQUE display/variety/date key)
    log_result(
        make_record(run_date="2023-01-01", forecast_units=100, actual_units=120),
        db_path=str(db_path),
    )
    log_result(
        make_record(run_date="2024-01-01", forecast_units=100, actual_units=140),
        db_path=str(db_path),
    )
    result = compute_bias_correction("Chocolate", db_path=str(db_path))
    # ratios: 1.2, 1.4 -> average 1.3
    assert result == pytest.approx(1.3)


def test_bias_correction_only_considers_matching_variety(tmp_path):
    db_path = tmp_path / "results.db"
    log_result(
        make_record(variety_name="Chocolate", run_date="2023-01-01",
                    forecast_units=100, actual_units=200),
        db_path=str(db_path),
    )
    log_result(
        make_record(variety_name="Chocolate", run_date="2024-01-01",
                    forecast_units=100, actual_units=200),
        db_path=str(db_path),
    )
    log_result(
        make_record(variety_name="Vanilla", run_date="2023-01-01",
                    forecast_units=100, actual_units=50),
        db_path=str(db_path),
    )
    result = compute_bias_correction("Vanilla", db_path=str(db_path))
    # Only 1 Vanilla record -> below min_history -> defaults to 1.0
    assert result == 1.0


def test_compute_all_bias_corrections_covers_every_logged_variety(tmp_path):
    db_path = tmp_path / "results.db"
    for year in ("2023", "2024"):
        log_result(
            make_record(variety_name="Chocolate", run_date=f"{year}-01-01",
                        forecast_units=100, actual_units=110),
            db_path=str(db_path),
        )
        log_result(
            make_record(variety_name="Vanilla", run_date=f"{year}-01-01",
                        forecast_units=100, actual_units=90),
            db_path=str(db_path),
        )
    corrections = compute_all_bias_corrections(db_path=str(db_path))
    assert set(corrections.keys()) == {"Chocolate", "Vanilla"}
    assert corrections["Chocolate"] == pytest.approx(1.1)
    assert corrections["Vanilla"] == pytest.approx(0.9)


def test_logging_same_display_variety_date_twice_updates_not_duplicates(tmp_path):
    # Real-world safety net: if you accidentally log the same display's
    # result twice, it should update in place, not silently double-count
    # it in future averages.
    db_path = tmp_path / "results.db"
    log_result(make_record(actual_units=100), db_path=str(db_path))
    log_result(make_record(actual_units=999), db_path=str(db_path))  # same key, "corrected" value
    rows = load_results(db_path=str(db_path))
    assert len(rows) == 1
    assert rows[0]["actual_units"] == 999


def test_fit_elasticity_returns_none_without_discount_variation(tmp_path):
    db_path = tmp_path / "results.db"
    # Same discount every time (but distinct dates - these are 3 real,
    # separate logged runs) -> no slope to fit since there's no
    # variation in the input variable
    for i, year in enumerate(("2022", "2023", "2024")):
        log_result(
            make_record(run_date=f"{year}-01-01", discount_pct=0.10, actual_units=100),
            db_path=str(db_path),
        )
    result = fit_elasticity("Chocolate", db_path=str(db_path))
    assert result is None


def test_fit_elasticity_returns_none_below_min_points(tmp_path):
    db_path = tmp_path / "results.db"
    log_result(make_record(discount_pct=0.0, actual_units=100), db_path=str(db_path))
    log_result(make_record(discount_pct=0.20, actual_units=140), db_path=str(db_path))
    # Only 2 points; default min_points is 3
    result = fit_elasticity("Chocolate", db_path=str(db_path))
    assert result is None


def test_fit_elasticity_recovers_known_slope(tmp_path):
    db_path = tmp_path / "results.db"
    # Construct data from a known elasticity so we can check the fit recovers it.
    # units = base * (1 - discount) ** elasticity, with elasticity = -2.0
    base = 100
    true_elasticity = -2.0
    for i, discount in enumerate((0.0, 0.10, 0.20, 0.30)):
        units = base * (1 - discount) ** true_elasticity
        log_result(
            make_record(run_date=f"202{i}-01-01", discount_pct=discount, actual_units=units),
            db_path=str(db_path),
        )
    result = fit_elasticity("Chocolate", db_path=str(db_path))
    assert result == pytest.approx(true_elasticity, abs=0.01)
