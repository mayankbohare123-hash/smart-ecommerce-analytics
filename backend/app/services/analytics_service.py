"""
services/analytics_service.py
──────────────────────────────
Core analytics engine powered by Pandas.

Responsibilities:
  - Normalize uploaded CSV columns to canonical names
  - Compute KPI metrics (revenue, orders, AOV, growth)
  - Build monthly sales time series
  - Rank top products by revenue
  - Break down sales by region and category
  - Return fully typed Pydantic response objects

All methods are pure functions of the DataFrame — no side effects,
no DB access, easy to unit-test in isolation.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.models.schemas import (
    AnalyticsResponse,
    KPIMetrics,
    MonthlySales,
    TopProduct,
    RegionSales,
    CategorySales,
)
from app.utils.validators import detect_column_mapping


class AnalyticsService:
    """
    Computes all analytics from a Pandas DataFrame.

    Usage:
        service = AnalyticsService(df)
        result  = service.compute_all(file_id=1)
    """

    def __init__(self, df: pd.DataFrame):
        # Normalize the raw DataFrame on construction
        self.raw_df = df
        self.df, self.col_map = self._normalize(df)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def compute_all(self, file_id: int) -> AnalyticsResponse:
        """
        Run every analytics computation and return a single response object.
        This is the only method the route handler needs to call.
        """
        logger.info(f"Computing analytics for file_id={file_id}, rows={len(self.df)}")

        return AnalyticsResponse(
            file_id=file_id,
            kpis=self._compute_kpis(),
            monthly_sales=self._monthly_sales(),
            top_products=self._top_products(limit=10),
            region_sales=self._region_sales(),
            category_sales=self._category_sales(),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Normalization
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """
        Map the user's column names to canonical names and
        cast columns to appropriate types.

        Returns:
            (normalized_df, column_mapping_dict)
        """
        col_map = detect_column_mapping(list(df.columns))
        logger.debug(f"Column mapping: {col_map}")

        # Rename matched columns to canonical names
        rename = {v: k for k, v in col_map.items()}
        df = df.rename(columns=rename).copy()

        # ── Parse order_date ─────────────────────────────────────────────────
        if "order_date" in df.columns:
            df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
            # Drop rows where date couldn't be parsed
            before = len(df)
            df = df.dropna(subset=["order_date"])
            dropped = before - len(df)
            if dropped > 0:
                logger.warning(f"Dropped {dropped} rows with unparseable dates")

            # Extract time components for grouping
            df["year"]       = df["order_date"].dt.year
            df["month"]      = df["order_date"].dt.month
            df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
            df["week"]       = df["order_date"].dt.isocalendar().week.astype(int)

        # ── Cast net_revenue to float ────────────────────────────────────────
        if "net_revenue" in df.columns:
            df["net_revenue"] = pd.to_numeric(df["net_revenue"], errors="coerce").fillna(0.0)

        # ── Cast quantity to int ─────────────────────────────────────────────
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
        else:
            df["quantity"] = 1  # default: each row = 1 unit

        # ── Fill optional string columns with "Unknown" ──────────────────────
        for col in ("product", "category", "region", "customer_id"):
            if col not in df.columns:
                df[col] = "Unknown"
            else:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip()

        return df, col_map

    # ─────────────────────────────────────────────────────────────────────────
    # KPI Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_kpis(self) -> KPIMetrics:
        """
        Compute top-level KPI cards:
        - Total revenue (sum of net_revenue)
        - Total orders (row count — each row = one order line)
        - Average order value (revenue / orders)
        - Unique customers
        - Top product by revenue
        - Top region by revenue
        - Month-over-month revenue growth (last two complete months)
        """
        df = self.df

        total_revenue    = float(df["net_revenue"].sum())
        total_orders     = len(df)
        avg_order_value  = total_revenue / total_orders if total_orders > 0 else 0.0
        unique_customers = df["customer_id"].nunique() if "customer_id" in df.columns else 0

        # Top product by total revenue
        if "product" in df.columns:
            top_product = (
                df.groupby("product")["net_revenue"]
                .sum()
                .idxmax()
            )
        else:
            top_product = "N/A"

        # Top region by total revenue
        top_region = (
            df.groupby("region")["net_revenue"]
            .sum()
            .idxmax()
        ) if "region" in df.columns else "N/A"

        # MoM revenue growth — compare last two complete calendar months
        revenue_growth = self._compute_mom_growth(df)

        return KPIMetrics(
            total_revenue=round(total_revenue, 2),
            total_orders=total_orders,
            avg_order_value=round(avg_order_value, 2),
            unique_customers=int(unique_customers),
            top_product=str(top_product),
            top_region=str(top_region),
            revenue_growth=revenue_growth,
        )

    def _compute_mom_growth(self, df: pd.DataFrame) -> Optional[float]:
        """
        Calculate month-over-month revenue growth percentage.
        Uses the two most recent complete months in the dataset.
        Returns None if there isn't enough data.
        """
        if "year_month" not in df.columns:
            return None

        monthly = (
            df.groupby("year_month")["net_revenue"]
            .sum()
            .sort_index()
        )

        if len(monthly) < 2:
            return None

        prev_month_rev = float(monthly.iloc[-2])
        last_month_rev = float(monthly.iloc[-1])

        if prev_month_rev == 0:
            return None

        growth = ((last_month_rev - prev_month_rev) / prev_month_rev) * 100
        return round(growth, 2)

    # ─────────────────────────────────────────────────────────────────────────
    # Monthly Sales Time Series
    # ─────────────────────────────────────────────────────────────────────────

    def _monthly_sales(self) -> List[MonthlySales]:
        """
        Aggregate revenue and order count by calendar month.
        Returns a list sorted chronologically — perfect for a line chart.

        Example output:
            [{"month": "2023-01", "revenue": 12450.50, "orders": 87}, ...]
        """
        df = self.df
        if "year_month" not in df.columns:
            return []

        monthly = (
            df.groupby("year_month")
            .agg(
                revenue=("net_revenue", "sum"),
                orders=("net_revenue", "count"),
            )
            .reset_index()
            .sort_values("year_month")
        )

        return [
            MonthlySales(
                month=row["year_month"],
                revenue=round(float(row["revenue"]), 2),
                orders=int(row["orders"]),
            )
            for _, row in monthly.iterrows()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Top Products
    # ─────────────────────────────────────────────────────────────────────────

    def _top_products(self, limit: int = 10) -> List[TopProduct]:
        """
        Rank products by total net revenue (descending).
        Also reports total units sold for each product.

        Returns at most `limit` products.
        """
        df = self.df

        agg = (
            df.groupby("product")
            .agg(
                revenue=("net_revenue", "sum"),
                units_sold=("quantity", "sum"),
            )
            .reset_index()
            .sort_values("revenue", ascending=False)
            .head(limit)
            .reset_index(drop=True)
        )

        return [
            TopProduct(
                product=row["product"],
                revenue=round(float(row["revenue"]), 2),
                units_sold=int(row["units_sold"]),
                rank=idx + 1,
            )
            for idx, row in agg.iterrows()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Regional Breakdown
    # ─────────────────────────────────────────────────────────────────────────

    def _region_sales(self) -> List[RegionSales]:
        """
        Aggregate revenue and order count by region.
        Also computes each region's percentage share of total revenue.
        Sorted by revenue descending.
        """
        df = self.df
        total_revenue = df["net_revenue"].sum()

        regional = (
            df.groupby("region")
            .agg(
                revenue=("net_revenue", "sum"),
                orders=("net_revenue", "count"),
            )
            .reset_index()
            .sort_values("revenue", ascending=False)
        )

        return [
            RegionSales(
                region=row["region"],
                revenue=round(float(row["revenue"]), 2),
                orders=int(row["orders"]),
                percentage=round(
                    float(row["revenue"] / total_revenue * 100) if total_revenue > 0 else 0,
                    1,
                ),
            )
            for _, row in regional.iterrows()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Category Breakdown
    # ─────────────────────────────────────────────────────────────────────────

    def _category_sales(self) -> List[CategorySales]:
        """
        Aggregate revenue and units sold by product category.
        Sorted by revenue descending.
        """
        df = self.df

        cats = (
            df.groupby("category")
            .agg(
                revenue=("net_revenue", "sum"),
                units_sold=("quantity", "sum"),
            )
            .reset_index()
            .sort_values("revenue", ascending=False)
        )

        return [
            CategorySales(
                category=row["category"],
                revenue=round(float(row["revenue"]), 2),
                units_sold=int(row["units_sold"]),
            )
            for _, row in cats.iterrows()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Bonus: Weekly trend (used by visualization service in Step 4)
    # ─────────────────────────────────────────────────────────────────────────

    def weekly_sales(self) -> pd.DataFrame:
        """
        Return weekly aggregated revenue as a raw DataFrame.
        Called by VisualizationService — not part of the main analytics response.
        """
        df = self.df
        if "order_date" not in df.columns:
            return pd.DataFrame()

        df["week_start"] = df["order_date"] - pd.to_timedelta(
            df["order_date"].dt.dayofweek, unit="D"
        )

        return (
            df.groupby("week_start")
            .agg(revenue=("net_revenue", "sum"), orders=("net_revenue", "count"))
            .reset_index()
            .sort_values("week_start")
        )

    def daily_revenue_series(self) -> pd.Series:
        """
        Return a daily revenue Series indexed by date.
        Used by the ML prediction service in Step 5 for feature engineering.
        """
        df = self.df
        if "order_date" not in df.columns:
            return pd.Series(dtype=float)

        daily = (
            df.groupby(df["order_date"].dt.date)["net_revenue"]
            .sum()
            .sort_index()
        )
        daily.index = pd.to_datetime(daily.index)
        return daily
