import pytest

from src.io_utils import load_display_config


def write_displays_csv(path, rows):
    header = (
        "display_id,duration_days_this_year,duration_days_prior_year,"
        "growth_target_pct,tie_in,tie_in_bonus_pct,context_notes\n"
    )
    path.write_text(header + "\n".join(rows) + "\n")


def test_load_display_config_reads_all_fields(tmp_path):
    csv_path = tmp_path / "displays.csv"
    write_displays_csv(csv_path, [
        'disp1,14,14,0.10,true,0.05,"Back to school promo"'
    ])
    config = load_display_config(str(csv_path), "disp1")
    assert config.duration_days_this_year == 14
    assert config.duration_days_prior_year == 14
    assert config.growth_target_pct == pytest.approx(0.10)
    assert config.tie_in is True
    assert config.tie_in_bonus_pct == pytest.approx(0.05)
    assert config.context_notes == "Back to school promo"


def test_load_display_config_raises_for_missing_display_id(tmp_path):
    csv_path = tmp_path / "displays.csv"
    write_displays_csv(csv_path, ['disp1,14,14,0.10,true,0.05,'])
    with pytest.raises(ValueError):
        load_display_config(str(csv_path), "does_not_exist")


def test_load_display_config_defaults_prior_year_duration_to_this_year(tmp_path):
    # If duration_days_prior_year is omitted, assume the comparable
    # display ran the same length last year rather than forcing the
    # person to fill in a value they may not know.
    csv_path = tmp_path / "displays.csv"
    header = (
        "display_id,duration_days_this_year,growth_target_pct,tie_in,"
        "tie_in_bonus_pct,context_notes\n"
    )
    csv_path.write_text(header + "disp1,10,0.0,false,0.0,\n")
    config = load_display_config(str(csv_path), "disp1")
    assert config.duration_days_prior_year == 10


def test_load_display_config_defaults_optional_fields(tmp_path):
    csv_path = tmp_path / "displays.csv"
    header = "display_id,duration_days_this_year\n"
    csv_path.write_text(header + "disp1,7\n")
    config = load_display_config(str(csv_path), "disp1")
    assert config.duration_days_this_year == 7
    assert config.growth_target_pct == 0.0
    assert config.tie_in is False
    assert config.tie_in_bonus_pct == 0.0
    assert config.context_notes == ""


def test_load_display_config_shelves_empty_by_default(tmp_path):
    csv_path = tmp_path / "displays.csv"
    write_displays_csv(csv_path, ['disp1,14,14,0.0,false,0.0,'])
    config = load_display_config(str(csv_path), "disp1")
    assert config.shelves == []


def test_display_duration_from_csv_actually_changes_forecast(tmp_path):
    # The point of this input: two displays differing ONLY in how long
    # they'll be up should get proportionally different forecasts, and
    # that duration has to come from the CSV, not a hard-coded value.
    from src.forecasting import forecast_total_units

    csv_path = tmp_path / "displays.csv"
    write_displays_csv(csv_path, [
        "short_run,7,14,0.0,false,0.0,",
        "long_run,28,14,0.0,false,0.0,",
    ])

    short_config = load_display_config(str(csv_path), "short_run")
    long_config = load_display_config(str(csv_path), "long_run")

    prior_year_units = 400
    short_forecast = forecast_total_units(prior_year_units, short_config)
    long_forecast = forecast_total_units(prior_year_units, long_config)

    # 7 days vs 28 days -> long_run should forecast 4x short_run
    assert long_forecast == pytest.approx(short_forecast * 4)


def test_load_display_config_defaults_fixture_type_to_shelf_when_column_missing():
    # Backward compatibility: displays.csv files from before crate/
    # side_stack support existed have no fixture_type column at all.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        csv_path = f"{d}/displays.csv"
        with open(csv_path, "w") as f:
            f.write(
                "display_id,duration_days_this_year,duration_days_prior_year,"
                "growth_target_pct,tie_in,tie_in_bonus_pct,context_notes\n"
                "disp1,14,14,0.0,false,0.0,\n"
            )
        config = load_display_config(csv_path, "disp1")
        assert config.fixture_type == "shelf"


def test_load_display_config_reads_explicit_fixture_type(tmp_path):
    csv_path = tmp_path / "displays.csv"
    header = (
        "display_id,fixture_type,duration_days_this_year,duration_days_prior_year,"
        "growth_target_pct,tie_in,tie_in_bonus_pct,context_notes\n"
    )
    csv_path.write_text(header + "disp1,crate,10,10,0.0,false,0.0,\n")
    config = load_display_config(str(csv_path), "disp1")
    assert config.fixture_type == "crate"


def test_load_varieties_reads_case_dimensions(tmp_path):
    from src.io_utils import load_varieties

    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "display_id,name,upc,prior_year_units,case_pack,unit_width_in,"
        "unit_depth_in,unit_height_in,min_facings,stockout_last_year,"
        "discount_pct,elasticity_coefficient,case_width_in,case_depth_in,case_height_in\n"
        "disp1,Cola,,3000,24,2.5,2.5,4.8,1,false,0.0,-1.5,16,12,10\n"
    )
    varieties = load_varieties(str(csv_path), "disp1")
    assert varieties[0].case_width_in == 16
    assert varieties[0].case_depth_in == 12
    assert varieties[0].case_height_in == 10


def test_load_varieties_case_dimensions_default_to_none_when_omitted(tmp_path):
    from src.io_utils import load_varieties

    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "display_id,name,upc,prior_year_units,case_pack\n"
        "disp1,Chocolate,,100,12\n"
    )
    varieties = load_varieties(str(csv_path), "disp1")
    assert varieties[0].case_width_in is None
    assert varieties[0].case_depth_in is None
    assert varieties[0].case_height_in is None
