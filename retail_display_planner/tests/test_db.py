import csv
import os

import pytest

from src.db import (
    import_results_csv,
    init_db,
    load_display_config,
    load_results,
    load_varieties,
    log_result,
    summarize_results_by_variety,
    sync_display_config_from_csv,
    sync_varieties_from_csv,
    upsert_display_config,
    upsert_variety,
)
from src.models import DisplayConfig, ResultRecord, Variety


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


def test_init_db_creates_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert os.path.isfile(db_path)


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # should not raise or duplicate schema


# --- varieties ----------------------------------------------------------

def test_upsert_and_load_variety_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    variety = Variety(
        name="Chocolate", prior_year_units=480, case_pack=12,
        unit_width_in=2.5, unit_depth_in=2.5, unit_height_in=3.0,
        min_facings=1, stockout_last_year=True, discount_pct=0.1,
        elasticity_coefficient=-1.8,
    )
    upsert_variety("display_a", variety, db_path)

    loaded = load_varieties("display_a", db_path)
    assert len(loaded) == 1
    assert loaded[0].name == "Chocolate"
    assert loaded[0].prior_year_units == 480
    assert loaded[0].stockout_last_year is True
    assert loaded[0].elasticity_coefficient == -1.8


def test_upsert_variety_updates_existing_row_instead_of_duplicating(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    v1 = Variety(name="Chocolate", prior_year_units=100, case_pack=12)
    v2 = Variety(name="Chocolate", prior_year_units=999, case_pack=12)  # updated value
    upsert_variety("display_a", v1, db_path)
    upsert_variety("display_a", v2, db_path)

    loaded = load_varieties("display_a", db_path)
    assert len(loaded) == 1
    assert loaded[0].prior_year_units == 999


def test_load_varieties_filters_by_display_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_variety("display_a", Variety(name="X", case_pack=12), db_path)
    upsert_variety("display_b", Variety(name="Y", case_pack=12), db_path)

    assert [v.name for v in load_varieties("display_a", db_path)] == ["X"]
    assert [v.name for v in load_varieties("display_b", db_path)] == ["Y"]


def test_sync_varieties_from_csv_imports_all_rows(tmp_path):
    csv_path = tmp_path / "sales_history.csv"
    csv_path.write_text(
        "display_id,name,upc,prior_year_units,case_pack,unit_width_in,"
        "unit_depth_in,unit_height_in,min_facings,stockout_last_year,"
        "discount_pct,elasticity_coefficient\n"
        "test_disp,Chocolate,123,480,12,2.5,2.5,3.0,1,true,0.0,-1.5\n"
        "test_disp,Vanilla,124,360,12,2.5,2.5,3.0,1,false,0.0,-1.5\n"
    )
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    count = sync_varieties_from_csv(str(csv_path), "test_disp", db_path)
    assert count == 2
    loaded = load_varieties("test_disp", db_path)
    assert {v.name for v in loaded} == {"Chocolate", "Vanilla"}


def test_sync_varieties_from_csv_is_safe_to_rerun(tmp_path):
    csv_path = tmp_path / "sales_history.csv"
    csv_path.write_text(
        "display_id,name,upc,prior_year_units,case_pack,unit_width_in,"
        "unit_depth_in,unit_height_in,min_facings,stockout_last_year,"
        "discount_pct,elasticity_coefficient\n"
        "test_disp,Chocolate,123,480,12,2.5,2.5,3.0,1,false,0.0,-1.5\n"
    )
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sync_varieties_from_csv(str(csv_path), "test_disp", db_path)
    sync_varieties_from_csv(str(csv_path), "test_disp", db_path)  # rerun
    loaded = load_varieties("test_disp", db_path)
    assert len(loaded) == 1  # no duplicate


# --- results --------------------------------------------------------------

def test_log_result_and_load_results_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    log_result(make_record(), db_path)
    rows = load_results(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["variety_name"] == "Chocolate"


def test_load_results_empty_when_nothing_logged(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert load_results(db_path=db_path) == []


def test_load_results_filters_by_variety_name(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    log_result(make_record(variety_name="Chocolate"), db_path)
    log_result(make_record(variety_name="Vanilla"), db_path)
    rows = load_results(variety_name="Vanilla", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["variety_name"] == "Vanilla"


def test_log_result_same_key_updates_instead_of_duplicating(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    log_result(make_record(actual_units=100), db_path)
    log_result(make_record(actual_units=150), db_path)  # same display/variety/date
    rows = load_results(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["actual_units"] == 150


def test_import_results_csv_returns_zero_for_missing_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    count = import_results_csv(str(tmp_path / "does_not_exist.csv"), db_path)
    assert count == 0


def test_import_results_csv_migrates_legacy_format(tmp_path):
    csv_path = tmp_path / "results_log.csv"
    csv_path.write_text(
        "display_id,variety_name,run_date,forecast_units,actual_units,"
        "discount_pct,elasticity_coefficient,growth_target_pct,tie_in,notes\n"
        "disp1,Chocolate,2023-11-01,400,450,0.0,-1.5,0.05,False,\n"
        "disp2,Vanilla,2023-11-01,300,280,0.1,-1.5,0.0,False,\n"
    )
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    count = import_results_csv(str(csv_path), db_path)
    assert count == 2
    rows = load_results(db_path=db_path)
    assert len(rows) == 2


def test_import_results_csv_is_idempotent(tmp_path):
    csv_path = tmp_path / "results_log.csv"
    csv_path.write_text(
        "display_id,variety_name,run_date,forecast_units,actual_units,"
        "discount_pct,elasticity_coefficient,growth_target_pct,tie_in,notes\n"
        "disp1,Chocolate,2023-11-01,400,450,0.0,-1.5,0.05,False,\n"
    )
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    import_results_csv(str(csv_path), db_path)
    import_results_csv(str(csv_path), db_path)  # re-import
    assert len(load_results(db_path=db_path)) == 1  # no duplicate


def test_summarize_results_by_variety_aggregates_correctly(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    log_result(make_record(variety_name="Chocolate", run_date="2023-01-01",
                            forecast_units=100, actual_units=120), db_path)
    log_result(make_record(variety_name="Chocolate", run_date="2024-01-01",
                            forecast_units=100, actual_units=140), db_path)
    log_result(make_record(variety_name="Vanilla", run_date="2024-06-01",
                            forecast_units=50, actual_units=50), db_path)

    summary = {row["variety_name"]: row for row in summarize_results_by_variety(db_path)}
    assert summary["Chocolate"]["runs_logged"] == 2
    assert summary["Chocolate"]["avg_actual_to_forecast_ratio"] == pytest.approx(1.3)
    assert summary["Chocolate"]["first_run"] == "2023-01-01"
    assert summary["Chocolate"]["most_recent_run"] == "2024-01-01"
    assert summary["Vanilla"]["runs_logged"] == 1


# --- display config -------------------------------------------------------

def test_upsert_and_load_display_config_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    config = DisplayConfig(
        duration_days_this_year=10, duration_days_prior_year=14,
        growth_target_pct=0.15, tie_in=True, tie_in_bonus_pct=0.05,
        context_notes="Holiday weekend, extra foot traffic expected",
    )
    upsert_display_config("disp1", config, db_path)

    loaded = load_display_config("disp1", db_path)
    assert loaded is not None
    assert loaded.duration_days_this_year == 10
    assert loaded.duration_days_prior_year == 14
    assert loaded.growth_target_pct == pytest.approx(0.15)
    assert loaded.tie_in is True
    assert loaded.context_notes == "Holiday weekend, extra foot traffic expected"


def test_load_display_config_returns_none_when_not_synced(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert load_display_config("never_synced", db_path) is None


def test_upsert_display_config_updates_not_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_display_config(
        "disp1", DisplayConfig(duration_days_this_year=7, duration_days_prior_year=7), db_path
    )
    upsert_display_config(
        "disp1", DisplayConfig(duration_days_this_year=21, duration_days_prior_year=7), db_path
    )
    loaded = load_display_config("disp1", db_path)
    assert loaded.duration_days_this_year == 21


def test_sync_display_config_from_csv(tmp_path):
    csv_path = tmp_path / "displays.csv"
    csv_path.write_text(
        "display_id,duration_days_this_year,duration_days_prior_year,"
        "growth_target_pct,tie_in,tie_in_bonus_pct,context_notes\n"
        'disp1,14,14,0.10,true,0.05,"Back to school"\n'
    )
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    sync_display_config_from_csv(str(csv_path), "disp1", db_path)
    loaded = load_display_config("disp1", db_path)
    assert loaded.duration_days_this_year == 14
    assert loaded.context_notes == "Back to school"


def test_upsert_display_config_persists_fixture_type(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    config = DisplayConfig(
        fixture_type="side_stack", duration_days_this_year=10, duration_days_prior_year=10,
    )
    upsert_display_config("disp1", config, db_path)
    loaded = load_display_config("disp1", db_path)
    assert loaded.fixture_type == "side_stack"


def test_upsert_variety_persists_case_dimensions(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    variety = Variety(
        name="Cola", case_pack=24,
        case_width_in=16, case_depth_in=12, case_height_in=10,
    )
    upsert_variety("disp1", variety, db_path)
    loaded = load_varieties("disp1", db_path)
    assert loaded[0].case_width_in == 16
    assert loaded[0].case_depth_in == 12
    assert loaded[0].case_height_in == 10


# --- schema migration (backward compatibility) ------------------------

def test_init_db_adds_missing_columns_to_existing_tables(tmp_path):
    # Regression test: a database created before case_width_in/
    # case_depth_in/case_height_in/fixture_type existed should get
    # those columns added automatically, not crash on the next read.
    import sqlite3

    db_path = str(tmp_path / "old_schema.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE varieties (
            display_id TEXT NOT NULL, name TEXT NOT NULL, upc TEXT,
            prior_year_units REAL NOT NULL DEFAULT 0, case_pack INTEGER NOT NULL DEFAULT 1,
            unit_width_in REAL, unit_depth_in REAL, unit_height_in REAL,
            min_facings INTEGER NOT NULL DEFAULT 1, stockout_last_year INTEGER NOT NULL DEFAULT 0,
            discount_pct REAL NOT NULL DEFAULT 0, elasticity_coefficient REAL NOT NULL DEFAULT -1.5,
            PRIMARY KEY (display_id, name)
        )
    """)
    conn.execute("""
        CREATE TABLE displays (
            display_id TEXT PRIMARY KEY, duration_days_this_year INTEGER NOT NULL,
            duration_days_prior_year INTEGER NOT NULL, growth_target_pct REAL NOT NULL DEFAULT 0,
            tie_in INTEGER NOT NULL DEFAULT 0, tie_in_bonus_pct REAL NOT NULL DEFAULT 0,
            context_notes TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "INSERT INTO varieties (display_id, name, prior_year_units, case_pack) "
        "VALUES ('old_disp', 'OldVariety', 100, 12)"
    )
    conn.execute(
        "INSERT INTO displays (display_id, duration_days_this_year, duration_days_prior_year) "
        "VALUES ('old_disp', 14, 14)"
    )
    conn.commit()
    conn.close()

    # This must not raise -- init_db (called internally by load_varieties/
    # load_display_config) should add the missing columns.
    varieties = load_varieties("old_disp", db_path)
    assert varieties[0].name == "OldVariety"
    assert varieties[0].case_width_in is None  # new column, defaults to NULL

    config = load_display_config("old_disp", db_path)
    assert config.fixture_type == "shelf"  # new column, defaults per its DDL


def test_init_db_column_migration_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # running twice on an already-migrated DB shouldn't error
    assert os.path.isfile(db_path)
