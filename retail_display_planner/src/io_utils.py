"""CSV loading - one file for varieties, one for display settings,
both keyed by display_id. Gets synced into SQLite by db.py."""

import csv

from src.models import DisplayConfig, Variety


def load_varieties(csv_path: str, display_id: str) -> list[Variety]:
    """Columns: display_id, name, upc, prior_year_units, case_pack,
    unit_width_in, unit_depth_in, unit_height_in, min_facings,
    stockout_last_year, discount_pct, elasticity_coefficient,
    case_width_in, case_depth_in, case_height_in.

    Last five are optional. case dims only matter for side_stack
    displays, leave blank otherwise."""
    varieties = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["display_id"] != display_id:
                continue
            varieties.append(
                Variety(
                    name=row["name"],
                    upc=row.get("upc") or None,
                    prior_year_units=float(row["prior_year_units"]),
                    case_pack=int(row["case_pack"]),
                    unit_width_in=_to_float(row.get("unit_width_in")),
                    unit_depth_in=_to_float(row.get("unit_depth_in")),
                    unit_height_in=_to_float(row.get("unit_height_in")),
                    min_facings=int(row.get("min_facings") or 1),
                    stockout_last_year=_to_bool(row.get("stockout_last_year")),
                    discount_pct=_to_float(row.get("discount_pct")) or 0.0,
                    elasticity_coefficient=(
                        _to_float(row.get("elasticity_coefficient"))
                        if row.get("elasticity_coefficient")
                        else -1.5
                    ),
                    case_width_in=_to_float(row.get("case_width_in")),
                    case_depth_in=_to_float(row.get("case_depth_in")),
                    case_height_in=_to_float(row.get("case_height_in")),
                )
            )
    return varieties


def load_display_config(csv_path: str, display_id: str) -> DisplayConfig:
    """Columns: display_id, duration_days_this_year, duration_days_prior_year,
    growth_target_pct, tie_in, tie_in_bonus_pct, context_notes, fixture_type.

    Only duration_days_this_year is required. fixture_type defaults to
    "shelf" if left out. Raises if display_id isn't found - better to
    fail loudly than silently plan off default assumptions.

    Fixture dimensions (shelves/crates/stacks) aren't in this CSV, those
    stay hardcoded in main.py for now."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["display_id"] != display_id:
                continue
            return DisplayConfig(
                fixture_type=row.get("fixture_type") or "shelf",
                duration_days_this_year=int(row["duration_days_this_year"]),
                duration_days_prior_year=int(
                    row.get("duration_days_prior_year")
                    or row["duration_days_this_year"]
                ),
                growth_target_pct=_to_float(row.get("growth_target_pct")) or 0.0,
                tie_in=_to_bool(row.get("tie_in")),
                tie_in_bonus_pct=_to_float(row.get("tie_in_bonus_pct")) or 0.0,
                context_notes=row.get("context_notes") or "",
            )

    raise ValueError(
        f"No display config found for display_id={display_id!r} in {csv_path}. "
        "Add a row for it (see data/displays.csv for the expected format)."
    )


def list_display_ids(*csv_paths: str) -> list[str]:
    """Every display_id found across the given CSVs, sorted, no dupes.
    Used by --list so you don't have to grep for the exact string."""
    ids: set[str] = set()
    for path in csv_paths:
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("display_id"):
                        ids.add(row["display_id"])
        except FileNotFoundError:
            continue
    return sorted(ids)


def _to_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _to_bool(value):
    if value is None:
        return False
    return value.strip().lower() in ("1", "true", "yes", "y")
