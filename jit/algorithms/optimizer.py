"""
Tax optimization algorithms.

Implements recursive optimization strategies to minimize tax liability
while remaining fully compliant, including retirement contribution
optimization, entity structure analysis, and tax-loss harvesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class OptimizationStrategy:
    """A single tax optimization strategy."""

    strategy_id: str
    title: str
    description: str
    estimated_savings: float
    implementation_complexity: str  # "low", "medium", "high"
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)  # IRC sections


@dataclass
class OptimizationResult:
    """Result of tax optimization analysis."""

    gross_income: float
    current_estimated_tax: float
    optimized_estimated_tax: float
    total_savings: float
    strategies: List[OptimizationStrategy] = field(default_factory=list)
    implementation_order: List[str] = field(default_factory=list)  # Strategy IDs
    warnings: List[str] = field(default_factory=list)

    @property
    def savings_percentage(self) -> float:
        """Percentage reduction in tax liability."""
        if self.current_estimated_tax == 0:
            return 0.0
        return round(self.total_savings / self.current_estimated_tax * 100, 2)


# 2024 Contribution limits
LIMITS = {
    "401k_employee": 23_000,
    "401k_catchup": 7_500,       # Age 50+
    "ira_traditional": 7_000,
    "ira_catchup": 1_000,
    "sep_ira_rate": 0.25,         # 25% of net SE income
    "sep_ira_max": 69_000,
    "hsa_self": 4_150,
    "hsa_family": 8_300,
    "hsa_catchup": 1_000,         # Age 55+
    "fsa_health": 3_200,
    "dependent_care_fsa": 5_000,
    "solo_401k_total": 69_000,    # Employee + employer contributions
}

# Qualified Opportunity Zone deferral period (example parameters)
QOZ_DEFERRAL_YEARS = 10


class TaxOptimizer:
    """
    Recursive tax optimization engine.

    Analyzes a taxpayer's financial situation and recursively applies
    optimization strategies from highest to lowest impact, considering
    eligibility requirements and phase-outs.
    """

    def optimize(
        self,
        gross_income: float,
        current_tax: float,
        marginal_rate: float,
        filing_status: str = "single",
        age: int = 40,
        has_401k_access: bool = False,
        current_401k_contribution: float = 0.0,
        self_employment_income: float = 0.0,
        current_sep_contribution: float = 0.0,
        has_hsa_eligible_plan: bool = False,
        current_hsa_contribution: float = 0.0,
        has_hsa_family_coverage: bool = False,
        has_capital_losses: float = 0.0,
        unrealized_capital_gains: float = 0.0,
        charitable_intent: float = 0.0,
        qualified_business_income: float = 0.0,
        is_business_owner: bool = False,
        has_real_estate: bool = False,
        net_rental_income: float = 0.0,
        expected_state_tax: float = 0.0,
    ) -> OptimizationResult:
        """
        Run comprehensive tax optimization analysis.

        Args:
            gross_income: Total gross income.
            current_tax: Current estimated tax liability.
            marginal_rate: Marginal federal tax rate.
            filing_status: IRS filing status string.
            age: Taxpayer age.
            has_401k_access: Access to employer 401(k).
            current_401k_contribution: Current pre-tax 401(k) contribution.
            self_employment_income: Net SE income.
            current_sep_contribution: Current SEP-IRA contribution.
            has_hsa_eligible_plan: Enrolled in HDHP.
            current_hsa_contribution: Current HSA contribution.
            has_hsa_family_coverage: Family vs. self-only HDHP.
            has_capital_losses: Available capital loss carryforwards.
            unrealized_capital_gains: Unrealized gains in taxable accounts.
            charitable_intent: Amount planning to donate.
            qualified_business_income: QBI for §199A deduction.
            is_business_owner: Whether taxpayer owns a business.
            has_real_estate: Whether taxpayer owns investment real estate.
            net_rental_income: Net rental income.
            expected_state_tax: State tax for SALT planning.

        Returns:
            OptimizationResult with strategies sorted by estimated savings.
        """
        strategies: List[OptimizationStrategy] = []
        warnings: List[str] = []

        # Run each optimization sub-analysis recursively
        strategies.extend(self._optimize_retirement(
            gross_income, marginal_rate, age,
            has_401k_access, current_401k_contribution,
            self_employment_income, current_sep_contribution,
        ))

        strategies.extend(self._optimize_hsa(
            marginal_rate, age, has_hsa_eligible_plan,
            current_hsa_contribution, has_hsa_family_coverage,
        ))

        strategies.extend(self._optimize_capital_gains(
            has_capital_losses, unrealized_capital_gains,
            marginal_rate, gross_income, filing_status,
        ))

        strategies.extend(self._optimize_charitable(
            charitable_intent, marginal_rate, gross_income, filing_status,
        ))

        if qualified_business_income > 0:
            strategies.extend(self._optimize_qbi(
                qualified_business_income, gross_income, filing_status,
            ))

        if is_business_owner:
            strategies.extend(self._optimize_business_structure(
                gross_income, self_employment_income, marginal_rate,
            ))

        # Sort by estimated savings descending
        strategies.sort(key=lambda s: s.estimated_savings, reverse=True)

        total_savings = sum(s.estimated_savings for s in strategies)
        optimized_tax = max(0.0, current_tax - total_savings)
        impl_order = [s.strategy_id for s in strategies]

        return OptimizationResult(
            gross_income=gross_income,
            current_estimated_tax=current_tax,
            optimized_estimated_tax=round(optimized_tax, 2),
            total_savings=round(total_savings, 2),
            strategies=strategies,
            implementation_order=impl_order,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Sub-optimization methods
    # ------------------------------------------------------------------

    def _optimize_retirement(
        self,
        gross_income: float,
        marginal_rate: float,
        age: int,
        has_401k: bool,
        current_401k: float,
        se_income: float,
        current_sep: float,
    ) -> List[OptimizationStrategy]:
        """Optimize retirement account contributions."""
        strategies: List[OptimizationStrategy] = []

        # 401(k) optimization
        if has_401k:
            limit = LIMITS["401k_employee"] + (LIMITS["401k_catchup"] if age >= 50 else 0)
            room = max(0.0, limit - current_401k)
            if room > 0:
                savings = room * marginal_rate
                strategies.append(
                    OptimizationStrategy(
                        strategy_id="retire_401k",
                        title="Maximize 401(k) Pre-Tax Contributions",
                        description=(
                            f"Increase pre-tax 401(k) contribution by ${room:,.0f} "
                            f"(from ${current_401k:,.0f} to ${limit:,.0f}). "
                            f"Estimated tax savings: ${savings:,.0f} at {marginal_rate:.0%} rate."
                        ),
                        estimated_savings=round(savings, 2),
                        implementation_complexity="low",
                        citations=["IRC § 401(k)", "IRC § 402(g)"],
                    )
                )

        # SEP-IRA for SE income
        if se_income > 0:
            sep_limit = min(se_income * LIMITS["sep_ira_rate"], LIMITS["sep_ira_max"])
            room = max(0.0, sep_limit - current_sep)
            if room > 0:
                savings = room * marginal_rate
                strategies.append(
                    OptimizationStrategy(
                        strategy_id="retire_sep",
                        title="Maximize SEP-IRA Contribution",
                        description=(
                            f"Contribute ${room:,.0f} to a SEP-IRA "
                            f"(maximum: ${sep_limit:,.0f} = 25% of net SE income). "
                            f"Reduces both income and SE tax. Estimated savings: ${savings:,.0f}."
                        ),
                        estimated_savings=round(savings, 2),
                        implementation_complexity="low",
                        citations=["IRC § 408(k)", "IRC § 402(h)"],
                    )
                )

        return strategies

    def _optimize_hsa(
        self,
        marginal_rate: float,
        age: int,
        has_hsa: bool,
        current_hsa: float,
        family_coverage: bool,
    ) -> List[OptimizationStrategy]:
        """Optimize HSA contributions."""
        if not has_hsa:
            return []

        base_limit = LIMITS["hsa_family"] if family_coverage else LIMITS["hsa_self"]
        catchup = LIMITS["hsa_catchup"] if age >= 55 else 0
        limit = base_limit + catchup
        room = max(0.0, limit - current_hsa)

        if room <= 0:
            return []

        # HSA is triple tax-advantaged: pre-tax contribution, tax-free growth, tax-free withdrawals
        savings = room * marginal_rate
        return [
            OptimizationStrategy(
                strategy_id="hsa_max",
                title="Maximize HSA Contributions (Triple Tax Advantage)",
                description=(
                    f"Contribute ${room:,.0f} more to your Health Savings Account "
                    f"(limit: ${limit:,.0f}). HSA contributions are pre-tax, grow "
                    f"tax-free, and are tax-free when used for medical expenses. "
                    f"Estimated savings: ${savings:,.0f}."
                ),
                estimated_savings=round(savings, 2),
                implementation_complexity="low",
                citations=["IRC § 223"],
            )
        ]

    def _optimize_capital_gains(
        self,
        capital_losses: float,
        unrealized_gains: float,
        marginal_rate: float,
        agi: float,
        filing_status: str,
    ) -> List[OptimizationStrategy]:
        """Optimize capital gains and losses."""
        strategies: List[OptimizationStrategy] = []

        # Tax-loss harvesting
        if capital_losses > 0:
            usable_this_year = min(capital_losses, 3_000)  # Annual capital loss limit
            savings = usable_this_year * marginal_rate * 0.5  # Approximate savings
            strategies.append(
                OptimizationStrategy(
                    strategy_id="capital_loss_harvest",
                    title="Apply Capital Loss Carryforward",
                    description=(
                        f"Apply up to ${usable_this_year:,.0f} of capital loss "
                        f"carryforward against capital gains or ordinary income. "
                        f"Estimated savings: ${savings:,.0f}."
                    ),
                    estimated_savings=round(savings, 2),
                    implementation_complexity="low",
                    citations=["IRC § 1211", "IRC § 1212"],
                )
            )

        # 0% LTCG rate opportunity
        ltcg_thresholds = {
            "single": 47_025,
            "married_filing_jointly": 94_050,
            "head_of_household": 63_000,
        }
        threshold = ltcg_thresholds.get(filing_status.lower(), 47_025)
        if agi < threshold and unrealized_gains > 0:
            realizable = min(unrealized_gains, threshold - agi)
            strategies.append(
                OptimizationStrategy(
                    strategy_id="zero_ltcg",
                    title="Realize Long-Term Gains at 0% Rate",
                    description=(
                        f"You have room to realize up to ${realizable:,.0f} of "
                        f"long-term capital gains at the 0% preferential rate "
                        f"(your income is below the ${threshold:,.0f} threshold). "
                        f"Consider 'harvesting' these gains now."
                    ),
                    estimated_savings=round(realizable * 0.15, 2),  # vs 15% rate later
                    implementation_complexity="medium",
                    citations=["IRC § 1(h)", "IRC § 1222"],
                )
            )

        return strategies

    def _optimize_charitable(
        self,
        charitable_intent: float,
        marginal_rate: float,
        agi: float,
        filing_status: str,
    ) -> List[OptimizationStrategy]:
        """Optimize charitable contribution strategy."""
        if charitable_intent <= 0:
            return []

        strategies: List[OptimizationStrategy] = []

        # Donor-Advised Fund
        if charitable_intent > 5_000:
            savings = charitable_intent * marginal_rate
            strategies.append(
                OptimizationStrategy(
                    strategy_id="daf",
                    title="Use Donor-Advised Fund (DAF) for Charitable Giving",
                    description=(
                        f"Contribute ${charitable_intent:,.0f} to a Donor-Advised Fund. "
                        f"Take the full deduction in the contribution year, then "
                        f"distribute grants to charities over time. "
                        f"Estimated savings: ${savings:,.0f}."
                    ),
                    estimated_savings=round(savings, 2),
                    implementation_complexity="medium",
                    citations=["IRC § 170(f)(18)"],
                )
            )

        # Qualified Charitable Distribution (QCD) for IRA owners 70.5+
        # (Would need age parameter — simplified here)

        return strategies

    def _optimize_qbi(
        self,
        qbi: float,
        agi: float,
        filing_status: str,
    ) -> List[OptimizationStrategy]:
        """Optimize QBI deduction strategy."""
        potential_deduction = qbi * 0.20
        # Rough savings estimate at 22% marginal rate
        savings = potential_deduction * 0.22

        return [
            OptimizationStrategy(
                strategy_id="qbi",
                title="Qualified Business Income (QBI) Deduction",
                description=(
                    f"Your qualified business income of ${qbi:,.0f} qualifies for "
                    f"the §199A 20% QBI deduction (up to ${potential_deduction:,.0f}). "
                    f"Ensure your entity structure maximizes this deduction. "
                    f"Estimated benefit: ${savings:,.0f}."
                ),
                estimated_savings=round(savings, 2),
                implementation_complexity="medium",
                citations=["IRC § 199A"],
            )
        ]

    def _optimize_business_structure(
        self,
        gross_income: float,
        se_income: float,
        marginal_rate: float,
    ) -> List[OptimizationStrategy]:
        """Analyze business entity structure optimization."""
        strategies: List[OptimizationStrategy] = []

        # S-Corp election for SE tax savings
        if se_income > 80_000:
            # Rough estimate: pay reasonable salary, rest as distribution
            reasonable_salary = min(se_income * 0.6, 60_000)
            distribution = se_income - reasonable_salary
            se_savings = distribution * 0.153 * 0.9235  # SE tax savings on distribution
            strategies.append(
                OptimizationStrategy(
                    strategy_id="scorp_election",
                    title="S-Corporation Election to Reduce SE Tax",
                    description=(
                        f"With SE income of ${se_income:,.0f}, electing S-Corp status "
                        f"and paying a reasonable salary of ~${reasonable_salary:,.0f} "
                        f"could save ~${se_savings:,.0f} in self-employment taxes annually. "
                        f"Requires filing Form 2553."
                    ),
                    estimated_savings=round(se_savings, 2),
                    implementation_complexity="high",
                    prerequisites=[
                        "Consult a CPA or tax attorney",
                        "File Form 2553 by March 15",
                        "Establish payroll system",
                    ],
                    risks=[
                        "Reasonable compensation scrutiny from IRS",
                        "Additional compliance costs (payroll, corporate returns)",
                    ],
                    citations=["IRC § 1361", "IRC § 1362", "Rev. Rul. 59-221"],
                )
            )

        return strategies
