"""Database models for Prometheus.

The persistent schema keeps investment, ledger, ownership, Deal Room and
secondary-market state. Predictive liquidity outputs are computed from current
market state by the isolated liquidity engine instead of being persisted as
opaque database fields.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = INSTANCE_DIR / "prometheus.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
DATABASE_URL = os.getenv("PROMETHEUS_DATABASE_URL", DEFAULT_DATABASE_URL)

engine_options = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    """A prototype investor account."""

    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    kyc_status = Column(String(30), nullable=False, default="not_started")
    risk_profile = Column(String(30), nullable=False, default="Balanced")
    failed_login_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    wallet = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    holdings = relationship(
        "Holding",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    selling_listings = relationship(
        "SecondaryListing",
        foreign_keys="SecondaryListing.seller_id",
        back_populates="seller",
    )
    purchased_listings = relationship(
        "SecondaryListing",
        foreign_keys="SecondaryListing.buyer_id",
        back_populates="buyer",
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Deal(Base):
    """A shared private-market deal available on the primary marketplace."""

    __tablename__ = "deal"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(120), nullable=False)
    sector = Column(String(60), nullable=False)
    type = Column(String(60), nullable=False)
    blurb = Column(Text, nullable=False)
    total_raise = Column(Float, nullable=False)
    funded = Column(Float, nullable=False, default=0)
    unit_price = Column(Float, nullable=False)
    risk = Column(String(10), nullable=False)
    lock_in = Column(String(60), nullable=False)
    lock_in_months = Column(Integer, nullable=False, default=24)
    projected = Column(String(80), nullable=False)

    # Deal Room fields introduced before V6.
    geography = Column(String(120), nullable=False, default="South Africa")
    issuer = Column(String(160), nullable=False, default="Prometheus Demo Issuer")
    investment_thesis = Column(Text, nullable=False, default="")
    use_of_funds = Column(Text, nullable=False, default="")
    key_risks = Column(Text, nullable=False, default="")
    key_documents = Column(Text, nullable=False, default="")
    base_return_pct = Column(Float, nullable=False, default=12.0)
    base_horizon_months = Column(Integer, nullable=False, default=36)
    income_style = Column(String(20), nullable=False, default="growth")

    milestones = relationship(
        "DealMilestone",
        back_populates="deal",
        cascade="all, delete-orphan",
        order_by="DealMilestone.sequence",
    )

    @property
    def funded_pct(self):
        if self.total_raise <= 0:
            return 0.0
        return min(100.0, (self.funded / self.total_raise) * 100)

    @property
    def remaining(self):
        return max(0.0, self.total_raise - self.funded)


class DealMilestone(Base):
    """Illustrative capital journey milestone shown in the Deal Room."""

    __tablename__ = "deal_milestone"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deal.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    title = Column(String(140), nullable=False)
    description = Column(Text, nullable=False)
    phase = Column(String(30), nullable=False, default="upcoming")
    timing_label = Column(String(80), nullable=False)

    deal = relationship("Deal", back_populates="milestones")


class Holding(Base):
    """Available units of a deal owned by one investor."""

    __tablename__ = "holding"
    __table_args__ = (
        UniqueConstraint("user_id", "deal_id", name="uq_holding_user_deal"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    deal_id = Column(Integer, ForeignKey("deal.id"), nullable=False, index=True)
    units = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="holdings")
    deal = relationship("Deal")

    @property
    def cost_basis(self):
        return self.units * self.deal.unit_price

    @property
    def ownership_pct(self):
        if self.deal.total_raise <= 0:
            return 0.0
        return (self.units * self.deal.unit_price / self.deal.total_raise) * 100


class Wallet(Base):
    """One ZAR wallet account owned by one user."""

    __tablename__ = "wallet"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, unique=True, index=True)
    currency = Column(String(3), nullable=False, default="ZAR")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="wallet")
    transactions = relationship(
        "WalletTransaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )


class WalletTransaction(Base):
    """One immutable money movement in a user's wallet ledger."""

    __tablename__ = "wallet_transaction"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallet.id"), nullable=False, index=True)
    transaction_type = Column(String(30), nullable=False, index=True)
    description = Column(String(180), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), nullable=False, default="completed", index=True)
    reference = Column(String(80), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    wallet = relationship("Wallet", back_populates="transactions")


class SecondaryListing(Base):
    """Units reserved by a real prototype user for resale."""

    __tablename__ = "secondary_listing"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("deal.id"), nullable=False, index=True)
    units = Column(Integer, nullable=False)
    price_per_unit = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    seller = relationship(
        "User",
        foreign_keys=[seller_id],
        back_populates="selling_listings",
    )
    buyer = relationship(
        "User",
        foreign_keys=[buyer_id],
        back_populates="purchased_listings",
    )
    deal = relationship("Deal")
    trade = relationship("Trade", back_populates="listing", uselist=False)

    @property
    def total_value(self):
        return float(self.units * self.price_per_unit)


class IndicativeBid(Base):
    """Non-binding simulated demand used to present a two-sided order book."""

    __tablename__ = "indicative_bid"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deal.id"), nullable=False, index=True)
    bidder_label = Column(String(80), nullable=False)
    units = Column(Integer, nullable=False)
    price_per_unit = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    deal = relationship("Deal")


class Trade(Base):
    """Completed secondary-market transfer and settlement audit record."""

    __tablename__ = "trade"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("secondary_listing.id"), nullable=False, unique=True)
    deal_id = Column(Integer, ForeignKey("deal.id"), nullable=False, index=True)
    seller_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    units = Column(Integer, nullable=False)
    price_per_unit = Column(Numeric(14, 2), nullable=False)
    gross_amount = Column(Numeric(14, 2), nullable=False)
    platform_fee = Column(Numeric(14, 2), nullable=False, default=0)
    net_to_seller = Column(Numeric(14, 2), nullable=False)
    reference = Column(String(80), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="completed")
    executed_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    listing = relationship("SecondaryListing", back_populates="trade")
    deal = relationship("Deal")
    seller = relationship("User", foreign_keys=[seller_id])
    buyer = relationship("User", foreign_keys=[buyer_id])


class Notification(Base):
    """In-app notification owned by a single user."""

    __tablename__ = "notification"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    category = Column(String(30), nullable=False, index=True)
    title = Column(String(140), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    reference = Column(String(80), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = relationship("User", back_populates="notifications")


class AuditEvent(Base):
    """Security and business audit trail for prototype accountability."""

    __tablename__ = "audit_event"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="info")
    reference = Column(String(80), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = relationship("User", back_populates="audit_events")
