import pytest

from src.models import DisplayConfig, Shelf, Variety
from src.validation import (
    validate_all,
    validate_display_config,
    validate_variety,
    validate_varieties,
)


def make_variety(**overrides):
    defaults = dict(
        name="Chocolate", prior_year_units=100, case_pack=12,
        unit_width_in=2.5, unit_depth_in=2.5, unit_height_in=3.0,
    )
    defaults.update(overrides)
    return Variety(**defaults)


def make_config(**overrides):
    defaults = dict(
        shelves=[Shelf(width_in=36, depth_in=18)],
        duration_days_this_year=14,
        duration_days_prior_year=14,
    )
    defaults.update(overrides)
    return DisplayConfig(**defaults)


# --- variety-level errors --------------------------------------------------

def test_valid_variety_has_no_errors():
    result = validate_variety(make_variety())
    assert result.is_valid
    assert result.errors == []


def test_zero_case_pack_is_an_error():
    result = validate_variety(make_variety(case_pack=0))
    assert not result.is_valid
    assert any("case_pack" in e for e in result.errors)


def test_negative_case_pack_is_an_error():
    result = validate_variety(make_variety(case_pack=-5))
    assert not result.is_valid


def test_negative_prior_year_units_is_an_error():
    result = validate_variety(make_variety(prior_year_units=-10))
    assert not result.is_valid
    assert any("prior_year_units" in e for e in result.errors)


def test_negative_min_facings_is_an_error():
    result = validate_variety(make_variety(min_facings=-1))
    assert not result.is_valid


def test_negative_dimension_is_an_error():
    result = validate_variety(make_variety(unit_width_in=-2.0))
    assert not result.is_valid
    assert any("unit_width_in" in e for e in result.errors)


def test_zero_dimension_is_an_error():
    result = validate_variety(make_variety(unit_depth_in=0))
    assert not result.is_valid


def test_discount_pct_over_one_is_an_error():
    # Classic typo: entering 20 meaning 20% instead of 0.20
    result = validate_variety(make_variety(discount_pct=20))
    assert not result.is_valid
    assert any("discount_pct" in e for e in result.errors)


def test_negative_discount_pct_is_an_error():
    result = validate_variety(make_variety(discount_pct=-0.1))
    assert not result.is_valid


def test_discount_pct_of_exactly_one_is_an_error():
    # A 100% discount (free product) is at the boundary and treated as invalid
    result = validate_variety(make_variety(discount_pct=1.0))
    assert not result.is_valid


# --- variety-level warnings -------------------------------------------------

def test_deep_but_valid_discount_is_a_warning_not_error():
    result = validate_variety(make_variety(discount_pct=0.70))
    assert result.is_valid  # doesn't block execution
    assert any("discount_pct" in w for w in result.warnings)


def test_moderate_discount_has_no_warning():
    result = validate_variety(make_variety(discount_pct=0.20))
    assert result.warnings == []


def test_positive_elasticity_coefficient_is_a_warning():
    result = validate_variety(make_variety(elasticity_coefficient=1.5))
    assert result.is_valid
    assert any("elasticity_coefficient" in w for w in result.warnings)


def test_negative_elasticity_coefficient_has_no_warning():
    result = validate_variety(make_variety(elasticity_coefficient=-1.5))
    assert result.warnings == []


def test_missing_all_dimensions_is_a_warning():
    result = validate_variety(make_variety(
        unit_width_in=None, unit_depth_in=None, unit_height_in=None
    ))
    assert result.is_valid
    assert any("dimensions" in w for w in result.warnings)


def test_partial_dimensions_does_not_warn():
    result = validate_variety(make_variety(unit_width_in=2.5, unit_depth_in=None))
    assert not any("dimensions" in w for w in result.warnings)


# --- list-level: duplicates and empty ---------------------------------------

def test_duplicate_variety_names_is_an_error():
    varieties = [make_variety(name="Chocolate"), make_variety(name="Chocolate")]
    result = validate_varieties(varieties)
    assert not result.is_valid
    assert any("Duplicate" in e for e in result.errors)


def test_no_varieties_at_all_is_an_error():
    result = validate_varieties([])
    assert not result.is_valid


def test_distinct_variety_names_no_duplicate_error():
    varieties = [make_variety(name="Chocolate"), make_variety(name="Vanilla")]
    result = validate_varieties(varieties)
    assert not any("Duplicate" in e for e in result.errors)


# --- display config ----------------------------------------------------------

def test_valid_display_config_has_no_errors():
    result = validate_display_config(make_config())
    assert result.is_valid


def test_zero_duration_this_year_is_an_error():
    result = validate_display_config(make_config(duration_days_this_year=0))
    assert not result.is_valid


def test_negative_duration_prior_year_is_an_error():
    result = validate_display_config(make_config(duration_days_prior_year=-5))
    assert not result.is_valid


def test_extreme_growth_target_is_a_warning():
    # 1000% growth -- almost certainly a typo of 10% (0.10 vs 10)
    result = validate_display_config(make_config(growth_target_pct=10.0))
    assert result.is_valid
    assert any("growth_target_pct" in w for w in result.warnings)


def test_normal_growth_target_has_no_warning():
    result = validate_display_config(make_config(growth_target_pct=0.10))
    assert result.warnings == []


def test_extreme_tie_in_bonus_is_a_warning_only_when_tie_in_true():
    config_with = make_config(tie_in=True, tie_in_bonus_pct=5.0)
    config_without = make_config(tie_in=False, tie_in_bonus_pct=5.0)
    assert any("tie_in_bonus_pct" in w for w in validate_display_config(config_with).warnings)
    assert not any("tie_in_bonus_pct" in w for w in validate_display_config(config_without).warnings)


def test_no_shelves_is_a_warning():
    result = validate_display_config(make_config(shelves=[]))
    assert result.is_valid
    assert any("shelves" in w for w in result.warnings)


def test_unknown_fixture_type_is_an_error():
    result = validate_display_config(make_config(fixture_type="not_a_real_type"))
    assert not result.is_valid
    assert any("fixture_type" in e for e in result.errors)


def test_valid_fixture_types_do_not_error():
    for fixture_type in ("shelf", "crate", "side_stack"):
        result = validate_display_config(make_config(fixture_type=fixture_type))
        assert not any("fixture_type" in e for e in result.errors)


def test_no_crates_is_a_warning_for_crate_fixture_type():
    from src.models import Crate
    config = make_config(fixture_type="crate", shelves=[], crates=[])
    result = validate_display_config(config)
    assert result.is_valid
    assert any("crates" in w for w in result.warnings)


def test_no_side_stacks_is_a_warning_for_side_stack_fixture_type():
    config = make_config(fixture_type="side_stack", shelves=[], side_stacks=[])
    result = validate_display_config(config)
    assert result.is_valid
    assert any("side stacks" in w for w in result.warnings)


def test_crate_fixture_with_crates_configured_has_no_fixture_warning():
    from src.models import Crate
    config = make_config(
        fixture_type="crate", shelves=[],
        crates=[Crate(width_in=24, depth_in=18, fill_height_in=8)],
    )
    result = validate_display_config(config)
    assert not any("crates" in w for w in result.warnings)


# --- combined ------------------------------------------------------------

def test_validate_all_merges_variety_and_config_issues():
    varieties = [make_variety(case_pack=0)]
    config = make_config(duration_days_this_year=0)
    result = validate_all(varieties, config)
    assert not result.is_valid
    assert len(result.errors) == 2  # one from variety, one from config
