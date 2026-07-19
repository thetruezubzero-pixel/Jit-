"""Accounting module for tax calculation and financial analysis."""

from jit.accounting.tax_calculator import TaxCalculator, TaxResult
from jit.accounting.income_processor import IncomeProcessor, IncomeRecord
from jit.accounting.deduction_optimizer import DeductionOptimizer, DeductionResult
from jit.accounting.amt_calculator import AMTCalculator, AMTResult
from jit.accounting.quarterly_estimator import QuarterlyEstimator, QuarterlyPayment

__all__ = [
    "TaxCalculator",
    "TaxResult",
    "IncomeProcessor",
    "IncomeRecord",
    "DeductionOptimizer",
    "DeductionResult",
    "AMTCalculator",
    "AMTResult",
    "QuarterlyEstimator",
    "QuarterlyPayment",
]
