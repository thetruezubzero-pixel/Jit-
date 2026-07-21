"""
Unit tests for recursive algorithms module.
"""

import pytest
from jit.algorithms.decision_tree import DecisionTree, DecisionNode, NodeType
from jit.algorithms.optimizer import TaxOptimizer
from jit.algorithms.risk_assessor import RiskAssessor

# -----------------------------------------------------------------------
# DecisionTree tests
# -----------------------------------------------------------------------


class TestDecisionTree:
    def test_filing_status_single(self):
        """Unmarried, no qualifying dependent → Single."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": False,
                "prefer_filing_separately": False,
                "is_qualifying_surviving_spouse": False,
                "has_qualifying_dependent": False,
            }
        )
        assert "SINGLE" in result.recommendation.upper()

    def test_filing_status_mfj(self):
        """Married, no preference for separate → MFJ."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": True,
                "prefer_filing_separately": False,
            }
        )
        assert "MARRIED FILING JOINTLY" in result.recommendation.upper()

    def test_filing_status_mfs(self):
        """Married, prefer filing separately → MFS."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": True,
                "prefer_filing_separately": True,
            }
        )
        assert "SEPARATELY" in result.recommendation.upper()

    def test_filing_status_hoh(self):
        """Unmarried with qualifying dependent → HOH."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": False,
                "prefer_filing_separately": False,
                "is_qualifying_surviving_spouse": False,
                "has_qualifying_dependent": True,
            }
        )
        assert "HEAD OF HOUSEHOLD" in result.recommendation.upper()

    def test_filing_status_qss(self):
        """Qualifying surviving spouse status."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": False,
                "is_qualifying_surviving_spouse": True,
                "has_qualifying_dependent": False,
            }
        )
        assert "SURVIVING SPOUSE" in result.recommendation.upper()

    def test_deduction_method_itemized(self):
        """Itemized deductions > standard should recommend itemizing."""
        tree = DecisionTree.build_deduction_method_tree()
        result = tree.evaluate(
            {
                "itemized_deductions": 25_000,
                "standard_deduction": 14_600,
            }
        )
        assert "ITEMIZE" in result.recommendation.upper()

    def test_deduction_method_standard(self):
        """Itemized deductions < standard should recommend standard."""
        tree = DecisionTree.build_deduction_method_tree()
        result = tree.evaluate(
            {
                "itemized_deductions": 5_000,
                "standard_deduction": 14_600,
            }
        )
        assert "STANDARD" in result.recommendation.upper()

    def test_confidence_matches_leaf_node(self):
        """Condition nodes pass through the confidence of the leaf they route to."""
        tree = DecisionTree.build_filing_status_tree()
        # married_check(True) -> mfs_or_mfj(prefer_separately=False) -> mfj_rec
        mfj_result = tree.evaluate({"is_married": True, "prefer_filing_separately": False})
        assert mfj_result.confidence == 0.90
        # married_check(False) -> qss_check(False) -> has_qualifying_person(True) -> hoh_rec
        hoh_result = tree.evaluate(
            {
                "is_married": False,
                "has_qualifying_dependent": True,
                "is_qualifying_surviving_spouse": False,
            }
        )
        assert hoh_result.confidence == 0.92

    def test_path_non_empty(self):
        """Path taken should include at least one node."""
        tree = DecisionTree.build_filing_status_tree()
        result = tree.evaluate(
            {
                "is_married": False,
                "has_qualifying_dependent": False,
                "is_qualifying_surviving_spouse": False,
            }
        )
        assert len(result.path_taken) > 0

    def test_no_root_raises(self):
        """Evaluating a tree with no root should raise ValueError."""
        tree = DecisionTree("Empty Tree")
        with pytest.raises(ValueError):
            tree.evaluate({})

    def test_max_depth_respected(self):
        """Recursion depth limit should prevent infinite loops."""
        # Build a deeply nested chain (depth > max_depth)
        leaf = DecisionNode(
            "leaf", NodeType.RECOMMENDATION, "Leaf", recommendation="Done", max_depth=5
        )
        node = leaf
        for i in range(10):
            node = DecisionNode(
                f"cond_{i}",
                NodeType.CONDITION,
                f"Condition {i}",
                condition=lambda ctx: True,
                yes_child=node,
                max_depth=5,
            )
        tree = DecisionTree("Deep Tree", root=node)
        result = tree.evaluate({})
        # Should complete without recursion error
        assert result is not None

    def test_custom_calculation_node(self):
        """Calculation node should compute and store values."""
        calc_node = DecisionNode(
            "compute_tax",
            NodeType.CALCULATION,
            "Compute Estimated Tax",
            calculation=lambda ctx: ctx.get("income", 0) * 0.25,
            result_key="estimated_tax",
        )
        tree = DecisionTree("Tax Calculator", root=calc_node)
        result = tree.evaluate({"income": 100_000})
        assert result.value == 25_000.0


# -----------------------------------------------------------------------
# TaxOptimizer tests
# -----------------------------------------------------------------------


class TestTaxOptimizer:
    def test_basic_optimization(self):
        """Should return optimization strategies for a typical scenario."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=100_000,
            current_tax=22_000,
            marginal_rate=0.22,
            filing_status="single",
            age=40,
            has_401k_access=True,
            current_401k_contribution=5_000,
        )
        assert len(result.strategies) > 0
        assert result.total_savings >= 0

    def test_401k_strategy_when_under_limit(self):
        """401(k) strategy should appear when contribution is below limit."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=100_000,
            current_tax=22_000,
            marginal_rate=0.22,
            has_401k_access=True,
            current_401k_contribution=5_000,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "retire_401k" in ids

    def test_sep_strategy_for_se_income(self):
        """SEP-IRA strategy should appear for self-employment income."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=120_000,
            current_tax=25_000,
            marginal_rate=0.24,
            self_employment_income=120_000,
            current_sep_contribution=0,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "retire_sep" in ids

    def test_hsa_strategy_for_eligible_plan(self):
        """HSA strategy should appear for HDHP-enrolled taxpayer."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=80_000,
            current_tax=16_000,
            marginal_rate=0.22,
            has_hsa_eligible_plan=True,
            current_hsa_contribution=0,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "hsa_max" in ids

    def test_scorp_strategy_for_high_se(self):
        """S-Corp strategy should appear for high SE income business owners."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=200_000,
            current_tax=45_000,
            marginal_rate=0.32,
            self_employment_income=200_000,
            is_business_owner=True,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "scorp_election" in ids

    def test_backdoor_roth_strategy_above_phaseout(self):
        """Backdoor Roth should appear once income exceeds the direct-contribution phase-out."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=200_000,
            current_tax=45_000,
            marginal_rate=0.32,
            filing_status="single",
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "backdoor_roth" in ids
        strategy = next(s for s in result.strategies if s.strategy_id == "backdoor_roth")
        # No current-year deduction either way — the benefit is future tax-free growth.
        assert strategy.estimated_savings == 0.0

    def test_no_backdoor_roth_below_phaseout(self):
        """Backdoor Roth should not appear for a filer still eligible to contribute directly."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=80_000,
            current_tax=12_000,
            marginal_rate=0.22,
            filing_status="single",
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "backdoor_roth" not in ids

    def test_salt_cap_workaround_for_business_owner(self):
        """PTET SALT cap workaround should appear for a business owner with state tax."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=300_000,
            current_tax=70_000,
            marginal_rate=0.35,
            is_business_owner=True,
            expected_state_tax=20_000,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "salt_cap_ptet" in ids
        strategy = next(s for s in result.strategies if s.strategy_id == "salt_cap_ptet")
        assert strategy.estimated_savings == pytest.approx(20_000 * 0.35)

    def test_no_salt_cap_workaround_without_business(self):
        """PTET workaround should not appear for a non-business-owner."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=300_000,
            current_tax=70_000,
            marginal_rate=0.35,
            is_business_owner=False,
            expected_state_tax=20_000,
        )
        ids = [s.strategy_id for s in result.strategies]
        assert "salt_cap_ptet" not in ids

    def test_optimized_tax_less_than_current(self):
        """Optimized tax should be less than or equal to current tax."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=120_000,
            current_tax=28_000,
            marginal_rate=0.24,
            has_401k_access=True,
            has_hsa_eligible_plan=True,
        )
        assert result.optimized_estimated_tax <= result.current_estimated_tax

    def test_strategies_sorted_by_savings(self):
        """Strategies should be sorted highest savings first."""
        optimizer = TaxOptimizer()
        result = optimizer.optimize(
            gross_income=200_000,
            current_tax=50_000,
            marginal_rate=0.32,
            has_401k_access=True,
            self_employment_income=100_000,
            has_hsa_eligible_plan=True,
        )
        if len(result.strategies) > 1:
            for i in range(len(result.strategies) - 1):
                assert (
                    result.strategies[i].estimated_savings
                    >= result.strategies[i + 1].estimated_savings
                )


# -----------------------------------------------------------------------
# RiskAssessor tests
# -----------------------------------------------------------------------


class TestRiskAssessor:
    def test_low_risk_clean_return(self):
        """Clean return should have low overall risk."""
        assessor = RiskAssessor()
        profile = assessor.assess_individual_tax(agi=75_000)
        assert profile.overall_risk_rating in ("Low", "Moderate")
        assert profile.estimated_audit_probability < 0.05

    def test_schedule_c_increases_risk(self):
        """Schedule C should increase audit risk."""
        assessor = RiskAssessor()
        clean = assessor.assess_individual_tax(agi=75_000)
        with_sch_c = assessor.assess_individual_tax(
            agi=75_000, has_schedule_c=True, schedule_c_income=75_000
        )
        assert with_sch_c.audit_risk_score > clean.audit_risk_score

    def test_unreported_income_critical(self):
        """Unreported income should push penalty risk very high."""
        assessor = RiskAssessor()
        profile = assessor.assess_individual_tax(agi=100_000, has_unreported_income=True)
        penalty_factors = [
            f for f in profile.factors if f.factor_id == "unreported_income" and f.is_present
        ]
        assert len(penalty_factors) == 1
        assert penalty_factors[0].risk_contribution == 1.0

    def test_foreign_income_compliance_risk(self):
        """Foreign income should add compliance risk factor."""
        assessor = RiskAssessor()
        profile = assessor.assess_individual_tax(agi=200_000, has_foreign_income=True)
        foreign_factors = [f for f in profile.present_factors if f.factor_id == "foreign_income"]
        assert len(foreign_factors) > 0

    def test_high_agi_higher_base_audit_rate(self):
        """High AGI should have higher audit probability than low AGI."""
        assessor = RiskAssessor()
        low_income = assessor.assess_individual_tax(agi=30_000)
        high_income = assessor.assess_individual_tax(agi=2_000_000)
        assert high_income.estimated_audit_probability > low_income.estimated_audit_probability

    def test_recommendations_always_returned(self):
        """Recommendations should always be present in the profile."""
        assessor = RiskAssessor()
        profile = assessor.assess_individual_tax(agi=50_000)
        assert isinstance(profile.recommendations, list)
        assert len(profile.recommendations) > 0

    def test_risk_scores_in_valid_range(self):
        """All risk scores should be between 0 and 1."""
        assessor = RiskAssessor()
        profile = assessor.assess_individual_tax(
            agi=150_000,
            has_schedule_c=True,
            has_foreign_income=True,
            has_crypto_transactions=True,
            claimed_home_office=True,
            large_charitable_pct=0.40,
        )
        # Audit-category factors present: schedule_c (0.35) + home_office
        # (0.20) + large_charitable (0.25, since 40% > 30% threshold) = 0.80
        assert profile.audit_risk_score == 0.8
        # No penalty-category factors triggered (no unreported income,
        # substantial understatement, or late filing)
        assert profile.penalty_risk_score == 0.0
        # overall = audit*0.4 + penalty*0.35 + compliance*0.25
        # compliance = foreign_income (0.40) + crypto (0.25) = 0.65
        # = 0.8*0.4 + 0.0*0.35 + 0.65*0.25 = 0.32 + 0 + 0.1625 = 0.4825
        assert profile.overall_risk_score == 0.483
