# Data Cleaning Report

| Metric | Value |
| --- | --- |
| Rows before cleaning | 1248 |
| Exact duplicates removed | 48 |
| Rows dropped (unparseable date) | 0 |
| Rows dropped (invalid quantity/price) | 35 |
| Rows after cleaning | 1165 |

## Missing values filled

- `customer_id`: 38
- `region`: 39
- `payment_method`: 37

## Cleaning steps applied

1. Column names standardized to snake_case
2. Exact duplicate rows removed
3. Text fields trimmed; categories unified to title case (`and` normalized to `&`)
4. Mixed date formats parsed to ISO `YYYY-MM-DD` (day-first fallback)
5. `unit_price` coerced to numeric (currency symbols and separators stripped)
6. Missing values filled: median for numerics, `Unknown` for categoricals
7. Rows with non-positive quantity or price dropped
8. Derived column `total_amount = quantity * unit_price` added
