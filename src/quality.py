"""Data-quality helpers: column profiling, outlier flagging and a before/after chart."""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def snake(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def profile(df):
    """Per-column quality profile: dtype, missing count/share and distinct values."""
    out = pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "missing_pct": (df.isna().mean() * 100).round(2),
        "unique": df.nunique(dropna=True),
    })
    out.index = [snake(c) for c in out.index]
    return out


def flag_outliers_iqr(df, value_col="unit_price", group_col="category", k=1.5):
    """Boolean Series: True where value is outside Q1 - k*IQR .. Q3 + k*IQR within its group.

    Flagging (not deleting) keeps the decision with the analyst: a very high price
    can be a real premium product rather than an error.
    """
    grouped = df.groupby(group_col)[value_col]
    q1 = grouped.transform(lambda s: s.quantile(0.25))
    q3 = grouped.transform(lambda s: s.quantile(0.75))
    iqr = q3 - q1
    return (df[value_col] < q1 - k * iqr) | (df[value_col] > q3 + k * iqr)


def completeness(df):
    """Share of non-missing cells, in percent."""
    total = df.shape[0] * df.shape[1]
    return 100.0 if total == 0 else round((1 - df.isna().sum().sum() / total) * 100, 2)


def plot_before_after(before, after, path="figures/before_after.png"):
    """Two-panel chart: missing values per column and row counts, raw vs cleaned."""
    pb, pa = profile(before), profile(after)
    cols = [c for c in pb.index if c in pa.index]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    x = range(len(cols))
    w = 0.38
    axes[0].bar([i - w / 2 for i in x], pb.loc[cols, "missing"], w, label="raw", color="#ef4444")
    axes[0].bar([i + w / 2 for i in x], pa.loc[cols, "missing"], w, label="cleaned", color="#10b981")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(cols, rotation=45, ha="right")
    axes[0].set_title("Missing values per column", fontweight="bold")
    axes[0].legend()
    axes[1].bar(["raw", "cleaned"], [len(before), len(after)], color=["#ef4444", "#10b981"])
    for i, v in enumerate([len(before), len(after)]):
        axes[1].text(i, v, f"{v:,}", ha="center", va="bottom")
    axes[1].set_title("Row count", fontweight="bold")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Completeness: {completeness(before)}% -> {completeness(after)}%", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
