"""
utils/validators.py
───────────────────
CSV structure and data-quality validators.

All validators raise ValueError with a human-readable message on failure,
so route handlers can catch them and return clean 422 responses.
"""

import pandas as pd
from typing import List, Tuple, Dict


# ── Required columns ─────────────────────────────────────────────────────────
# The upload service will map user column names to these canonical names.
# At minimum, a CSV must have a date column and a revenue/sales column.

REQUIRED_COLUMN_PATTERNS: Dict[str, List[str]] = {
    # canonical name → accepted aliases (case-insensitive)
    "order_date": [
        "order_date", "date", "sale_date", "transaction_date",
        "purchase_date", "order date", "sale date",
    ],
    "net_revenue": [
        "net_revenue", "revenue", "sales", "amount", "total",
        "total_price", "net revenue", "total price", "price",
    ],
}

# Columns that are optional but used for richer analytics if present
OPTIONAL_COLUMNS: Dict[str, List[str]] = {
    "product":   ["product", "product_name", "item", "item_name"],
    "category":  ["category", "product_category", "type"],
    "region":    ["region", "area", "zone", "location", "territory"],
    "quantity":  ["quantity", "qty", "units", "units_sold"],
    "customer_id": ["customer_id", "customer", "user_id", "client_id"],
    "order_id":  ["order_id", "order", "transaction_id", "id"],
    "discount":  ["discount", "discount_pct", "discount_rate"],
}


def normalize_column_name(col: str) -> str:
    """Lowercase and strip whitespace from a column name for comparison."""
    return col.strip().lower().replace("-", "_").replace(" ", "_")


def detect_column_mapping(df_columns: List[str]) -> Dict[str, str]:
    """
    Attempt to map the user's CSV columns to our canonical column names.

    Returns a dict: { canonical_name → actual_csv_column_name }
    Only includes columns that were successfully matched.

    Example:
        CSV has: ["Date", "Total Price", "Product Name", "Region"]
        Returns: {
            "order_date": "Date",
            "net_revenue": "Total Price",
            "product": "Product Name",
            "region": "Region",
        }
    """
    normalized = {normalize_column_name(c): c for c in df_columns}
    mapping: Dict[str, str] = {}

    all_patterns = {**REQUIRED_COLUMN_PATTERNS, **OPTIONAL_COLUMNS}

    for canonical, aliases in all_patterns.items():
        for alias in aliases:
            norm_alias = normalize_column_name(alias)
            if norm_alias in normalized:
                mapping[canonical] = normalized[norm_alias]
                break

    return mapping


def validate_required_columns(df_columns: List[str]) -> Tuple[bool, List[str]]:
    """
    Check that the CSV contains at least the required columns.

    Returns:
        (is_valid, missing_canonical_names)
    """
    mapping = detect_column_mapping(df_columns)
    missing = [col for col in REQUIRED_COLUMN_PATTERNS if col not in mapping]
    return len(missing) == 0, missing


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Run data-quality checks on the parsed DataFrame.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors: List[str] = []

    # ── 1. Not empty ────────────────────────────────────────────────────────
    if df.empty:
        errors.append("The CSV file contains no data rows.")
        return False, errors

    if len(df) < 2:
        errors.append("The CSV must contain at least 2 data rows.")

    # ── 2. Not too many columns (sanity check) ───────────────────────────────
    if len(df.columns) > 100:
        errors.append(f"Too many columns ({len(df.columns)}). Maximum is 100.")

    # ── 3. Check for a usable date column ───────────────────────────────────
    mapping = detect_column_mapping(list(df.columns))
    if "order_date" in mapping:
        date_col = mapping["order_date"]
        try:
            parsed = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")
            null_count = parsed.isna().sum()
            if null_count > len(df) * 0.5:
                errors.append(
                    f"Column '{date_col}' has too many unparseable dates "
                    f"({null_count}/{len(df)} rows)."
                )
        except Exception as e:
            errors.append(f"Could not parse date column '{date_col}': {e}")

    # ── 4. Check for a usable numeric revenue column ─────────────────────────
    if "net_revenue" in mapping:
        rev_col = mapping["net_revenue"]
        numeric = pd.to_numeric(df[rev_col], errors="coerce")
        null_count = numeric.isna().sum()
        if null_count > len(df) * 0.5:
            errors.append(
                f"Column '{rev_col}' has too many non-numeric values "
                f"({null_count}/{len(df)} rows)."
            )
        elif numeric.dropna().lt(0).all():
            errors.append(f"Column '{rev_col}' contains only negative values.")

    return len(errors) == 0, errors


def get_csv_summary(df: pd.DataFrame) -> Dict:
    """
    Return a human-readable summary of the uploaded CSV.
    Used in the upload response payload.
    """
    mapping = detect_column_mapping(list(df.columns))

    summary = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "detected_mapping": mapping,
        "null_counts": df.isnull().sum().to_dict(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }

    # Date range if we found a date column
    if "order_date" in mapping:
        date_col = mapping["order_date"]
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not dates.empty:
            summary["date_range"] = {
                "start": dates.min().date().isoformat(),
                "end":   dates.max().date().isoformat(),
            }

    return summary
