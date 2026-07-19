"""
SQLAlchemy database models for the Jit system.

Defines ORM models for users, tax cases, legal cases, income entries,
and compliance checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class User(Base):
    """Registered user of the Jit system."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tax_cases: Mapped[list["TaxCase"]] = relationship("TaxCase", back_populates="user")
    legal_cases: Mapped[list["LegalCase"]] = relationship("LegalCase", back_populates="user")
    income_entries: Mapped[list["IncomeEntry"]] = relationship(
        "IncomeEntry", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User(username={self.username!r}, email={self.email!r})>"


class TaxCase(Base):
    """A stored tax calculation case."""

    __tablename__ = "tax_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    filing_status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Income
    gross_income: Mapped[float] = mapped_column(Float, default=0.0)
    agi: Mapped[float] = mapped_column(Float, default=0.0)
    taxable_income: Mapped[float] = mapped_column(Float, default=0.0)

    # Tax results
    federal_tax: Mapped[float] = mapped_column(Float, default=0.0)
    state_tax: Mapped[float] = mapped_column(Float, default=0.0)
    total_tax: Mapped[float] = mapped_column(Float, default=0.0)
    effective_rate: Mapped[float] = mapped_column(Float, default=0.0)
    marginal_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # State
    state_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="tax_cases")
    income_entries: Mapped[list["IncomeEntry"]] = relationship(
        "IncomeEntry", back_populates="tax_case"
    )

    def __repr__(self) -> str:
        return f"<TaxCase(user_id={self.user_id!r}, year={self.tax_year}, total_tax={self.total_tax})>"


class LegalCase(Base):
    """A stored legal analysis case."""

    __tablename__ = "legal_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="legal_cases")

    def __repr__(self) -> str:
        return f"<LegalCase(title={self.title!r}, risk_score={self.risk_score})>"


class IncomeEntry(Base):
    """An individual income record linked to a user and optionally a tax case."""

    __tablename__ = "income_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    tax_case_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tax_cases.id"), nullable=True
    )

    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    income_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    withheld_federal: Mapped[float] = mapped_column(Float, default=0.0)
    withheld_state: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="income_entries")
    tax_case: Mapped[Optional["TaxCase"]] = relationship("TaxCase", back_populates="income_entries")

    def __repr__(self) -> str:
        return f"<IncomeEntry(type={self.income_type!r}, amount={self.amount})>"


class ComplianceCheck(Base):
    """Audit log of compliance checks performed."""

    __tablename__ = "compliance_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    tax_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    overall_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    compliance_score: Mapped[float] = mapped_column(Float, default=1.0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<ComplianceCheck(risk={self.overall_risk!r}, score={self.compliance_score})>"
        )
