import pytest

from src.forecasting import adjust_for_stockout, forecast_total_units
from src.models import DisplayConfig, Shelf, Variety


def make_config(**overrides):
    defaults = dict(
        shelves=[Shelf(width_in=36, depth_in=18)],
        duration_days_this_year=14,
        duration_days_prior_year=14,
        growth_target_pct=0.0,
        tie_in=False,
        tie_in_bonus_pct=0.0,
    )
    defaults.update(overrides)
    return DisplayConfig(**defaults)


def test_flat_forecast_with_no_adjustments():
    # Same duration, 0% growth, no tie-in, no discount -> forecast == prior year units
    config = make_config()
    result = forecast_total_units(500, config)
    assert result == pytest.approx(500)


def test_growth_target_increases_forecast():
    config = make_config(growth_target_pct=0.10)
    result = forecast_total_units(500, config)
    assert result == pytest.approx(550)


def test_shorter_display_scales_down():
    # Half the days this year vs last year -> half the units, before growth
    config = make_config(duration_days_this_year=7, duration_days_prior_year=14)
    result = forecast_total_units(500, config)
    assert result == pytest.approx(250)


def test_longer_display_scales_up():
    config = make_config(duration_days_this_year=28, duration_days_prior_year=14)
    result = forecast_total_units(500, config)
    assert result == pytest.approx(1000)


def test_tie_in_bonus_only_applies_when_tie_in_true():
    config_with = make_config(tie_in=True, tie_in_bonus_pct=0.20)
    config_without = make_config(tie_in=False, tie_in_bonus_pct=0.20)
    assert forecast_total_units(500, config_with) == pytest.approx(600)
    assert forecast_total_units(500, config_without) == pytest.approx(500)


def test_discount_with_negative_elasticity_increases_forecast():
    # Standard demand curve: negative elasticity + a discount -> lift
    config = make_config()
    result = forecast_total_units(
        500, config, discount_pct=0.20, elasticity_coefficient=-1.5
    )
    # lift = -(-1.5) * 0.20 = 0.30 -> +30%
    assert result == pytest.approx(650)


def test_zero_discount_has_no_lift_regardless_of_elasticity():
    config = make_config()
    result = forecast_total_units(
        500, config, discount_pct=0.0, elasticity_coefficient=-3.0
    )
    assert result == pytest.approx(500)


def test_bias_correction_scales_final_forecast():
    config = make_config()
    result = forecast_total_units(500, config, bias_correction=1.2)
    assert result == pytest.approx(600)


def test_zero_duration_prior_year_raises():
    config = make_config(duration_days_prior_year=0)
    with pytest.raises(ValueError):
        forecast_total_units(500, config)


def test_stockout_correction_bumps_units_up():
    v = Variety(name="Chocolate", prior_year_units=100, stockout_last_year=True)
    result = adjust_for_stockout(v, assumed_lost_sales_pct=0.15)
    assert result == pytest.approx(115)


def test_no_stockout_correction_when_flag_is_false():
    v = Variety(name="Vanilla", prior_year_units=100, stockout_last_year=False)
    result = adjust_for_stockout(v)
    assert result == pytest.approx(100)
