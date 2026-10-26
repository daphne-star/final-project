"""Financial calculators.

Pure functions over explicit inputs: no database, no MCP, no global state.
That is what lets the same logic serve an in-process MCP server today and a
Streamable HTTP one later without touching anything here.

Every result carries the arithmetic it performed. The CFO is instructed never
to present an invented figure as fact, and a tool that returns a bare number
makes that instruction hard to follow — returning the working makes the
model's claim checkable by the reader.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field


class RunwayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_on_hand_usd: float = Field(gt=0, description="Unrestricted cash available now")
    monthly_burn_usd: float = Field(
        gt=0, description="Net monthly cash burn, before any change being considered"
    )
    monthly_burn_change_usd: float = Field(
        default=0.0,
        description="Change to monthly burn under the scenario. Negative to cut spend.",
    )
    expected_monthly_revenue_growth_usd: float = Field(
        default=0.0,
        ge=0,
        description="Additional monthly revenue expected, if any. Reduces net burn.",
    )


class RunwayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runway_months: float
    baseline_runway_months: float
    net_monthly_burn_usd: float
    change_in_runway_months: float
    calculation: str
    caveats: list[str]


def calculate_cash_runway(data: RunwayInput) -> RunwayResult:
    """Months of runway at a given burn, and how a change moves it."""
    baseline = data.cash_on_hand_usd / data.monthly_burn_usd

    net_burn = (
        data.monthly_burn_usd
        + data.monthly_burn_change_usd
        - data.expected_monthly_revenue_growth_usd
    )

    caveats = [
        "Assumes burn and revenue stay flat month to month; neither is usually true.",
        "Uses unrestricted cash only. Restricted cash or committed spend is not modelled.",
    ]

    if net_burn <= 0:
        return RunwayResult(
            runway_months=math.inf,
            baseline_runway_months=round(baseline, 1),
            net_monthly_burn_usd=round(net_burn, 2),
            change_in_runway_months=math.inf,
            calculation=(
                f"Net monthly burn is ${net_burn:,.0f}, i.e. not negative cash flow. "
                f"At these inputs the company does not consume cash, so runway is "
                f"not bounded by this calculation."
            ),
            caveats=[*caveats, "A non-positive net burn makes runway undefined, not infinite in practice."],
        )

    runway = data.cash_on_hand_usd / net_burn
    return RunwayResult(
        runway_months=round(runway, 1),
        baseline_runway_months=round(baseline, 1),
        net_monthly_burn_usd=round(net_burn, 2),
        change_in_runway_months=round(runway - baseline, 1),
        calculation=(
            f"${data.cash_on_hand_usd:,.0f} cash / ${net_burn:,.0f} net monthly burn "
            f"= {runway:.1f} months "
            f"(baseline {baseline:.1f} months at ${data.monthly_burn_usd:,.0f} burn)."
        ),
        caveats=caveats,
    )


class UnitEconomicsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_revenue_per_account_usd: float = Field(
        gt=0, description="Annual revenue per customer (ARPA)"
    )
    gross_margin_rate: float = Field(
        gt=0, le=1, description="Gross margin as a fraction, e.g. 0.78"
    )
    customer_acquisition_cost_usd: float = Field(ge=0, description="Fully loaded CAC")
    annual_churn_rate: float = Field(
        gt=0, le=1, description="Annual customer churn as a fraction, e.g. 0.15"
    )


class UnitEconomicsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_customer_lifetime_years: float
    lifetime_gross_profit_usd: float
    ltv_to_cac_ratio: float
    cac_payback_months: float
    calculation: str
    interpretation: str
    caveats: list[str]


def calculate_unit_economics(data: UnitEconomicsInput) -> UnitEconomicsResult:
    """LTV, LTV/CAC and CAC payback from explicit inputs."""
    lifetime_years = 1 / data.annual_churn_rate
    annual_gross_profit = data.average_revenue_per_account_usd * data.gross_margin_rate
    ltv = annual_gross_profit * lifetime_years
    ratio = ltv / data.customer_acquisition_cost_usd if data.customer_acquisition_cost_usd else math.inf
    monthly_gross_profit = annual_gross_profit / 12
    payback = (
        data.customer_acquisition_cost_usd / monthly_gross_profit
        if monthly_gross_profit
        else math.inf
    )

    if ratio >= 3 and payback <= 12:
        interpretation = "Healthy on both common thresholds (LTV/CAC >= 3, payback <= 12 months)."
    elif ratio >= 3:
        interpretation = (
            f"LTV/CAC is healthy but payback of {payback:.1f} months ties up cash longer "
            "than the common 12-month guideline."
        )
    elif payback <= 12:
        interpretation = (
            f"Payback is quick but LTV/CAC of {ratio:.1f} is below the common 3.0 guideline, "
            "so each customer returns less over their life than the rule of thumb expects."
        )
    else:
        interpretation = (
            f"Weak on both: LTV/CAC {ratio:.1f} (guideline 3.0) and payback "
            f"{payback:.1f} months (guideline 12)."
        )

    return UnitEconomicsResult(
        average_customer_lifetime_years=round(lifetime_years, 2),
        lifetime_gross_profit_usd=round(ltv, 2),
        ltv_to_cac_ratio=round(ratio, 2),
        cac_payback_months=round(payback, 1),
        calculation=(
            f"Lifetime = 1 / {data.annual_churn_rate:.2%} churn = {lifetime_years:.2f} years. "
            f"Annual gross profit = ${data.average_revenue_per_account_usd:,.0f} x "
            f"{data.gross_margin_rate:.0%} = ${annual_gross_profit:,.0f}. "
            f"LTV = ${annual_gross_profit:,.0f} x {lifetime_years:.2f} = ${ltv:,.0f}. "
            f"LTV/CAC = ${ltv:,.0f} / ${data.customer_acquisition_cost_usd:,.0f} = {ratio:.2f}. "
            f"Payback = ${data.customer_acquisition_cost_usd:,.0f} / "
            f"${monthly_gross_profit:,.0f} monthly gross profit = {payback:.1f} months."
        ),
        interpretation=interpretation,
        caveats=[
            "The 3.0 and 12-month figures are industry rules of thumb, not facts about this company.",
            "Assumes constant churn and margin; both usually vary by cohort and segment.",
            "Uses simple (not discounted) lifetime value.",
        ],
    )


class FinancialScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    monthly_burn_change_usd: float = Field(
        default=0.0, description="Change to monthly burn. Negative to cut spend."
    )
    one_off_cost_usd: float = Field(default=0.0, ge=0)
    expected_monthly_revenue_growth_usd: float = Field(default=0.0, ge=0)


class ScenarioComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_on_hand_usd: float = Field(gt=0)
    monthly_burn_usd: float = Field(gt=0)
    scenarios: list[FinancialScenario] = Field(min_length=1, max_length=6)


class ScenarioOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    runway_months: float
    change_vs_baseline_months: float
    net_monthly_burn_usd: float
    cash_after_one_off_usd: float


class ScenarioComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_runway_months: float
    outcomes: list[ScenarioOutcome]
    longest_runway: str
    calculation_note: str
    caveats: list[str]


def compare_financial_scenarios(data: ScenarioComparisonInput) -> ScenarioComparisonResult:
    """Runway under each explicitly supplied scenario. Invents nothing."""
    baseline = data.cash_on_hand_usd / data.monthly_burn_usd
    outcomes: list[ScenarioOutcome] = []

    for scenario in data.scenarios:
        cash = max(data.cash_on_hand_usd - scenario.one_off_cost_usd, 0.0)
        net_burn = (
            data.monthly_burn_usd
            + scenario.monthly_burn_change_usd
            - scenario.expected_monthly_revenue_growth_usd
        )
        runway = cash / net_burn if net_burn > 0 else math.inf
        outcomes.append(
            ScenarioOutcome(
                name=scenario.name,
                runway_months=round(runway, 1) if runway != math.inf else math.inf,
                change_vs_baseline_months=(
                    round(runway - baseline, 1) if runway != math.inf else math.inf
                ),
                net_monthly_burn_usd=round(net_burn, 2),
                cash_after_one_off_usd=round(cash, 2),
            )
        )

    best = max(outcomes, key=lambda o: o.runway_months)
    return ScenarioComparisonResult(
        baseline_runway_months=round(baseline, 1),
        outcomes=outcomes,
        longest_runway=best.name,
        calculation_note=(
            "Each scenario is cash less any one-off cost, divided by burn adjusted by "
            "that scenario's recurring change. Longest runway is not the same as best "
            "decision; it ignores what the spend would buy."
        ),
        caveats=[
            "Only the scenarios supplied were evaluated. No alternatives were invented.",
            "Revenue growth figures are inputs, not forecasts produced by this tool.",
        ],
    )
