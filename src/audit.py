"""Build an audit of what the pipeline changed, from the raw file and the cleaned output.

Everything is computed by running the real pipeline on the raw CSV, then comparing
cell by cell. The result is written to docs/data.json for the live demo.

    python src/audit.py
"""
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.clean_data import clean, coerce_price, normalize_categories, parse_dates, standardize_columns  # noqa: E402
from src.quality import completeness, profile  # noqa: E402

warnings.filterwarnings("ignore")

DATE_PATTERNS = [
    ("2025-01-31", r"\d{4}-\d{2}-\d{2}", "year first, unambiguous"),
    ("31 Jan 2025", r"\d{1,2} [A-Za-z]{3} \d{4}", "month name, unambiguous"),
    ("31/01/2025", r"\d{1,2}/\d{1,2}/\d{4}", "slash, read day-first"),
    ("01-31-2025", r"\d{1,2}-\d{1,2}-\d{4}", "dash, read month-first"),
]
PRICE_PATTERNS = [
    ("plain number", r"\d+(\.\d+)?"),
    ("$ prefix", r"\$.*"),
    ("EGP suffix", r".*EGP"),
]


def classify(value, patterns):
    v = str(value).strip()
    for entry in patterns:
        if re.fullmatch(entry[1], v):
            return entry[0]
    return "other"


def build(raw_path="data/raw/messy_sales.csv", clean_path="data/cleaned/clean_sales.csv"):
    raw = pd.read_csv(raw_path)
    rawn = standardize_columns(raw.copy())
    cleaned, report = clean(raw.copy(), flag_outliers=True)

    # --- date formats, and how many were ambiguous ---
    d = rawn["order_date"].astype(str).str.strip()
    fmt = d.map(lambda x: classify(x, DATE_PATTERNS))
    slash = d[d.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}")]
    ambiguous = int(slash.map(lambda x: int(x.split("/")[0]) <= 12 and int(x.split("/")[1]) <= 12).sum())
    dayfirst_naive = pd.to_datetime(slash, format="mixed", dayfirst=False, errors="coerce")
    dayfirst_used = parse_dates(slash)
    changed_vs_naive = int((dayfirst_naive != dayfirst_used).sum())

    # --- prices ---
    price_fmt = rawn["unit_price"].astype(str).map(lambda x: classify(x, PRICE_PATTERNS))
    price_num = coerce_price(rawn["unit_price"])

    # --- categorical variants ---
    cat_cols = ["category", "region", "payment_method", "product_name"]
    variants = {}
    for col in cat_cols:
        before = rawn[col].astype("string")
        after = normalize_categories(rawn[[col]].copy(), [col])[col].astype("string")
        pairs = Counter(zip(before.fillna("(missing)"), after.fillna("(missing)")))
        by_clean = {}
        for (b, a), n in pairs.items():
            by_clean.setdefault(a, []).append([b, n])
        variants[col] = {
            "raw_distinct": int(before.nunique()),
            "clean_distinct": int(after.nunique()),
            "map": {a: sorted(v, key=lambda x: -x[1]) for a, v in sorted(by_clean.items())},
        }

    # --- missing values ---
    pb, pa = profile(rawn), profile(cleaned)
    missing = [[c, int(pb.loc[c, "missing"]), int(pa.loc[c, "missing"]) if c in pa.index else 0] for c in pb.index]

    # --- row-level before/after sample (first 60 changed rows by order id) ---
    first = rawn.drop_duplicates().set_index("order_id")
    out = cleaned.set_index("order_id")
    rows = []
    for oid in sorted(out.index):
        r, c = first.loc[oid], out.loc[oid]
        changes = []
        if str(r["order_date"]).strip() != c["order_date"]:
            changes.append("date")
        if str(r["unit_price"]) != f"{c['unit_price']}" and not re.fullmatch(r"\d+(\.\d+)?", str(r["unit_price"])):
            changes.append("price")
        for col in ("category", "region", "payment_method"):
            if str(r[col]) != str(c[col]):
                changes.append(col)
        if changes:
            rows.append({"id": oid, "changes": changes,
                         "raw": [str(r["order_date"]), str(r["category"]), str(r["region"]), str(r["unit_price"])],
                         "clean": [c["order_date"], c["category"], c["region"], f"{c['unit_price']:.2f}"]})
    rows_changed = len(rows)
    fix_counts = Counter(c for r in rows for c in r["changes"])
    rows.sort(key=lambda r: -len(r["changes"]))

    # --- drops ---
    drops = {"duplicates": report["duplicates_removed"],
             "unparseable_date": report["rows_dropped_unparseable_date"],
             "invalid_quantity_or_price": report["rows_dropped_invalid_values"]}

    # --- outliers ---
    outl = cleaned.groupby("category")["is_price_outlier"].agg(["sum", "count"]).reset_index()

    # --- the cleaned data itself (small enough for the in-browser table) ---
    keep = ["order_id", "order_date", "customer_id", "product_name", "category", "region", "quantity", "unit_price", "payment_method", "total_amount"]
    data = {
        "report": report,
        "steps": [
            ["Read raw file", report["rows_before"], f"{raw.shape[1]} columns, {int(raw.isna().sum().sum())} empty cells"],
            ["Drop exact duplicates", -drops["duplicates"], "rows identical in every column"],
            ["Drop unparseable dates", -drops["unparseable_date"], "no usable date"],
            ["Drop invalid values", -drops["invalid_quantity_or_price"], "quantity or price of zero or below"],
            ["Result", report["rows_after"], f"{report['completeness_after_pct']}% of cells filled"],
        ],
        "completeness": [completeness(rawn), completeness(cleaned)],
        "date_formats": dict(Counter(fmt)),
        "date_ambiguity": {"slash_dates": int(len(slash)), "ambiguous": ambiguous, "differs_from_month_first_reading": changed_vs_naive},
        "price_formats": dict(Counter(price_fmt)),
        "price_unparseable": int(price_num.isna().sum() - rawn["unit_price"].isna().sum()),
        "variants": variants,
        "missing": missing,
        "rows_changed": rows_changed,
        "fix_counts": dict(fix_counts.most_common()),
        "changed_sample": rows[:80],
        "outliers": [[r["category"], int(r["sum"]), int(r["count"])] for _, r in outl.iterrows()],
        "cleaned": cleaned[keep].head(60).astype(object).where(cleaned[keep].head(60).notna(), None).values.tolist(),
        "cleaned_cols": keep,
    }
    # raw -> cleaned pairs, used to check the in-browser cleaner against the pipeline
    cat_clean = normalize_categories(rawn[["category"]].copy(), ["category"])["category"]
    dates_raw = d.unique()
    pairs = {
        "price": [[str(a), None if pd.isna(b) else float(b)] for a, b in
                  dict(zip(rawn["unit_price"].astype(str), price_num)).items()],
        "text": [[str(a), None if pd.isna(b) else str(b)] for a, b in
                 dict(zip(rawn["category"].astype(str), cat_clean)).items()],
        "date": [[x, parse_dates(pd.Series([x])).iloc[0].strftime("%Y-%m-%d")] for x in dates_raw
                 if not pd.isna(parse_dates(pd.Series([x])).iloc[0])],
    }
    return data, pairs


if __name__ == "__main__":
    data, pairs = build()
    Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
    Path("tests/fixtures/pairs.json").write_text(json.dumps(pairs))
    Path("docs").mkdir(exist_ok=True)
    Path("docs/data.json").write_text(json.dumps(data, default=str))
    print(json.dumps({k: data[k] for k in ("steps", "completeness", "date_formats", "date_ambiguity", "price_formats", "rows_changed")}, indent=1))
