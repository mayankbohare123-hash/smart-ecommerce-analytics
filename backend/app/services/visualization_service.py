"""
services/visualization_service.py
───────────────────────────────────
Transforms raw analytics data into Chart.js-compatible JSON payloads.

Every method returns a ChartData object — the exact structure Chart.js
expects on the frontend:
    {
        labels: [...],
        datasets: [{ label, data, backgroundColor, borderColor, ... }]
    }

Color palettes are carefully chosen for accessibility and dark mode
compatibility. Each chart type has its own tailored color scheme.

Usage:
    analytics_svc = AnalyticsService(df)
    viz_svc       = VisualizationService(analytics_svc)
    chart_data    = viz_svc.build_all(file_id=1)
"""

from typing import List, Optional
from loguru import logger

from app.models.schemas import (
    ChartData,
    ChartDataset,
    VisualizationResponse,
)
from app.services.analytics_service import AnalyticsService


# ── Color Palettes ────────────────────────────────────────────────────────────
# Chosen for contrast, accessibility, and readability on both light/dark bg.

# Multi-series line / bar — distinct, high-contrast
PALETTE_MULTI = [
    "#6366f1",  # indigo
    "#22c55e",  # green
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#06b6d4",  # cyan
    "#a855f7",  # purple
    "#f97316",  # orange
    "#14b8a6",  # teal
]

# Gradient ramp for single-series bars (darkest → lightest)
PALETTE_BARS = [
    "#4f46e5", "#5b52e8", "#675feb", "#736bee",
    "#7f78f1", "#8b84f4", "#9790f7", "#a39dfa",
    "#afa9fc", "#bbb6ff",
]

# Doughnut / pie slices — warm-to-cool arc
PALETTE_PIE = [
    "#6366f1", "#8b5cf6", "#a855f7",
    "#ec4899", "#f43f5e", "#f97316",
    "#f59e0b", "#22c55e",
]

# Region horizontal bars — single cohesive ramp
PALETTE_REGION = [
    "#0ea5e9", "#38bdf8", "#7dd3fc", "#bae6fd", "#e0f2fe",
]


class VisualizationService:
    """
    Builds all Chart.js-ready payloads for the frontend dashboard.

    Depends on a fully constructed AnalyticsService so that
    data is only aggregated once per request.
    """

    def __init__(self, analytics: AnalyticsService):
        self.analytics = analytics

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def build_all(self, file_id: int) -> VisualizationResponse:
        """
        Build every chart payload in one call.
        This is the only method the route handler calls.
        """
        logger.info(f"Building visualization data for file_id={file_id}")

        return VisualizationResponse(
            file_id=file_id,
            revenue_trend=self.revenue_trend_chart(),
            top_products=self.top_products_chart(),
            category_pie=self.category_pie_chart(),
            region_bar=self.region_bar_chart(),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 1 — Revenue Trend (Line Chart)
    # ─────────────────────────────────────────────────────────────────────────

    def revenue_trend_chart(self, include_orders: bool = True) -> ChartData:
        """
        Monthly revenue trend as a dual-axis line chart.

        Dataset 1 (primary Y): Revenue in dollars — smooth filled line
        Dataset 2 (secondary Y): Order count — thin dashed line

        Frontend usage:
            type: 'line'
            options.scales.y  → revenue (left axis)
            options.scales.y1 → orders  (right axis, dataset borderDash: [5,5])
        """
        monthly = self.analytics._monthly_sales()

        if not monthly:
            return ChartData(labels=[], datasets=[])

        labels   = [m.month for m in monthly]
        revenues = [m.revenue for m in monthly]
        orders   = [m.orders for m in monthly]

        datasets: List[ChartDataset] = [
            ChartDataset(
                label="Monthly Revenue ($)",
                data=revenues,
                borderColor="#6366f1",
                backgroundColor="rgba(99, 102, 241, 0.08)",
                borderWidth=2,
                fill=True,
                tension=0.4,
            ),
        ]

        if include_orders:
            datasets.append(
                ChartDataset(
                    label="Orders",
                    data=orders,
                    borderColor="#22c55e",
                    backgroundColor="rgba(34, 197, 94, 0.0)",
                    borderWidth=2,
                    fill=False,
                    tension=0.4,
                )
            )

        return ChartData(labels=labels, datasets=datasets)

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 2 — Top Products (Horizontal Bar Chart)
    # ─────────────────────────────────────────────────────────────────────────

    def top_products_chart(self, limit: int = 8) -> ChartData:
        """
        Top N products by revenue as a horizontal bar chart.

        Each bar gets a progressively lighter shade of indigo
        so the chart feels like a ranked list (most important = darkest).

        Frontend usage:
            type: 'bar'
            options.indexAxis: 'y'   ← makes it horizontal
        """
        products = self.analytics._top_products(limit=limit)

        if not products:
            return ChartData(labels=[], datasets=[])

        labels  = [p.product for p in products]
        revenue = [p.revenue for p in products]

        # Assign a shade per bar — cycle palette if more products than shades
        colors = [
            PALETTE_BARS[i % len(PALETTE_BARS)]
            for i in range(len(products))
        ]

        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Revenue ($)",
                    data=revenue,
                    backgroundColor=colors,
                    borderColor=colors,
                    borderWidth=0,
                    fill=False,
                    tension=0.0,
                )
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 3 — Category Breakdown (Doughnut / Pie)
    # ─────────────────────────────────────────────────────────────────────────

    def category_pie_chart(self) -> ChartData:
        """
        Revenue share by product category as a doughnut chart.

        Uses a warm-to-cool arc palette so adjacent slices
        are always distinguishable.

        Frontend usage:
            type: 'doughnut'
            options.plugins.legend.position: 'right'
        """
        categories = self.analytics._category_sales()

        if not categories:
            return ChartData(labels=[], datasets=[])

        labels  = [c.category for c in categories]
        revenue = [c.revenue for c in categories]

        # Cycle palette colors if more categories than swatches
        colors = [PALETTE_PIE[i % len(PALETTE_PIE)] for i in range(len(categories))]

        # Build slightly lighter border colors for the slice gap effect
        border_colors = ["rgba(255,255,255,0.1)"] * len(categories)

        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Revenue by Category",
                    data=revenue,
                    backgroundColor=colors,
                    borderColor=border_colors,
                    borderWidth=2,
                    fill=False,
                    tension=0.0,
                )
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 4 — Regional Sales (Horizontal Bar, sorted)
    # ─────────────────────────────────────────────────────────────────────────

    def region_bar_chart(self) -> ChartData:
        """
        Revenue and order count by region as a grouped horizontal bar chart.

        Two datasets allow the frontend to render either:
          - A grouped bar (revenue + orders side by side)
          - A stacked bar
          - Just revenue bars (hide the orders dataset)

        Frontend usage:
            type: 'bar'
            options.indexAxis: 'y'
        """
        regions = self.analytics._region_sales()

        if not regions:
            return ChartData(labels=[], datasets=[])

        # Already sorted by revenue desc in analytics service
        labels  = [r.region for r in regions]
        revenue = [r.revenue for r in regions]
        orders  = [r.orders for r in regions]
        pcts    = [r.percentage for r in regions]

        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Revenue ($)",
                    data=revenue,
                    backgroundColor="rgba(14, 165, 233, 0.85)",   # sky-500
                    borderColor="#0ea5e9",
                    borderWidth=1,
                    fill=False,
                    tension=0.0,
                ),
                ChartDataset(
                    label="Orders",
                    data=orders,
                    backgroundColor="rgba(99, 102, 241, 0.7)",    # indigo-500
                    borderColor="#6366f1",
                    borderWidth=1,
                    fill=False,
                    tension=0.0,
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Bonus Charts
    # ─────────────────────────────────────────────────────────────────────────

    def weekly_trend_chart(self) -> ChartData:
        """
        Weekly revenue trend — more granular than monthly.
        Useful for a zoom-in view on the dashboard.
        """
        weekly_df = self.analytics.weekly_sales()

        if weekly_df.empty:
            return ChartData(labels=[], datasets=[])

        labels  = [str(d.date()) for d in weekly_df["week_start"]]
        revenue = [round(float(v), 2) for v in weekly_df["revenue"]]

        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Weekly Revenue ($)",
                    data=revenue,
                    borderColor="#f59e0b",
                    backgroundColor="rgba(245, 158, 11, 0.08)",
                    borderWidth=2,
                    fill=True,
                    tension=0.3,
                )
            ],
        )

    def units_sold_chart(self, limit: int = 8) -> ChartData:
        """
        Top products by units sold (not revenue).
        Highlights volume leaders vs revenue leaders.
        """
        products = self.analytics._top_products(limit=limit)
        products_by_units = sorted(products, key=lambda p: p.units_sold, reverse=True)

        labels = [p.product for p in products_by_units]
        units  = [p.units_sold for p in products_by_units]
        colors = ["rgba(168, 85, 247, 0.8)"] * len(products_by_units)  # purple

        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Units Sold",
                    data=units,
                    backgroundColor=colors,
                    borderColor=["#a855f7"] * len(products_by_units),
                    borderWidth=0,
                    fill=False,
                    tension=0.0,
                )
            ],
        )
