import pytest

from src.io_utils import list_display_ids
from src.main import parse_args


# --- argument parsing --------------------------------------------------

def test_parse_args_defaults():
    args = parse_args([])
    assert args.display_id == "pudding_endcap_2025"
    assert args.sales_csv == "data/sales_history.csv"
    assert args.displays_csv == "data/displays.csv"
    assert args.list is False


def test_parse_args_display_id_override():
    args = parse_args(["--display-id", "some_other_display"])
    assert args.display_id == "some_other_display"


def test_parse_args_list_flag():
    args = parse_args(["--list"])
    assert args.list is True


def test_parse_args_custom_paths():
    args = parse_args([
        "--sales-csv", "/tmp/custom_sales.csv",
        "--displays-csv", "/tmp/custom_displays.csv",
        "--db-path", "/tmp/custom.db",
        "--output-image", "/tmp/custom.png",
    ])
    assert args.sales_csv == "/tmp/custom_sales.csv"
    assert args.displays_csv == "/tmp/custom_displays.csv"
    assert args.db_path == "/tmp/custom.db"
    assert args.output_image == "/tmp/custom.png"


# --- list_display_ids ----------------------------------------------------

def test_list_display_ids_from_single_csv(tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "display_id,name\n"
        "display_b,X\n"
        "display_a,Y\n"
        "display_b,Z\n"
    )
    ids = list_display_ids(str(csv_path))
    assert ids == ["display_a", "display_b"]  # sorted, deduplicated


def test_list_display_ids_merges_multiple_csvs(tmp_path):
    csv1 = tmp_path / "sales.csv"
    csv1.write_text("display_id,name\ndisplay_a,X\n")
    csv2 = tmp_path / "displays.csv"
    csv2.write_text("display_id,duration_days_this_year\ndisplay_b,14\n")

    ids = list_display_ids(str(csv1), str(csv2))
    assert ids == ["display_a", "display_b"]


def test_list_display_ids_ignores_missing_files(tmp_path):
    csv1 = tmp_path / "sales.csv"
    csv1.write_text("display_id,name\ndisplay_a,X\n")
    missing = tmp_path / "does_not_exist.csv"

    ids = list_display_ids(str(csv1), str(missing))
    assert ids == ["display_a"]


def test_list_display_ids_empty_when_no_files_exist(tmp_path):
    ids = list_display_ids(str(tmp_path / "nope1.csv"), str(tmp_path / "nope2.csv"))
    assert ids == []
