"""Day 5 · Lab 1 · Part 3 — HRLookupPlugin.

Wraps the Day 1 HR connector behaviour as SK kernel functions.
For training simplicity we return canned mock data for the three
course personas — in production, each method would call the real
Connector endpoint from Day 1.

Why the descriptions are verbose:
  The `description=` argument is what the model reads when deciding
  whether to call the function. Terse descriptions = agent that
  doesn't call the tool. Start each with a verb, name the use-case.
"""
from typing import Annotated

from semantic_kernel.functions import kernel_function

# The same three personas used in Days 1–4. Keeping them consistent
# means eval prompts from earlier days still score against this agent.
_EMPLOYEES = {
    "E-1042": {
        "name": "Priya Raman",
        "vacation_available": 12.5,
        "vacation_used": 7.5,
        "manager": "Jordan Chen",
        "department": "Engineering",
    },
    "E-1357": {
        "name": "Aisha Patel",
        "vacation_available": 18.0,
        "vacation_used": 2.0,
        "manager": "Sam Ortiz",
        "department": "Product",
    },
    "E-1199": {
        "name": "Daniel Okafor",
        "vacation_available": 6.0,
        "vacation_used": 14.0,
        "manager": "Jordan Chen",
        "department": "Engineering",
    },
}

_POLICIES = {
    "vacation": (
        "Vacation: 20 days/year accrued monthly. Max carryover 5 days "
        "into next calendar year. Requests > 5 consecutive days need "
        "manager approval 2 weeks in advance."
    ),
    "leave": (
        "Leave: bereavement up to 5 paid days, jury duty fully paid, "
        "medical leave follows FMLA (12 weeks unpaid, benefits retained)."
    ),
    "benefits": (
        "Benefits: medical/dental/vision from day 1, 401(k) 5% match "
        "after 90 days, $2,000 annual learning stipend, ESPP 15% "
        "discount."
    ),
    "travel": (
        "Travel: economy domestic / business international for flights "
        "> 6 hrs. Per diem $75 US, $100 intl. Book via Concur. All "
        "spend > $500 needs manager pre-approval."
    ),
}


class HRLookupPlugin:
    """SK plugin exposing Contoso HR lookups as agent tools."""

    @kernel_function(
        description=(
            "Look up the current vacation balance for a specific "
            "Contoso employee by their employee ID (format: E-NNNN). "
            "Returns days available, days used, and the employee name."
        ),
        name="get_vacation_balance",
    )
    def get_vacation_balance(
        self,
        employee_id: Annotated[str, "The employee ID, e.g. E-1042"],
    ) -> str:
        emp = _EMPLOYEES.get(employee_id.upper().strip())
        if not emp:
            return f"No employee found with ID '{employee_id}'."
        return (
            f"{emp['name']} ({employee_id}): "
            f"{emp['vacation_available']} days available, "
            f"{emp['vacation_used']} days used."
        )

    @kernel_function(
        description=(
            "Look up a Contoso HR policy by topic. Valid topics: "
            "'vacation', 'leave', 'benefits', 'travel'. Returns the "
            "policy text. Use for questions about company rules, "
            "not for specific employee data."
        ),
        name="get_hr_policy",
    )
    def get_hr_policy(
        self,
        topic: Annotated[
            str,
            "The policy topic: 'vacation', 'leave', 'benefits', or 'travel'.",
        ],
    ) -> str:
        policy = _POLICIES.get(topic.lower().strip())
        if not policy:
            valid = ", ".join(sorted(_POLICIES.keys()))
            return f"Unknown policy topic '{topic}'. Valid topics: {valid}."
        return policy
