"""Tests for src/clean_data.py::clean."""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Make `src` importable when pytest is run from the repo root or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.clean_data import clean  # noqa: E402

# Pandas emits UserWarning/FutureWarning for some mixed-format date parsing and
# dtype behaviors; they are irrelevant to what these tests verify.
pytestmark = pytest.mark.filterwarnings("ignore::UserWarning", "ignore::FutureWarning")

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------- #
# Helpers & fixtures
# --------------------------------------------------------------------------- #
def make_row(**overrides):
    """A single valid, already-snake_case row; override any field."""
    row = {
        "order_id": "A1",
        "customer_id": "C001",
        "order_date": "2025-01-15",
        "category": "Electronics",
        "product_name": "Widget",

        "region": "North",
        "payment_method": "Credit Card",
        "quantity": 2,
        "unit_price": 10.0,
    }
    row.update(overrides)
    return row


def make_df(overrides_list):
    """Build a DataFrame from a list of override dicts.

    Rows without an explicit order_id get a unique one so they are never
    accidentally treated as exact duplicates.
    """
    rows = []
    for i, overrides in enumerate(overrides_list):
        overrides = dict(overrides)
        overrides.setdefault("order_id", f"ORD-{i}")
        rows.append(make_row(**overrides))
    return pd.DataFrame(rows)


def run_clean(overrides_list):
    result, report = clean(make_df(overrides_list))
    return result.reset_index(drop=True), report


@pytest.fixture
def messy_columns_df():
    """Raw frame whose headers need snake_case standardization."""
    return pd.DataFrame(

        {
            " Order ID ": ["A1", "A2"],
            "Customer-ID": ["C001", "C002"],
            "ORDER DATE": ["2025-01-15", "2025-01-16"],
            "Category": ["Electronics", "Toys"],
            "Product Name": ["Widget", "Robot"],
            "Region": ["North", "South"],
            "payment_method": ["Cash", "Card"],
            "Quantity ": [1, 2],
            "Unit Price ($)": [5.0, 7.5],
        }
    )


@pytest.fixture
def valid_df():
    """Three clean, valid rows."""
    return make_df(
        [
            {"quantity": 1, "unit_price": 10.0},
            {"quantity": 2, "unit_price": 20.0},
            {"quantity": 3, "unit_price": 30.0},
        ]
    )


@pytest.fixture
def kitchen_sink_df():
    """A messy frame exercising every cleaning step at once."""
    dup = make_row(order_id="DUP", unit_price="$1,000.00")
    return pd.DataFrame(
        [

            make_row(order_id="G1", category=" electronics ", order_date="31/01/2025",
                     unit_price="$1,299.99", quantity=2),
            make_row(order_id="G2", category="home and garden", order_date="Jan 5, 2025",
                     unit_price="€45.50", quantity=3, region=np.nan),
            dup,
            dict(dup),  # exact duplicate
            make_row(order_id="BAD_QTY", quantity=0),
            make_row(order_id="BAD_PRICE", unit_price="-5"),
            make_row(order_id="BAD_DATE", order_date="not a date"),
        ]
    )


# --------------------------------------------------------------------------- #
# Return shape
# --------------------------------------------------------------------------- #
def test_clean_returns_dataframe_and_report(valid_df):
    result, report = clean(valid_df)
    assert isinstance(result, pd.DataFrame)
    assert isinstance(report, dict)
    assert report["rows_before"] == 3
    assert report["rows_after"] == len(result) == 3


# --------------------------------------------------------------------------- #
# 1. snake_case column standardization
# --------------------------------------------------------------------------- #
def test_columns_standardized_to_snake_case(messy_columns_df):
    result, _ = clean(messy_columns_df)
    assert list(result.columns) == [
        "order_id",
        "customer_id",

        "order_date",
        "category",
        "product_name",
        "region",
        "payment_method",
        "quantity",
        "unit_price",
        "total_amount",
    ]


def test_all_column_names_are_clean_identifiers(messy_columns_df):
    result, _ = clean(messy_columns_df)
    assert all(re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", c) for c in result.columns)


# --------------------------------------------------------------------------- #
# 2. Exact duplicate removal
# --------------------------------------------------------------------------- #
def test_exact_duplicates_removed():
    dup = make_row(order_id="DUP")
    df = pd.DataFrame([dup, dict(dup), make_row(order_id="OTHER")])
    result, report = clean(df)
    assert report["duplicates_removed"] == 1
    assert sorted(result["order_id"]) == ["DUP", "OTHER"]


def test_multiple_copies_of_same_row_collapse_to_one():
    dup = make_row(order_id="DUP")
    df = pd.DataFrame([dup, dict(dup), dict(dup), dict(dup)])
    result, report = clean(df)
    assert report["duplicates_removed"] == 3

    assert len(result) == 1


def test_rows_differing_in_any_field_are_not_exact_duplicates():
    a = make_row(order_id="X1", quantity=2)
    b = make_row(order_id="X1", quantity=3)  # differs only by quantity
    result, report = clean(pd.DataFrame([a, b]))
    assert report["duplicates_removed"] == 0
    assert len(result) == 2


def test_no_duplicates_reported_when_none_exist(valid_df):
    _, report = clean(valid_df)
    assert report["duplicates_removed"] == 0


# --------------------------------------------------------------------------- #
# 3. Category normalization (casing / whitespace)
# --------------------------------------------------------------------------- #
def test_category_casing_and_whitespace_normalized():
    result, _ = run_clean(
        [
            {"category": " electronics "},
            {"category": "ELECTRONICS"},
            {"category": "Electronics"},
            {"category": "home   and garden"},
            {"category": "  HOME & GARDEN  "},
            {"category": "Home & Garden"},
        ]
    )
    assert sorted(result["category"].unique()) == ["Electronics", "Home & Garden"]



def test_region_and_payment_method_normalized():
    result, _ = run_clean(
        [
            {"region": " north ", "payment_method": "credit card"},
            {"region": "NORTH", "payment_method": "CREDIT CARD "},
            {"region": "North", "payment_method": " Credit Card"},
        ]
    )
    assert result["region"].unique().tolist() == ["North"]
    assert result["payment_method"].unique().tolist() == ["Credit Card"]


def test_categorical_values_have_no_surrounding_whitespace():
    result, _ = run_clean([{"category": "   toys   ", "product_name": "  robot  "}])
    for col in ["category", "product_name"]:
        value = result.loc[0, col]
        assert value == value.strip()


def test_customer_id_whitespace_trimmed():
    result, _ = run_clean([{"customer_id": "  C042  "}])
    assert result.loc[0, "customer_id"] == "C042"


# --------------------------------------------------------------------------- #
# 4. Mixed date-format parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2025-01-15", "2025-01-15"),    # ISO

        ("01/20/2025", "2025-01-20"),    # US month-first
        ("31/01/2025", "2025-01-31"),    # day-first (only valid day-first)
        ("Jan 5, 2025", "2025-01-05"),   # textual month
        ("15 March 2025", "2025-03-15"), # textual month, day first
        ("2025/02/03", "2025-02-03"),    # year-first with slashes
    ],
)
def test_mixed_date_formats_parsed_to_iso(raw, expected):
    result, _ = run_clean([{"order_date": raw}])
    assert result.loc[0, "order_date"] == expected


def test_dates_in_one_column_with_mixed_formats():
    raws = ["2025-01-15", "01/20/2025", "31/01/2025", "Jan 5, 2025"]
    result, _ = run_clean([{"order_date": d} for d in raws])
    assert result["order_date"].tolist() == [
        "2025-01-15",
        "2025-01-20",
        "2025-01-31",
        "2025-01-05",
    ]
    assert all(ISO_DATE.match(d) for d in result["order_date"])


@pytest.mark.parametrize("bad_date", ["not a date", "", np.nan, "99/99/9999"])
def test_unparseable_or_missing_dates_are_dropped(bad_date):
    result, report = run_clean(
        [
            {"order_id": "GOOD"},
            {"order_id": "BAD", "order_date": bad_date},
        ]
    )

    assert result["order_id"].tolist() == ["GOOD"]
    assert report["rows_dropped_unparseable_date"] == 1


# --------------------------------------------------------------------------- #
# 5. Price coercion (currency symbols / separators)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$1,299.99", 1299.99),
        ("€45.50", 45.5),
        ("£ 1,000", 1000.0),
        ("¥2,500.00", 2500.0),
        ("USD 15", 15.0),
        ("12.5", 12.5),
        (20, 20.0),
        (7.25, 7.25),
    ],
)
def test_price_coerced_to_numeric(raw, expected):
    result, _ = run_clean([{"unit_price": raw, "quantity": 1}])
    assert result.loc[0, "unit_price"] == pytest.approx(expected)


def test_price_column_is_float_after_mixed_inputs():
    result, _ = run_clean(
        [
            {"unit_price": "$1,299.99"},
            {"unit_price": "€45.50"},
            {"unit_price": 20},
            {"unit_price": "12.5"},

        ]
    )
    assert pd.api.types.is_float_dtype(result["unit_price"])
    assert result["unit_price"].tolist() == pytest.approx([1299.99, 45.5, 20.0, 12.5])


# --------------------------------------------------------------------------- #
# 7. Dropping non-positive quantity / price
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity": 0},
        {"quantity": -3},
        {"unit_price": 0},
        {"unit_price": "$0.00"},
        {"unit_price": "-5"},
        {"unit_price": -19.99},
    ],
)
def test_non_positive_quantity_or_price_rows_dropped(overrides):
    result, report = run_clean(
        [
            {"order_id": "GOOD"},
            {"order_id": "BAD", **overrides},
        ]
    )
    assert result["order_id"].tolist() == ["GOOD"]
    assert report["rows_dropped_invalid_values"] == 1


def test_all_invalid_rows_counted_together():

    result, report = run_clean(
        [
            {"order_id": "GOOD"},
            {"order_id": "Q0", "quantity": 0},
            {"order_id": "QNEG", "quantity": -2},
            {"order_id": "P0", "unit_price": 0},
            {"order_id": "PNEG", "unit_price": "-5"},
            {"order_id": "PSYM", "unit_price": "$0.00"},
        ]
    )
    assert result["order_id"].tolist() == ["GOOD"]
    assert report["rows_dropped_invalid_values"] == 5


def test_remaining_rows_all_have_positive_quantity_and_price(kitchen_sink_df):
    result, _ = clean(kitchen_sink_df)
    assert (result["quantity"] > 0).all()
    assert (result["unit_price"] > 0).all()


# --------------------------------------------------------------------------- #
# 6. Missing-value filling
# --------------------------------------------------------------------------- #
def test_missing_categoricals_filled_with_unknown():
    result, report = run_clean(
        [
            {"order_id": "FULL"},
            {
                "order_id": "GAPS",
                "customer_id": np.nan,
                "region": np.nan,
                "payment_method": "",

            },
        ]
    )
    gaps = result.set_index("order_id").loc["GAPS"]
    assert gaps["customer_id"] == "Unknown"
    assert gaps["region"] == "Unknown"
    assert gaps["payment_method"] == "Unknown"
    assert report["missing_values_filled"] == {
        "customer_id": 1,
        "region": 1,
        "payment_method": 1,
    }


def test_present_categoricals_are_not_overwritten_with_unknown(valid_df):
    result, report = clean(valid_df)
    assert (result[["customer_id", "region", "payment_method"]] != "Unknown").all().all()
    assert report["missing_values_filled"] == {}


def test_no_missing_values_remain_in_filled_columns():
    result, _ = run_clean(
        [
            {"customer_id": np.nan},
            {"region": np.nan},
            {"payment_method": np.nan},
            {},
        ]
    )
    assert not result[["customer_id", "region", "payment_method"]].isna().any().any()



# NOTE: In clean(), rows whose quantity/unit_price are NaN are removed by the
# positivity filter (NaN > 0 is False) *before* the median fill runs, so the
# numeric fill is currently unreachable. These tests encode the intended
# behavior (median imputation). strict=True means they will flag XPASS once the
# pipeline is fixed -- at that point remove the marker.
@pytest.mark.xfail(
    strict=True,
    reason="NaN prices are dropped by the positivity filter before median fill.",
)
def test_missing_unit_price_filled_with_median():
    result, _ = run_clean(
        [
            {"order_id": "A", "unit_price": 10.0},
            {"order_id": "B", "unit_price": 20.0},
            {"order_id": "C", "unit_price": 30.0},
            {"order_id": "MISSING", "unit_price": np.nan},
        ]
    )
    assert len(result) == 4
    filled = result.set_index("order_id").loc["MISSING"]
    assert filled["unit_price"] == pytest.approx(20.0)


@pytest.mark.xfail(
    strict=True,
    reason="NaN quantities are dropped by the positivity filter before median fill.",
)
def test_missing_quantity_filled_with_rounded_median():
    result, _ = run_clean(
        [
            {"order_id": "A", "quantity": 1},
            {"order_id": "B", "quantity": 3},

            {"order_id": "C", "quantity": 5},
            {"order_id": "MISSING", "quantity": np.nan},
        ]
    )
    assert len(result) == 4
    filled = result.set_index("order_id").loc["MISSING"]
    assert filled["quantity"] == 3


# --------------------------------------------------------------------------- #
# Derived total_amount column
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "quantity, price, expected",
    [
        (3, 19.99, 59.97),
        (2, "$1,299.99", 2599.98),
        (7, 0.1, 0.7),
        (1, 5, 5.0),
        (10, "€45.50", 455.0),
    ],
)
def test_total_amount_is_quantity_times_price(quantity, price, expected):
    result, _ = run_clean([{"quantity": quantity, "unit_price": price}])
    assert result.loc[0, "total_amount"] == pytest.approx(expected)


def test_total_amount_rounded_to_two_decimals():
    result, _ = run_clean(
        [
            {"quantity": 3, "unit_price": 19.99},
            {"quantity": 7, "unit_price": 0.1},

            {"quantity": 3, "unit_price": 1.005},
        ]
    )
    assert (result["total_amount"] == result["total_amount"].round(2)).all()


def test_total_amount_matches_row_level_product(valid_df):
    result, _ = clean(valid_df)
    expected = (result["quantity"] * result["unit_price"]).round(2)
    pd.testing.assert_series_equal(result["total_amount"], expected, check_names=False)


def test_quantity_is_integer_dtype_after_cleaning(valid_df):
    result, _ = clean(valid_df)
    assert pd.api.types.is_integer_dtype(result["quantity"])


# --------------------------------------------------------------------------- #
# End-to-end
# --------------------------------------------------------------------------- #
def test_full_pipeline_on_messy_input(kitchen_sink_df):
    result, report = clean(kitchen_sink_df)
    result = result.set_index("order_id")

    # Survivors: G1, G2, DUP (once). Dropped: dup copy, bad qty/price/date.
    assert sorted(result.index) == ["DUP", "G1", "G2"]

    assert report["rows_before"] == 7
    assert report["duplicates_removed"] == 1
    assert report["rows_dropped_unparseable_date"] == 1
    assert report["rows_dropped_invalid_values"] == 2
    assert report["rows_after"] == 3


    # Normalization / parsing / coercion / derivation on the surviving rows.
    assert result.loc["G1", "category"] == "Electronics"
    assert result.loc["G1", "order_date"] == "2025-01-31"
    assert result.loc["G1", "unit_price"] == pytest.approx(1299.99)
    assert result.loc["G1", "total_amount"] == pytest.approx(2599.98)

    assert result.loc["G2", "category"] == "Home & Garden"
    assert result.loc["G2", "order_date"] == "2025-01-05"
    assert result.loc["G2", "region"] == "Unknown"
    assert result.loc["G2", "total_amount"] == pytest.approx(136.5)

    assert result.loc["DUP", "unit_price"] == pytest.approx(1000.0)


def test_report_row_counts_are_consistent(kitchen_sink_df):
    _, report = clean(kitchen_sink_df)
    accounted = (
        report["rows_after"]
        + report["duplicates_removed"]
        + report["rows_dropped_unparseable_date"]
        + report["rows_dropped_invalid_values"]
    )
    assert accounted == report["rows_before"]


# --------------------------------------------------------------------------- #
# Quality helpers and the --flag-outliers option
# --------------------------------------------------------------------------- #
from src.quality import completeness, flag_outliers_iqr, profile  # noqa: E402


def test_profile_counts_missing_and_unique():
    df = pd.DataFrame({"Order ID": ["a", "b", None], "Qty": [1, 1, 2]})
    p = profile(df)
    assert p.loc["order_id", "missing"] == 1
    assert p.loc["qty", "unique"] == 2
    assert p.loc["order_id", "missing_pct"] == pytest.approx(33.33, abs=0.01)


def test_completeness_percentage():
    df = pd.DataFrame({"a": [1, None], "b": [1, 1]})
    assert completeness(df) == 75.0


def test_iqr_flags_extreme_price_within_its_category():
    df = pd.DataFrame({
        "category": ["A"] * 8 + ["B"] * 8,
        "unit_price": [10, 11, 12, 10, 11, 12, 11, 500, 1000, 1010, 1020, 1000, 1010, 1020, 1005, 1015],
    })
    flags = flag_outliers_iqr(df)
    assert flags.iloc[7]          # 500 is extreme among A's
    assert not flags.iloc[8:].any()  # ~1000 is normal for B


def test_clean_flag_outliers_adds_column_and_keeps_rows():
    rows = [make_row(order_id=f"O{i}", unit_price=10.0 + i % 3) for i in range(12)]
    rows.append(make_row(order_id="BIG", unit_price=9999.0))
    df = pd.DataFrame(rows)
    plain, _ = clean(df.copy())
    flagged, report = clean(df.copy(), flag_outliers=True)
    assert len(flagged) == len(plain)
    assert "is_price_outlier" not in plain.columns
    assert flagged["is_price_outlier"].sum() >= 1
    assert report["price_outliers_flagged"] == int(flagged["is_price_outlier"].sum())
