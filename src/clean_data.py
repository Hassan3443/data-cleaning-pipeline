"""Clean a messy sales CSV into an analysis-ready dataset.

Steps:
  1. Standardize column names to snake_case
  2. Drop exact duplicate rows
  3. Trim whitespace and normalize categorical casing
  4. Parse mixed date formats into ISO dates
  5. Coerce numeric fields (strips currency symbols / thousand separators)
  6. Fill missing values (median for numerics, 'Unknown' for categoricals)
  7. Drop invalid rows (non-positive quantity or price)

Writes the cleaned CSV and a markdown cleaning report with before/after stats.

Usage:
    python src/clean_data.py
    python src/clean_data.py --flag-outliers --plot figures/before_after.png
    python src/clean_data.py --input data/raw/messy_sales.csv \
        --output data/cleaned/clean_sales.csv --report reports/cleaning_report.md
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

try:  # imported as a package (tests) or run as a script
    from src.quality import completeness, flag_outliers_iqr, plot_before_after
except ImportError:
    from quality import completeness, flag_outliers_iqr, plot_before_after


def standardize_columns(df):
    df.columns = [
        re.sub(r"[^a-z0-9]+", "_", c.strip().lower()).strip("_") for c in df.columns
    ]
    return df


def normalize_categories(df, columns):
    for col in columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.replace(r"\s+and\s+", " & ", regex=True)
            .str.title()
            .replace({"": pd.NA, "Nan": pd.NA})
        )
    return df


def parse_dates(series):
    parsed = pd.to_datetime(series, format="mixed", dayfirst=False, errors="coerce")
    # Retry failures with dayfirst=True for formats like 31/01/2025
    mask = parsed.isna() & series.notna() & (series.astype(str).str.strip() != "")
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(
            series[mask], format="mixed", dayfirst=True, errors="coerce"
        )
    return parsed


def coerce_price(series):
    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d.\-]", "", regex=True)
        .replace({"": pd.NA, "-": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def clean(df, flag_outliers=False):
    report = {"rows_before": len(df)}

    df = standardize_columns(df)

    # 2. Exact duplicates
    dupes = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()
    report["duplicates_removed"] = dupes

    # 3. Text hygiene
    df = normalize_categories(df, ["category", "region", "payment_method", "product_name"])
    df["customer_id"] = df["customer_id"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA})

    # 4. Dates
    df["order_date"] = parse_dates(df["order_date"])
    bad_dates = int(df["order_date"].isna().sum())
    df = df.dropna(subset=["order_date"])
    report["rows_dropped_unparseable_date"] = bad_dates

    # 5. Numerics
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = coerce_price(df["unit_price"])

    # 7. Invalid values (before filling, so we never fill junk rows)
    invalid = int(((df["quantity"] <= 0) | (df["unit_price"] <= 0)).sum())
    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0)]
    report["rows_dropped_invalid_values"] = invalid

    # 6. Missing values
    missing_before = df.isna().sum().to_dict()
    df["unit_price"] = df["unit_price"].fillna(df["unit_price"].median())
    df["quantity"] = df["quantity"].fillna(round(df["quantity"].median()))
    for col in ["customer_id", "region", "payment_method"]:
        df[col] = df[col].fillna("Unknown")
    report["missing_values_filled"] = {k: int(v) for k, v in missing_before.items() if v > 0}

    # Derived column
    df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)
    df["quantity"] = df["quantity"].astype(int)
    df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")

    if flag_outliers:
        df["is_price_outlier"] = flag_outliers_iqr(df, "unit_price", "category")
        report["price_outliers_flagged"] = int(df["is_price_outlier"].sum())

    report["rows_after"] = len(df)
    report["completeness_after_pct"] = completeness(df)
    return df, report


def write_report(report, path):
    lines = [
        "# Data Cleaning Report",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Rows before cleaning | {report['rows_before']} |",
        f"| Exact duplicates removed | {report['duplicates_removed']} |",
        f"| Rows dropped (unparseable date) | {report['rows_dropped_unparseable_date']} |",
        f"| Rows dropped (invalid quantity/price) | {report['rows_dropped_invalid_values']} |",
        f"| Rows after cleaning | {report['rows_after']} |",
        f"| Completeness after cleaning | {report['completeness_after_pct']}% |",
    ]
    if "price_outliers_flagged" in report:
        lines.append(f"| Price outliers flagged (IQR, per category) | {report['price_outliers_flagged']} |")
    lines += [
        "",
        "## Missing values filled",
        "",
    ]
    if report["missing_values_filled"]:
        for col, count in report["missing_values_filled"].items():
            lines.append(f"- `{col}`: {count}")
    else:
        lines.append("- None")
    lines += [
        "",
        "## Cleaning steps applied",
        "",
        "1. Column names standardized to snake_case",
        "2. Exact duplicate rows removed",
        "3. Text fields trimmed; categories unified to title case (`and` normalized to `&`)",
        "4. Mixed date formats parsed to ISO `YYYY-MM-DD` (day-first fallback)",
        "5. `unit_price` coerced to numeric (currency symbols and separators stripped)",
        "6. Missing values filled: median for numerics, `Unknown` for categoricals",
        "7. Rows with non-positive quantity or price dropped",
        "8. Derived column `total_amount = quantity * unit_price` added",
    ]
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Clean a messy sales CSV.")
    parser.add_argument("--input", default="data/raw/messy_sales.csv")
    parser.add_argument("--output", default="data/cleaned/clean_sales.csv")
    parser.add_argument("--report", default="reports/cleaning_report.md")
    parser.add_argument("--flag-outliers", action="store_true",
                        help="add an is_price_outlier column (IQR rule per category); rows are kept")
    parser.add_argument("--plot", default=None, metavar="PATH",
                        help="write a before/after quality chart to PATH (e.g. figures/before_after.png)")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    clean_df, report = clean(df.copy(), flag_outliers=args.flag_outliers)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(args.output, index=False)
    write_report(report, args.report)
    if args.plot:
        Path(args.plot).parent.mkdir(parents=True, exist_ok=True)
        plot_before_after(df, clean_df, args.plot)
    print(json.dumps(report, indent=2))
    print(f"Cleaned data -> {args.output}")
    print(f"Report       -> {args.report}")


if __name__ == "__main__":
    main()
