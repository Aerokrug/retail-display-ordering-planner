"""
Main entry point. Loads everything, validates it, runs the forecast,
lays out the display, spits out a mockup image.

    python -m src.main
    python -m src.main --display-id pudding_endcap_2025
    python -m src.main --list
"""

import argparse
import datetime
import os
import sys

from src.allocation import allocate_by_variety, summarize
from src.crate_layout import assign_crate_layout, summarize_crate_layout
from src.db import DEFAULT_DB_PATH, import_results_csv, init_db, summarize_results_by_variety
from src.db import load_display_config as load_display_config_db
from src.db import load_varieties as load_varieties_db
from src.db import sync_display_config_from_csv, sync_varieties_from_csv
from src.io_utils import list_display_ids
from src.layout import assign_layout, summarize_layout
from src.learning import compute_all_bias_corrections, fit_elasticity, log_result
from src.mockup import draw_mockup
from src.models import Crate, DisplayConfig, ResultRecord, Shelf, SideStack
from src.optimizer import optimize_facing_counts
from src.stack_layout import assign_stack_layout, summarize_stack_layout
from src.validation import print_validation_report, validate_all


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Retail display planner")
    parser.add_argument(
        "--display-id", default="pudding_endcap_2025",
        help="Which display to plan (must match a display_id in both CSVs). "
             "Default: pudding_endcap_2025",
    )
    parser.add_argument(
        "--sales-csv", default="data/sales_history.csv",
        help="Path to the variety input CSV (default: data/sales_history.csv)",
    )
    parser.add_argument(
        "--displays-csv", default="data/displays.csv",
        help="Path to the display-level config CSV (default: data/displays.csv)",
    )
    parser.add_argument(
        "--db-path", default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--output-image", default=None,
        help="Where to write the mockup image (default: data/<display_id>_mockup.png)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available display_id values from both CSVs and exit",
    )
    return parser.parse_args(argv)


def _setup_fixtures(config: DisplayConfig) -> None:
    """Fixture dimensions are hardcoded here for now - edit these to
    match your actual shelves/crates/stacks."""
    if config.fixture_type == "shelf":
        config.shelves = [Shelf(width_in=36, depth_in=18) for _ in range(4)]
    elif config.fixture_type == "crate":
        config.crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(3)]
    elif config.fixture_type == "side_stack":
        config.side_stacks = [
            SideStack(base_width_in=40, base_depth_in=40, max_height_in=60) for _ in range(2)
        ]


def _run_layout(config: DisplayConfig, orders):
    """Only shelf displays use the LP optimizer, crate/stack use the
    simpler greedy allocation."""
    if config.fixture_type == "shelf":
        try:
            lp_targets = optimize_facing_counts(config.shelves, orders)
            assign_layout(config.shelves, orders, target_facings=lp_targets)
            print("(facing counts chosen by LP optimizer)")
        except Exception as e:
            # PuLP/CBC might not be installed - fall back instead of crashing
            print(f"(LP optimizer unavailable ({e}), using the proportional fallback)")
            assign_layout(config.shelves, orders)
        return summarize_layout(orders)
    elif config.fixture_type == "crate":
        assign_crate_layout(config.crates, orders)
        return summarize_crate_layout(orders)
    elif config.fixture_type == "side_stack":
        assign_stack_layout(config.side_stacks, orders)
        return summarize_stack_layout(orders)
    else:
        raise ValueError(f"Unknown fixture_type: {config.fixture_type!r}")


def main(
    display_id: str = "pudding_endcap_2025",
    sales_csv: str = "data/sales_history.csv",
    displays_csv: str = "data/displays.csv",
    db_path: str = DEFAULT_DB_PATH,
    output_image: str = None,
):
    init_db(db_path)

    # migrate the old CSV results log if it's still sitting around
    legacy_csv = "data/results_log.csv"
    if os.path.isfile(legacy_csv):
        imported = import_results_csv(legacy_csv, db_path)
        print(f"Imported {imported} rows from legacy {legacy_csv} into {db_path}\n")

    sync_varieties_from_csv(sales_csv, display_id, db_path)
    varieties = load_varieties_db(display_id, db_path)

    try:
        sync_display_config_from_csv(displays_csv, display_id, db_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"Could not load display config: {e}")
        print(f"Run with --list to see available display_id values.")
        sys.exit(1)
    config = load_display_config_db(display_id, db_path)
    if config is None:
        print(f"No display config found for display_id={display_id!r}. "
              f"Add a row to {displays_csv} first.")
        sys.exit(1)
    _setup_fixtures(config)
    # print(config)  # was debugging a fixture_type mixup, leaving this here for now

    validation = validate_all(varieties, config)
    print_validation_report(validation)
    if not validation.is_valid:
        print(f"Fix the errors above in {sales_csv} / {displays_csv} and re-run.")
        sys.exit(1)

    if config.context_notes:
        print(f"Context: {config.context_notes}\n")

    # pull in whatever we've learned from past runs, if anything
    bias_corrections = compute_all_bias_corrections(db_path)
    for v in varieties:
        fitted = fit_elasticity(v.name, db_path=db_path)
        if fitted is not None:
            print(f"Using fitted elasticity for {v.name}: {fitted:.2f} (was {v.elasticity_coefficient:.2f})")
            v.elasticity_coefficient = fitted

    orders = allocate_by_variety(config, varieties, bias_corrections)

    print(summarize(orders))
    print()
    if bias_corrections:
        print("Bias corrections applied (learned from past runs):")
        for name, mult in bias_corrections.items():
            print(f"  {name}: {mult:.2f}x")
    else:
        print("No bias corrections yet - log a few real results to start learning.")

    print()
    layout_summary = _run_layout(config, orders)
    print(layout_summary)

    if output_image is None:
        output_image = f"data/{display_id}_mockup.png"
    output_path = draw_mockup(
        config, orders,
        title=f"{display_id} - {config.fixture_type.replace('_', ' ').title()} Display",
        output_path=output_image,
    )
    print(f"\nMockup image written to: {output_path}")

    history = summarize_results_by_variety(db_path)
    if history:
        print("\nAll-time forecast accuracy by variety (from SQLite):")
        for row in history:
            ratio = row["avg_actual_to_forecast_ratio"]
            ratio_str = f"{ratio:.2f}x" if ratio is not None else "n/a"
            print(
                f"  {row['variety_name']}: {row['runs_logged']} runs logged, "
                f"avg actual/forecast {ratio_str} "
                f"({row['first_run']} to {row['most_recent_run']})"
            )

    # once the display actually runs, log results like this:
    #
    # for order in orders:
    #     log_result(ResultRecord(
    #         display_id=display_id,
    #         variety_name=order.variety.name,
    #         run_date=datetime.date.today().isoformat(),
    #         forecast_units=order.forecast_units,
    #         actual_units=<real number from POS>,
    #         discount_pct=order.variety.discount_pct,
    #         elasticity_coefficient=order.variety.elasticity_coefficient,
    #         growth_target_pct=config.growth_target_pct,
    #         tie_in=config.tie_in,
    #     ), db_path=db_path)

    return orders


def cli():
    args = parse_args()

    if args.list:
        ids = list_display_ids(args.sales_csv, args.displays_csv)
        if ids:
            print("Available display_id values:")
            for display_id in ids:
                print(f"  {display_id}")
        else:
            print(f"No display_id values found in {args.sales_csv} or {args.displays_csv}.")
        return

    main(
        display_id=args.display_id,
        sales_csv=args.sales_csv,
        displays_csv=args.displays_csv,
        db_path=args.db_path,
        output_image=args.output_image,
    )


if __name__ == "__main__":
    cli()
