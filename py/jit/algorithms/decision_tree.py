"""
Recursive decision tree engine for multi-level financial and legal analysis.

Builds and evaluates decision trees that recursively analyze nested
financial scenarios, entity structures, and legal situations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class NodeType(str, Enum):
    """Type of decision node."""

    CONDITION = "condition"  # Boolean test — branches to yes/no children
    CALCULATION = "calculation"  # Computes a value
    RECOMMENDATION = "recommendation"  # Terminal recommendation
    LOOKUP = "lookup"  # Table/threshold lookup
    AGGREGATION = "aggregation"  # Combines multiple children


@dataclass
class NodeContext:
    """
    Execution context passed through the decision tree.

    Carries the working data set and intermediate results as the
    tree recursively evaluates each node.
    """

    data: Dict[str, Any]
    results: Dict[str, Any] = field(default_factory=dict)
    path: List[str] = field(default_factory=list)  # Nodes visited
    depth: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the data context."""
        return self.data.get(key, default)

    def set_result(self, key: str, value: Any) -> None:
        """Store a result value."""
        self.results[key] = value

    def child(self, node_id: str) -> "NodeContext":
        """Create a child context for a sub-node."""
        return NodeContext(
            data=dict(self.data),
            results=dict(self.results),
            path=self.path + [node_id],
            depth=self.depth + 1,
        )


@dataclass
class DecisionResult:
    """Result of evaluating a decision tree."""

    recommendation: str
    confidence: float  # 0.0 to 1.0
    value: Optional[Any]  # Computed value (e.g., tax savings)
    path_taken: List[str]  # Node IDs visited
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    supporting_reasons: List[str] = field(default_factory=list)
    alternative_paths: List[str] = field(default_factory=list)


class DecisionNode:
    """
    A node in a recursive decision tree.

    Each node may have child nodes for 'yes', 'no', or multiple
    weighted branches, enabling recursive depth-first evaluation.
    """

    def __init__(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
        condition: Optional[Callable[[NodeContext], bool]] = None,
        calculation: Optional[Callable[[NodeContext], Any]] = None,
        recommendation: Optional[str] = None,
        confidence: float = 1.0,
        yes_child: Optional["DecisionNode"] = None,
        no_child: Optional["DecisionNode"] = None,
        children: Optional[List[Tuple["DecisionNode", float]]] = None,
        result_key: Optional[str] = None,
        max_depth: int = 50,
    ) -> None:
        """
        Initialize a decision node.

        Args:
            node_id: Unique identifier for the node.
            node_type: Type of node (condition, calculation, etc.).
            label: Human-readable label.
            condition: Callable that returns bool for CONDITION nodes.
            calculation: Callable returning computed value for CALCULATION nodes.
            recommendation: Terminal recommendation text.
            confidence: Confidence weight for this node's recommendation.
            yes_child: Child node for True/Yes branch.
            no_child: Child node for False/No branch.
            children: Weighted children for AGGREGATION nodes.
            result_key: Key to store computed result in context.
            max_depth: Maximum recursion depth (safety limit).
        """
        self.node_id = node_id
        self.node_type = node_type
        self.label = label
        self.condition = condition
        self.calculation = calculation
        self.recommendation = recommendation
        self.confidence = confidence
        self.yes_child = yes_child
        self.no_child = no_child
        self.children = children or []
        self.result_key = result_key
        self.max_depth = max_depth

    def evaluate(self, context: NodeContext) -> DecisionResult:
        """
        Recursively evaluate this node and its children.

        Args:
            context: Execution context with input data.

        Returns:
            DecisionResult with recommendation and metadata.
        """
        if context.depth > self.max_depth:
            return DecisionResult(
                recommendation="Maximum analysis depth reached.",
                confidence=0.0,
                value=None,
                path_taken=context.path + [self.node_id],
                supporting_reasons=["Recursion depth limit hit."],
            )

        child_context = context.child(self.node_id)

        if self.node_type == NodeType.RECOMMENDATION:
            return self._eval_recommendation(child_context)

        elif self.node_type == NodeType.CONDITION:
            return self._eval_condition(child_context)

        elif self.node_type == NodeType.CALCULATION:
            return self._eval_calculation(child_context)

        elif self.node_type == NodeType.AGGREGATION:
            return self._eval_aggregation(child_context)

        else:
            return DecisionResult(
                recommendation=f"Node '{self.node_id}': unsupported type {self.node_type}",
                confidence=0.5,
                value=None,
                path_taken=child_context.path,
            )

    # ------------------------------------------------------------------
    # Node evaluation methods
    # ------------------------------------------------------------------

    def _eval_recommendation(self, context: NodeContext) -> DecisionResult:
        """Evaluate a terminal recommendation node."""
        return DecisionResult(
            recommendation=self.recommendation or self.label,
            confidence=self.confidence,
            value=context.results.get(self.result_key) if self.result_key else None,
            path_taken=context.path,
            intermediate_results=context.results,
            supporting_reasons=[f"Rule: {self.label}"],
        )

    def _eval_condition(self, context: NodeContext) -> DecisionResult:
        """Evaluate a condition node and recurse into appropriate branch."""
        if self.condition is None:
            raise ValueError(f"Node '{self.node_id}' (CONDITION) has no condition callable")

        branch_taken = self.condition(context)
        next_node = self.yes_child if branch_taken else self.no_child

        if next_node is None:
            reason = f"Condition '{self.label}' evaluated to {branch_taken}; no further branch."
            return DecisionResult(
                recommendation=reason,
                confidence=self.confidence,
                value=branch_taken,
                path_taken=context.path,
                supporting_reasons=[reason],
            )

        child_result = next_node.evaluate(context)
        child_result.path_taken = [self.node_id] + child_result.path_taken
        child_result.supporting_reasons.insert(
            0,
            f"Condition '{self.label}' = {'YES' if branch_taken else 'NO'}",
        )
        return child_result

    def _eval_calculation(self, context: NodeContext) -> DecisionResult:
        """Evaluate a calculation node and optionally recurse."""
        if self.calculation is None:
            raise ValueError(f"Node '{self.node_id}' (CALCULATION) has no calculation callable")

        value = self.calculation(context)
        if self.result_key:
            context.set_result(self.result_key, value)

        # Recurse into yes_child (single-branch continuation) if available
        if self.yes_child:
            child_result = self.yes_child.evaluate(context)
            child_result.path_taken = [self.node_id] + child_result.path_taken
            child_result.intermediate_results[self.result_key or self.node_id] = value
            return child_result

        return DecisionResult(
            recommendation=f"Computed {self.label}: {value}",
            confidence=self.confidence,
            value=value,
            path_taken=context.path,
            intermediate_results={self.result_key or self.node_id: value},
            supporting_reasons=[f"Calculated {self.label} = {value}"],
        )

    def _eval_aggregation(self, context: NodeContext) -> DecisionResult:
        """Evaluate all children and aggregate weighted results."""
        if not self.children:
            return DecisionResult(
                recommendation="No children to aggregate.",
                confidence=0.0,
                value=None,
                path_taken=context.path,
            )

        sub_results: List[DecisionResult] = []
        total_weight = sum(w for _, w in self.children)

        for child_node, weight in self.children:
            sub_result = child_node.evaluate(context)
            sub_results.append(sub_result)

        # Weighted confidence aggregation
        weighted_confidence = sum(
            r.confidence * w for r, (_, w) in zip(sub_results, self.children)
        ) / max(total_weight, 1e-9)

        recommendations = [r.recommendation for r in sub_results]
        all_intermediate = {}
        for r in sub_results:
            all_intermediate.update(r.intermediate_results)

        combined_path = [self.node_id]
        for r in sub_results:
            combined_path.extend(r.path_taken)

        return DecisionResult(
            recommendation=" | ".join(recommendations),
            confidence=round(weighted_confidence, 4),
            value=all_intermediate,
            path_taken=combined_path,
            intermediate_results=all_intermediate,
            supporting_reasons=[f"Aggregated {len(sub_results)} analysis branches"],
        )


class DecisionTree:
    """
    A recursive decision tree for complex financial and legal analysis.

    Provides a builder interface for constructing trees and methods
    for evaluating them against input data.
    """

    def __init__(self, name: str, root: Optional[DecisionNode] = None) -> None:
        """
        Initialize the decision tree.

        Args:
            name: Name/description of this decision tree.
            root: Root node of the tree.
        """
        self.name = name
        self.root = root

    def evaluate(self, data: Dict[str, Any]) -> DecisionResult:
        """
        Evaluate the decision tree against the provided data.

        Args:
            data: Input data dictionary (financial facts, legal factors, etc.).

        Returns:
            DecisionResult with recommendation and analysis path.

        Raises:
            ValueError: If the tree has no root node.
        """
        if self.root is None:
            raise ValueError(f"Decision tree '{self.name}' has no root node")

        context = NodeContext(data=data)
        result = self.root.evaluate(context)
        return result

    @staticmethod
    def build_filing_status_tree() -> "DecisionTree":
        """
        Build a decision tree that recommends optimal IRS filing status.

        Returns a pre-built filing status recommendation tree.
        """
        # Terminal nodes
        single_rec = DecisionNode(
            "rec_single",
            NodeType.RECOMMENDATION,
            "File as SINGLE",
            recommendation=(
                "File as Single. You are not married and do not qualify as head of household. "
                "Standard deduction: $14,600."
            ),
            confidence=0.95,
        )

        mfj_rec = DecisionNode(
            "rec_mfj",
            NodeType.RECOMMENDATION,
            "File as MARRIED FILING JOINTLY (MFJ)",
            recommendation=(
                "File as Married Filing Jointly. MFJ typically results in the lowest "
                "combined tax for most married couples. Standard deduction: $29,200."
            ),
            confidence=0.90,
        )

        mfs_rec = DecisionNode(
            "rec_mfs",
            NodeType.RECOMMENDATION,
            "File as MARRIED FILING SEPARATELY (MFS)",
            recommendation=(
                "File as Married Filing Separately. Consider MFS if your spouse has "
                "significant deductions or liabilities, but note this disallows many "
                "credits and deductions. Standard deduction: $14,600."
            ),
            confidence=0.75,
        )

        hoh_rec = DecisionNode(
            "rec_hoh",
            NodeType.RECOMMENDATION,
            "File as HEAD OF HOUSEHOLD (HOH)",
            recommendation=(
                "File as Head of Household. You are unmarried and pay more than half "
                "of the household costs for a qualifying person. Standard deduction: $21,900. "
                "Lower tax rates than Single status."
            ),
            confidence=0.92,
        )

        qss_rec = DecisionNode(
            "rec_qss",
            NodeType.RECOMMENDATION,
            "File as QUALIFYING SURVIVING SPOUSE (QSS)",
            recommendation=(
                "File as Qualifying Surviving Spouse. Your spouse passed away within "
                "the last 2 years and you have a dependent child. You qualify for "
                "MFJ rates and standard deduction ($29,200)."
            ),
            confidence=0.95,
        )

        # Condition: married vs. not
        mfs_or_mfj = DecisionNode(
            "mfs_vs_mfj",
            NodeType.CONDITION,
            "Is filing separately advantageous (separate debts/liabilities)?",
            condition=lambda ctx: ctx.get("prefer_filing_separately", False),
            yes_child=mfs_rec,
            no_child=mfj_rec,
        )

        has_qualifying_person = DecisionNode(
            "has_qualifying_person",
            NodeType.CONDITION,
            "Does a qualifying person live with you for more than half the year?",
            condition=lambda ctx: ctx.get("has_qualifying_dependent", False),
            yes_child=hoh_rec,
            no_child=single_rec,
        )

        qss_check = DecisionNode(
            "qss_check",
            NodeType.CONDITION,
            "Did your spouse pass away in the last 2 years and do you have a dependent child?",
            condition=lambda ctx: ctx.get("is_qualifying_surviving_spouse", False),
            yes_child=qss_rec,
            no_child=has_qualifying_person,
        )

        married_check = DecisionNode(
            "married_check",
            NodeType.CONDITION,
            "Are you married (or considered married) on December 31?",
            condition=lambda ctx: ctx.get("is_married", False),
            yes_child=mfs_or_mfj,
            no_child=qss_check,
        )

        return DecisionTree("Filing Status Recommender", root=married_check)

    @staticmethod
    def build_deduction_method_tree() -> "DecisionTree":
        """
        Build a decision tree to choose between standard and itemized deductions.

        Returns a pre-built deduction method selection tree.
        """
        itemized_rec = DecisionNode(
            "rec_itemize",
            NodeType.RECOMMENDATION,
            "ITEMIZE deductions (Schedule A)",
            recommendation=(
                "Itemize your deductions. Your itemized deductions exceed the standard "
                "deduction, resulting in a lower taxable income and reduced tax liability."
            ),
            confidence=0.95,
        )

        standard_rec = DecisionNode(
            "rec_standard",
            NodeType.RECOMMENDATION,
            "Take the STANDARD deduction",
            recommendation=(
                "Take the standard deduction. Your itemized deductions do not exceed "
                "the standard deduction for your filing status. No Schedule A required."
            ),
            confidence=0.95,
        )

        itemized_vs_standard = DecisionNode(
            "itemized_vs_standard",
            NodeType.CONDITION,
            "Do itemized deductions exceed the standard deduction?",
            condition=lambda ctx: (
                ctx.get("itemized_deductions", 0) > ctx.get("standard_deduction", 14_600)
            ),
            yes_child=itemized_rec,
            no_child=standard_rec,
        )

        return DecisionTree("Deduction Method Selector", root=itemized_vs_standard)
