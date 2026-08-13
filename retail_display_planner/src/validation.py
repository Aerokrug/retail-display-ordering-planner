"""
Sanity checks on the input data before we do any math with it.
Errors stop the run, warnings just get printed.
"""

from dataclasses import dataclass, field

from src.models import DisplayConfig, Variety


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_variety(variety: Variety) -> ValidationResult:
    result = ValidationResult()

    if variety.case_pack <= 0:
        result.errors.append(
            f"{variety.name}: case_pack must be > 0 (got {variety.case_pack})"
        )

    if variety.prior_year_units < 0:
        result.errors.append(
            f"{variety.name}: prior_year_units cannot be negative "
            f"(got {variety.prior_year_units})"
        )

    if variety.min_facings < 0:
        result.errors.append(
            f"{variety.name}: min_facings cannot be negative (got {variety.min_facings})"
        )

    for dim_name, dim_value in (
        ("unit_width_in", variety.unit_width_in),
        ("unit_depth_in", variety.unit_depth_in),
        ("unit_height_in", variety.unit_height_in),
    ):
        if dim_value is not None and dim_value <= 0:
            result.errors.append(
                f"{variety.name}: {dim_name} must be > 0 if provided (got {dim_value})"
            )

    if variety.discount_pct < 0 or variety.discount_pct >= 1:
        result.errors.append(
            f"{variety.name}: discount_pct must be between 0 and 1 "
            f"(got {variety.discount_pct}) -- did you mean a fraction like 0.20 "
            "instead of 20?"
        )
    elif variety.discount_pct > 0.6:
        result.warnings.append(
            f"{variety.name}: discount_pct of {variety.discount_pct:.0%} is "
            "unusually deep -- confirm this is intentional"
        )

    if variety.elasticity_coefficient > 0:
        result.warnings.append(
            f"{variety.name}: elasticity_coefficient is positive "
            f"({variety.elasticity_coefficient}) -- this is unusual. A positive "
            "value means a discount would REDUCE forecasted demand. Standard "
            "price elasticity is negative."
        )

    if (
        variety.unit_width_in is None
        and variety.unit_depth_in is None
        and variety.unit_height_in is None
    ):
        result.warnings.append(
            f"{variety.name}: no unit dimensions on file -- layout math will "
            "fall back to a default placeholder size, which may be "
            "significantly wrong"
        )

    return result


def validate_varieties(varieties: list[Variety]) -> ValidationResult:
    result = ValidationResult()

    seen_names = set()
    for variety in varieties:
        if variety.name in seen_names:
            result.errors.append(f"Duplicate variety name in this display: {variety.name!r}")
        seen_names.add(variety.name)
        result.merge(validate_variety(variety))

    if not varieties:
        result.errors.append(
            "No varieties loaded for this display -- check display_id matches "
            "a row in sales_history.csv"
        )

    return result


def validate_display_config(config: DisplayConfig) -> ValidationResult:
    result = ValidationResult()

    valid_fixture_types = {"shelf", "crate", "side_stack"}
    if config.fixture_type not in valid_fixture_types:
        result.errors.append(
            f"fixture_type must be one of {sorted(valid_fixture_types)} "
            f"(got {config.fixture_type!r})"
        )

    if config.duration_days_this_year <= 0:
        result.errors.append(
            f"duration_days_this_year must be > 0 (got {config.duration_days_this_year})"
        )

    if config.duration_days_prior_year <= 0:
        result.errors.append(
            f"duration_days_prior_year must be > 0 (got {config.duration_days_prior_year})"
        )

    if config.growth_target_pct < -0.9 or config.growth_target_pct > 3.0:
        result.warnings.append(
            f"growth_target_pct of {config.growth_target_pct:.0%} is unusually "
            "extreme -- did you mean a fraction like 0.10 instead of 10?"
        )

    if config.tie_in and (config.tie_in_bonus_pct < 0 or config.tie_in_bonus_pct > 2.0):
        result.warnings.append(
            f"tie_in_bonus_pct of {config.tie_in_bonus_pct:.0%} is unusually "
            "extreme -- verify this is intentional"
        )

    if config.fixture_type == "shelf" and not config.shelves:
        result.warnings.append(
            "No shelves configured -- the entire order will be treated as "
            "backroom overflow"
        )
    elif config.fixture_type == "crate" and not config.crates:
        result.warnings.append(
            "No crates configured -- the entire order will be treated as "
            "backroom overflow"
        )
    elif config.fixture_type == "side_stack" and not config.side_stacks:
        result.warnings.append(
            "No side stacks configured -- the entire order will be treated "
            "as backroom overflow"
        )

    return result


def validate_all(varieties: list[Variety], config: DisplayConfig) -> ValidationResult:
    """Runs every check and merges results into one report."""
    result = ValidationResult()
    result.merge(validate_varieties(varieties))
    result.merge(validate_display_config(config))
    return result


def print_validation_report(result: ValidationResult) -> None:
    if result.errors:
        print("VALIDATION ERRORS (must fix before continuing):")
        for e in result.errors:
            print(f"  x {e}")
    if result.warnings:
        print("Validation warnings (continuing anyway):")
        for w in result.warnings:
            print(f"  ! {w}")
    if result.errors or result.warnings:
        print()
