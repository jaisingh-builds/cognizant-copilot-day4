"""Day 5 · Lab 2 · shared — PolicyComparePlugin for the Analyst."""
from typing import Annotated

from semantic_kernel.functions import kernel_function


class PolicyComparePlugin:
    @kernel_function(
        description=(
            "Compare an employee's vacation usage against Contoso "
            "policy. Returns the percentage of annual allowance used "
            "and a category (low / normal / high / at-risk). Use "
            "ONLY when you already have both the employee's balance "
            "AND the vacation policy facts."
        ),
        name="compare_vacation_usage",
    )
    def compare_vacation_usage(
        self,
        days_available: Annotated[
            float, "Days still available from the employee's balance."
        ],
        days_used: Annotated[
            float, "Days already used from the employee's balance."
        ],
        annual_allowance: Annotated[
            float, "Annual allowance from policy. Default 20.", 20.0
        ] = 20.0,
    ) -> str:
        total = days_available + days_used
        if total <= 0:
            return "No usage data — compare unavailable."
        pct_used = (days_used / annual_allowance) * 100
        if pct_used < 25:
            category = "low"
        elif pct_used < 60:
            category = "normal"
        elif pct_used < 90:
            category = "high"
        else:
            category = "at-risk (near or over allowance)"
        return (
            f"{days_used} of {annual_allowance} days used "
            f"({pct_used:.0f}% of annual) — category: {category}. "
            f"{days_available} days remaining."
        )
