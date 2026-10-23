"""Business logic for Prometheus One — final V7 hackathon build.

Flet calls this module instead of touching SQLAlchemy directly. It preserves the
proven investing, wallet-ledger, ownership and atomic secondary-market flows,
alongside notifications, audit/security controls,
Deal Rooms, a transparent Scenario Lab, Portfolio Intelligence, Capital
Timelines and an order-book view with indicative bids.

Prometheus One adds an explainable Liquidity Intelligence layer while preserving
the stable V1–V6 transaction, ownership, wallet and secondary-market rules.
"""

from dataclasses import dataclass
from datetime import timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from uuid import uuid4

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from database import session_scope
from models import (
    AuditEvent,
    Deal,
    Holding,
    IndicativeBid,
    Notification,
    SecondaryListing,
    Trade,
    User,
    Wallet,
    WalletTransaction,
    utc_now,
)
from security import hash_password, verify_password
from liquidity.engine import (
    LiquidityFeatures,
    LiquidityForecast,
    PortfolioLiquiditySnapshot,
    backtest_model,
    forecast_liquidity,
    portfolio_liquidity_snapshot,
)
from liquidity.model_card import MODEL_CARD


MONEY = Decimal("0.01")
ALLOWED_RISK_PROFILES = {"Conservative", "Balanced", "Growth"}
ALLOWED_KYC_STATUSES = {"not_started", "pending", "verified"}
SECONDARY_PLATFORM_FEE_RATE = Decimal("0.01")
MAX_WALLET_MOVEMENT = Decimal("1000000.00")
MAX_LISTING_PRICE = Decimal("10000000.00")
MAX_UNITS_PER_ACTION = 100_000
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_MINUTES = 5
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class PrometheusServiceError(Exception):
    """A user-safe business rule failure."""


@dataclass(frozen=True)
class UserProfile:
    id: int
    name: str
    email: str
    kyc_status: str
    risk_profile: str


@dataclass(frozen=True)
class InvestmentResult:
    user_id: int
    deal_id: int
    deal_name: str
    units: int
    cost: float
    wallet_balance: float
    transaction_reference: str


@dataclass(frozen=True)
class WalletMovementResult:
    user_id: int
    amount: float
    wallet_balance: float
    transaction_reference: str


@dataclass(frozen=True)
class ListingResult:
    listing_id: int
    seller_id: int
    deal_id: int
    deal_name: str
    units: int
    price_per_unit: float
    total_value: float


@dataclass(frozen=True)
class CancellationResult:
    listing_id: int
    restored_units: int
    deal_name: str


@dataclass(frozen=True)
class TradeResult:
    trade_id: int
    listing_id: int
    reference: str
    deal_name: str
    seller_id: int
    buyer_id: int
    units: int
    price_per_unit: float
    gross_amount: float
    platform_fee: float
    net_to_seller: float
    buyer_wallet_balance: float
    seller_wallet_balance: float


@dataclass(frozen=True)
class ScenarioResult:
    deal_name: str
    investment_amount: float
    annual_return_pct: float
    horizon_months: int
    exit_delay_months: int
    valuation_shock_pct: float
    projected_value: float
    projected_gain: float
    disclaimer: str


@dataclass(frozen=True)
class PortfolioIntelligence:
    score: int
    total_value: float
    holding_count: int
    sector_count: int
    largest_sector: str
    largest_sector_pct: float
    high_risk_pct: float
    long_lock_in_pct: float
    income_exposure_pct: float
    status: str
    recommendations: tuple[str, ...]


@dataclass(frozen=True)
class SuitabilitySnapshot:
    deal_id: int
    deal_name: str
    risk_profile: str
    deal_risk: str
    risk_fit: str
    current_sector_pct: float
    sector_after_one_unit_pct: float
    lock_in_months: int
    summary: str
    cautions: tuple[str, ...]


@dataclass(frozen=True)
class OrderLevel:
    side: str
    price: float
    units: int
    orders: int


@dataclass(frozen=True)
class OrderBookSnapshot:
    deal_id: int
    deal_name: str
    indicative_value: float
    best_bid: float | None
    best_ask: float | None
    bid_levels: tuple[OrderLevel, ...]
    ask_levels: tuple[OrderLevel, ...]
    recent_traded_units: int


@dataclass(frozen=True)
class MarketRevision:
    active_listings: int
    active_bids: int
    completed_trades: int
    newest_listing_id: int
    newest_trade_id: int


@dataclass(frozen=True)
class LiquiditySnapshot:
    deal_id: int
    deal_name: str
    deal_code: str
    holding_units: int
    reference_price: float
    proposed_price: float
    best_bid: float | None
    best_ask: float | None
    visible_bid_units: int
    visible_ask_units: int
    market_observations: int
    forecast: LiquidityForecast


@dataclass(frozen=True)
class ExitGoalResult:
    deal_id: int
    deal_name: str
    target_days: int
    suggested_price_low: float
    suggested_price_high: float
    estimated_probability: float
    note: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise PrometheusServiceError("Enter a valid amount.")


def _normalise_email(email: str) -> str:
    value = (email or "").strip().lower()
    if len(value) > 180 or not EMAIL_RE.fullmatch(value):
        raise PrometheusServiceError("Enter a valid email address.")
    return value


def _profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        name=user.name,
        email=user.email,
        kyc_status=user.kyc_status,
        risk_profile=user.risk_profile,
    )


def _require_user(session, user_id: int) -> User:
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise PrometheusServiceError("User account was not found.")
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise PrometheusServiceError("User account was not found.")
    return user


def _require_verified_user(session, user_id: int) -> User:
    user = _require_user(session, user_id)
    if user.kyc_status != "verified":
        raise PrometheusServiceError(
            "Complete the simulated KYC step before using investment markets."
        )
    return user


def _require_wallet(session, user_id: int) -> Wallet:
    wallet = session.query(Wallet).filter(Wallet.user_id == int(user_id)).first()
    if wallet is None:
        raise PrometheusServiceError("Wallet is not initialised for this user.")
    return wallet


def _wallet_balance(session, wallet_id: int) -> Decimal:
    total = (
        session.query(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .filter(
            WalletTransaction.wallet_id == wallet_id,
            WalletTransaction.status == "completed",
        )
        .scalar()
    )
    return _money(total)


def _new_reference(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _notify(session, user_id: int, category: str, title: str, message: str, reference: str | None = None):
    session.add(
        Notification(
            user_id=user_id,
            category=category,
            title=title[:140],
            message=message,
            reference=reference,
            is_read=False,
        )
    )


def _audit(session, event_type: str, description: str, user_id: int | None = None, severity: str = "info", reference: str | None = None):
    session.add(
        AuditEvent(
            user_id=user_id,
            event_type=event_type,
            description=description,
            severity=severity,
            reference=reference,
        )
    )


def _validate_units(units, label: str = "units") -> int:
    try:
        units = int(units)
    except (TypeError, ValueError):
        raise PrometheusServiceError(f"Enter a valid number of {label}.")
    if units < 1:
        raise PrometheusServiceError("You must use at least one unit.")
    if units > MAX_UNITS_PER_ACTION:
        raise PrometheusServiceError(f"A single action is limited to {MAX_UNITS_PER_ACTION:,} units.")
    return units


# ---------------------------------------------------------------------------
# Users / authentication / profile
# ---------------------------------------------------------------------------


def create_user(name: str, email: str, password: str, risk_profile: str = "Balanced") -> UserProfile:
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 120:
        raise PrometheusServiceError("Enter a name between 2 and 120 characters.")
    email = _normalise_email(email)
    risk_profile = (risk_profile or "Balanced").strip().title()
    if risk_profile not in ALLOWED_RISK_PROFILES:
        raise PrometheusServiceError("Risk profile must be Conservative, Balanced, or Growth.")

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise PrometheusServiceError(str(exc)) from exc

    with session_scope() as session:
        if session.query(User).filter(User.email == email).first() is not None:
            raise PrometheusServiceError("An account with that email already exists.")

        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            kyc_status="not_started",
            risk_profile=risk_profile,
        )
        session.add(user)
        session.flush()

        wallet = Wallet(user_id=user.id, currency="ZAR")
        session.add(wallet)
        session.flush()

        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="opening_balance",
                description="Demo opening balance",
                amount=Decimal("15000.00"),
                status="completed",
                reference=f"OPENING-{user.id}",
            )
        )
        _notify(
            session,
            user.id,
            "account",
            "Welcome to Prometheus",
            "Your prototype account and R15,000 simulated wallet are ready. Complete demo KYC before investing.",
        )
        _audit(session, "account_created", f"Prototype account created for {email}.", user.id)
        session.flush()
        return _profile(user)


def authenticate_user(email: str, password: str) -> UserProfile:
    """Authenticate with a committed failed-attempt counter and temporary lockout."""
    email = _normalise_email(email)
    now = utc_now()
    error_message: str | None = None
    profile: UserProfile | None = None

    # Authentication failures must be committed rather than rolled back, so we
    # decide the outcome inside the transaction and raise only after it closes.
    with session_scope() as session:
        user = session.query(User).filter(User.email == email).first()
        if user is None:
            error_message = "Incorrect email or password."
        else:
            locked_until = _aware(user.locked_until)
            if locked_until and locked_until > now:
                seconds = max(1, int((locked_until - now).total_seconds()))
                minutes = max(1, (seconds + 59) // 60)
                _audit(session, "login_blocked", "Login blocked while temporary account lock was active.", user.id, "warning")
                error_message = f"Too many failed attempts. Try again in about {minutes} minute(s)."
            elif not verify_password(password or "", user.password_hash):
                user.failed_login_count = int(user.failed_login_count or 0) + 1
                _audit(session, "login_failed", "Incorrect password supplied.", user.id, "warning")
                if user.failed_login_count >= LOGIN_FAILURE_LIMIT:
                    user.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
                    user.failed_login_count = 0
                    _notify(
                        session,
                        user.id,
                        "security",
                        "Temporary login lock",
                        f"Your prototype account was locked for {LOGIN_LOCK_MINUTES} minutes after repeated failed sign-in attempts.",
                    )
                    error_message = f"Too many failed attempts. Account locked for {LOGIN_LOCK_MINUTES} minutes."
                else:
                    remaining = LOGIN_FAILURE_LIMIT - user.failed_login_count
                    error_message = f"Incorrect email or password. {remaining} attempt(s) before temporary lock."
            else:
                user.failed_login_count = 0
                user.locked_until = None
                user.last_login_at = now
                _audit(session, "login_success", "Successful sign-in.", user.id)
                session.flush()
                profile = _profile(user)

    if error_message is not None:
        raise PrometheusServiceError(error_message)
    if profile is None:
        raise PrometheusServiceError("Incorrect email or password.")
    return profile


def get_user_profile(user_id: int) -> UserProfile:
    with session_scope() as session:
        return _profile(_require_user(session, user_id))


def update_user_profile(user_id: int, name: str, risk_profile: str) -> UserProfile:
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 120:
        raise PrometheusServiceError("Enter a name between 2 and 120 characters.")
    risk_profile = (risk_profile or "").strip().title()
    if risk_profile not in ALLOWED_RISK_PROFILES:
        raise PrometheusServiceError("Risk profile must be Conservative, Balanced, or Growth.")

    with session_scope() as session:
        user = _require_user(session, user_id)
        user.name = name
        user.risk_profile = risk_profile
        _audit(session, "profile_updated", f"Profile updated; risk profile set to {risk_profile}.", user.id)
        session.flush()
        return _profile(user)


def set_demo_kyc_status(user_id: int, status: str) -> UserProfile:
    status = (status or "").strip().lower()
    if status not in ALLOWED_KYC_STATUSES:
        raise PrometheusServiceError("Invalid KYC status.")
    with session_scope() as session:
        user = _require_user(session, user_id)
        previous = user.kyc_status
        user.kyc_status = status
        _audit(session, "kyc_status_changed", f"Demo KYC changed from {previous} to {status}.", user.id)
        if status == "verified" and previous != "verified":
            _notify(
                session,
                user.id,
                "kyc",
                "Demo KYC verified",
                "Your simulated KYC status is verified. Investment-market actions are now enabled.",
            )
        session.flush()
        return _profile(user)


def get_audit_events(user_id: int, limit: int = 25):
    with session_scope() as session:
        _require_user(session, user_id)
        return (
            session.query(AuditEvent)
            .filter(AuditEvent.user_id == int(user_id))
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(max(1, min(int(limit), 100)))
            .all()
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def get_notifications(user_id: int, limit: int = 50):
    with session_scope() as session:
        _require_user(session, user_id)
        return (
            session.query(Notification)
            .filter(Notification.user_id == int(user_id))
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(max(1, min(int(limit), 100)))
            .all()
        )


def get_unread_notification_count(user_id: int) -> int:
    with session_scope() as session:
        _require_user(session, user_id)
        return int(
            session.query(func.count(Notification.id))
            .filter(Notification.user_id == int(user_id), Notification.is_read.is_(False))
            .scalar()
            or 0
        )


def mark_notification_read(user_id: int, notification_id: int) -> None:
    with session_scope() as session:
        _require_user(session, user_id)
        notification = (
            session.query(Notification)
            .filter(Notification.id == int(notification_id), Notification.user_id == int(user_id))
            .first()
        )
        if notification is None:
            raise PrometheusServiceError("Notification not found.")
        notification.is_read = True


def mark_all_notifications_read(user_id: int) -> int:
    with session_scope() as session:
        _require_user(session, user_id)
        rows = (
            session.query(Notification)
            .filter(Notification.user_id == int(user_id), Notification.is_read.is_(False))
            .update({Notification.is_read: True}, synchronize_session=False)
        )
        return int(rows or 0)


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------


def get_wallet(user_id: int) -> float:
    with session_scope() as session:
        wallet = _require_wallet(session, user_id)
        return float(_wallet_balance(session, wallet.id))


def get_wallet_transactions(user_id: int, limit: int | None = None):
    with session_scope() as session:
        wallet = _require_wallet(session, user_id)
        query = (
            session.query(WalletTransaction)
            .filter(WalletTransaction.wallet_id == wallet.id)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        )
        if limit is not None:
            query = query.limit(max(1, min(int(limit), 500)))
        return query.all()


def deposit_funds(user_id: int, amount) -> WalletMovementResult:
    amount = _money(amount)
    if amount <= 0:
        raise PrometheusServiceError("Deposit amount must be greater than zero.")
    if amount > MAX_WALLET_MOVEMENT:
        raise PrometheusServiceError("Prototype deposits are limited to R1,000,000 per action.")

    with session_scope() as session:
        user = _require_user(session, user_id)
        wallet = _require_wallet(session, user.id)
        reference = _new_reference("DEP")
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="deposit",
                description="Simulated wallet deposit",
                amount=amount,
                status="completed",
                reference=reference,
            )
        )
        _notify(session, user.id, "wallet", "Wallet deposit", f"R{float(amount):,.2f} simulated cash was added to your wallet.", reference)
        _audit(session, "wallet_deposit", f"Simulated deposit of R{float(amount):,.2f}.", user.id, reference=reference)
        session.flush()
        balance = _wallet_balance(session, wallet.id)
        return WalletMovementResult(user.id, float(amount), float(balance), reference)


def withdraw_funds(user_id: int, amount) -> WalletMovementResult:
    amount = _money(amount)
    if amount <= 0:
        raise PrometheusServiceError("Withdrawal amount must be greater than zero.")
    if amount > MAX_WALLET_MOVEMENT:
        raise PrometheusServiceError("Prototype withdrawals are limited to R1,000,000 per action.")

    with session_scope() as session:
        user = _require_user(session, user_id)
        wallet = _require_wallet(session, user.id)
        balance_before = _wallet_balance(session, wallet.id)
        if amount > balance_before:
            _audit(session, "withdrawal_rejected", f"Rejected withdrawal of R{float(amount):,.2f}; insufficient balance.", user.id, "warning")
            raise PrometheusServiceError(f"Insufficient wallet balance. Available: R{balance_before:,.2f}.")

        reference = _new_reference("WDR")
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="withdrawal",
                description="Simulated wallet withdrawal",
                amount=-amount,
                status="completed",
                reference=reference,
            )
        )
        _notify(session, user.id, "wallet", "Wallet withdrawal", f"R{float(amount):,.2f} simulated cash was withdrawn from your wallet.", reference)
        _audit(session, "wallet_withdrawal", f"Simulated withdrawal of R{float(amount):,.2f}.", user.id, reference=reference)
        session.flush()
        balance = _wallet_balance(session, wallet.id)
        return WalletMovementResult(user.id, float(amount), float(balance), reference)


# ---------------------------------------------------------------------------
# Marketplace / Deal Room / Scenario Lab
# ---------------------------------------------------------------------------


def get_deals():
    with session_scope() as session:
        return session.query(Deal).order_by(Deal.id).all()


def get_deal(deal_id: int):
    with session_scope() as session:
        deal = (
            session.query(Deal)
            .options(joinedload(Deal.milestones))
            .filter(Deal.id == int(deal_id))
            .first()
        )
        if deal is None:
            raise PrometheusServiceError("Deal not found.")
        return deal


def run_scenario(deal_id: int, investment_amount, valuation_shock_pct=0, exit_delay_months=0) -> ScenarioResult:
    """Transparent what-if calculator; this is NOT a prediction or forecast."""
    amount = _money(investment_amount)
    if amount <= 0 or amount > MAX_WALLET_MOVEMENT:
        raise PrometheusServiceError("Scenario amount must be between R0.01 and R1,000,000.")
    try:
        shock = float(valuation_shock_pct)
        delay = int(exit_delay_months)
    except (TypeError, ValueError):
        raise PrometheusServiceError("Enter valid scenario assumptions.")
    if shock < -90 or shock > 200:
        raise PrometheusServiceError("Valuation change must be between -90% and +200%.")
    if delay < 0 or delay > 60:
        raise PrometheusServiceError("Exit delay must be between 0 and 60 months.")

    deal = get_deal(deal_id)
    years = (deal.base_horizon_months + delay) / 12.0
    growth_factor = (1 + (deal.base_return_pct / 100.0)) ** years
    shock_factor = 1 + (shock / 100.0)
    projected = max(0.0, float(amount) * growth_factor * shock_factor)
    gain = projected - float(amount)
    return ScenarioResult(
        deal_name=deal.name,
        investment_amount=float(amount),
        annual_return_pct=float(deal.base_return_pct),
        horizon_months=int(deal.base_horizon_months),
        exit_delay_months=delay,
        valuation_shock_pct=shock,
        projected_value=round(projected, 2),
        projected_gain=round(gain, 2),
        disclaimer=(
            "Illustrative what-if scenario using user-selected assumptions and a static demo return rate. "
            "It is not a forecast, valuation, recommendation or guarantee."
        ),
    )


def invest_in_deal(user_id: int, deal_id: int, units) -> InvestmentResult:
    units = _validate_units(units)

    with session_scope() as session:
        user = _require_verified_user(session, user_id)
        wallet = _require_wallet(session, user.id)
        deal = session.query(Deal).filter(Deal.id == int(deal_id)).first()
        if deal is None:
            raise PrometheusServiceError("Deal not found.")

        cost = _money(units * deal.unit_price)
        if cost > _money(deal.remaining):
            raise PrometheusServiceError("This investment exceeds the remaining amount in the deal.")

        balance_before = _wallet_balance(session, wallet.id)
        if cost > balance_before:
            _audit(session, "investment_rejected", f"Rejected {deal.name} investment; insufficient balance.", user.id, "warning")
            raise PrometheusServiceError(f"Insufficient wallet balance. Available: R{balance_before:,.2f}.")

        holding = (
            session.query(Holding)
            .filter(Holding.user_id == user.id, Holding.deal_id == deal.id)
            .first()
        )
        if holding is None:
            holding = Holding(user_id=user.id, deal_id=deal.id, units=0)
            session.add(holding)
        holding.units += units
        deal.funded += float(cost)

        reference = _new_reference("INV")
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="investment",
                description=f"Investment in {deal.name} ({units} units)",
                amount=-cost,
                status="completed",
                reference=reference,
            )
        )
        _notify(session, user.id, "investment", "Investment completed", f"You invested R{float(cost):,.2f} in {deal.name} ({units} units).", reference)
        _audit(session, "primary_investment", f"Bought {units} units of {deal.name} for R{float(cost):,.2f}.", user.id, reference=reference)
        session.flush()
        balance_after = _wallet_balance(session, wallet.id)

        return InvestmentResult(
            user_id=user.id,
            deal_id=deal.id,
            deal_name=deal.name,
            units=units,
            cost=float(cost),
            wallet_balance=float(balance_after),
            transaction_reference=reference,
        )


# ---------------------------------------------------------------------------
# Portfolio + rule-based intelligence + capital timeline
# ---------------------------------------------------------------------------


def get_holdings(user_id: int):
    with session_scope() as session:
        _require_user(session, user_id)
        return (
            session.query(Holding)
            .options(joinedload(Holding.deal).joinedload(Deal.milestones))
            .filter(Holding.user_id == int(user_id), Holding.units > 0)
            .order_by(Holding.id)
            .all()
        )


def get_portfolio_total(user_id: int) -> float:
    return float(sum(holding.cost_basis for holding in get_holdings(user_id)))


def get_portfolio_intelligence(user_id: int) -> PortfolioIntelligence:
    holdings = get_holdings(user_id)
    total = float(sum(h.cost_basis for h in holdings))
    if total <= 0:
        return PortfolioIntelligence(
            score=0,
            total_value=0.0,
            holding_count=0,
            sector_count=0,
            largest_sector="—",
            largest_sector_pct=0.0,
            high_risk_pct=0.0,
            long_lock_in_pct=0.0,
            income_exposure_pct=0.0,
            status="No portfolio yet",
            recommendations=("Add a first investment to generate portfolio diagnostics.",),
        )

    sectors: dict[str, float] = {}
    high_risk = 0.0
    long_lock = 0.0
    income = 0.0
    for holding in holdings:
        value = float(holding.cost_basis)
        sectors[holding.deal.sector] = sectors.get(holding.deal.sector, 0.0) + value
        if holding.deal.risk.lower() == "high":
            high_risk += value
        if int(holding.deal.lock_in_months or 0) > 24:
            long_lock += value
        if holding.deal.income_style.lower() == "income":
            income += value

    largest_sector, largest_value = max(sectors.items(), key=lambda item: item[1])
    largest_pct = (largest_value / total) * 100
    high_pct = (high_risk / total) * 100
    long_pct = (long_lock / total) * 100
    income_pct = (income / total) * 100

    score = 100
    if len(sectors) == 1:
        score -= 25
    elif len(sectors) == 2:
        score -= 10
    if largest_pct > 65:
        score -= 25
    elif largest_pct > 50:
        score -= 15
    elif largest_pct > 40:
        score -= 7
    if high_pct > 70:
        score -= 20
    elif high_pct > 50:
        score -= 10
    if long_pct > 75:
        score -= 15
    elif long_pct > 50:
        score -= 8
    if income_pct < 15:
        score -= 5
    score = max(0, min(100, score))

    recommendations: list[str] = []
    if largest_pct > 50:
        recommendations.append(f"{largest_sector} is {largest_pct:.0f}% of portfolio value; consider broader sector diversification.")
    if high_pct > 50:
        recommendations.append(f"High-risk assets represent {high_pct:.0f}% of portfolio value.")
    if long_pct > 50:
        recommendations.append(f"Assets with lock-ins above 24 months represent {long_pct:.0f}% of portfolio value.")
    if income_pct < 15:
        recommendations.append("Income-oriented exposure is low relative to growth-oriented holdings.")
    if not recommendations:
        recommendations.append("Portfolio is reasonably balanced across the current prototype diagnostics.")

    status = "Strong" if score >= 80 else "Balanced" if score >= 60 else "Concentrated" if score >= 40 else "Needs attention"
    return PortfolioIntelligence(
        score=score,
        total_value=round(total, 2),
        holding_count=len(holdings),
        sector_count=len(sectors),
        largest_sector=largest_sector,
        largest_sector_pct=round(largest_pct, 1),
        high_risk_pct=round(high_pct, 1),
        long_lock_in_pct=round(long_pct, 1),
        income_exposure_pct=round(income_pct, 1),
        status=status,
        recommendations=tuple(recommendations),
    )


def get_deal_suitability(user_id: int, deal_id: int) -> SuitabilitySnapshot:
    """Rules-based fit snapshot for education; not an investment recommendation."""
    profile = get_user_profile(user_id)
    deal = get_deal(deal_id)
    holdings = get_holdings(user_id)
    total = float(sum(h.cost_basis for h in holdings))
    sector_value = float(sum(h.cost_basis for h in holdings if h.deal.sector == deal.sector))
    current_sector_pct = (sector_value / total * 100.0) if total > 0 else 0.0
    after_total = total + float(deal.unit_price)
    after_sector = sector_value + float(deal.unit_price)
    sector_after_pct = (after_sector / after_total * 100.0) if after_total > 0 else 100.0

    profile_capacity = {"Conservative": 1, "Balanced": 2, "Growth": 3}.get(profile.risk_profile, 2)
    deal_level = {"low": 1, "med": 2, "medium": 2, "high": 3}.get((deal.risk or "med").lower(), 2)
    if deal_level < profile_capacity:
        risk_fit = "Within profile"
    elif deal_level == profile_capacity:
        risk_fit = "Aligned"
    else:
        risk_fit = "Above profile"

    cautions: list[str] = []
    if deal_level > profile_capacity:
        cautions.append(f"{deal.name} is {deal.risk.upper()} risk while your profile is {profile.risk_profile}.")
    if sector_after_pct >= 50:
        cautions.append(f"One additional unit would take {deal.sector} exposure to about {sector_after_pct:.0f}% of portfolio value.")
    elif sector_after_pct - current_sector_pct >= 15:
        cautions.append(f"This position would materially increase {deal.sector} concentration.")
    if int(deal.lock_in_months or 0) > 24:
        cautions.append(f"The stated lock-in is {deal.lock_in}; capital may be unavailable for an extended period.")
    if not cautions:
        cautions.append("No concentration or risk-profile flag is triggered by the current prototype rules.")

    summary = (
        f"{risk_fit}. Current {deal.sector} exposure is {current_sector_pct:.0f}% and would be approximately "
        f"{sector_after_pct:.0f}% after one additional unit. This is an educational suitability snapshot, not advice."
    )
    return SuitabilitySnapshot(
        deal_id=deal.id,
        deal_name=deal.name,
        risk_profile=profile.risk_profile,
        deal_risk=deal.risk,
        risk_fit=risk_fit,
        current_sector_pct=round(current_sector_pct, 1),
        sector_after_one_unit_pct=round(sector_after_pct, 1),
        lock_in_months=int(deal.lock_in_months or 0),
        summary=summary,
        cautions=tuple(cautions),
    )


# ---------------------------------------------------------------------------
# Secondary market + order book
# ---------------------------------------------------------------------------


def create_secondary_listing(user_id: int, deal_id: int, units, price_per_unit) -> ListingResult:
    units = _validate_units(units, "units to list")
    price = _money(price_per_unit)
    if price <= 0:
        raise PrometheusServiceError("Listing price must be greater than zero.")
    if price > MAX_LISTING_PRICE:
        raise PrometheusServiceError("Listing price exceeds the prototype limit.")

    with session_scope() as session:
        seller = _require_verified_user(session, user_id)
        holding = (
            session.query(Holding)
            .options(joinedload(Holding.deal))
            .filter(Holding.user_id == seller.id, Holding.deal_id == int(deal_id))
            .first()
        )
        if holding is None or holding.units < units:
            available = holding.units if holding is not None else 0
            raise PrometheusServiceError(f"You cannot list more units than you own. Available: {available}.")

        holding.units -= units
        listing = SecondaryListing(
            seller_id=seller.id,
            deal_id=holding.deal_id,
            units=units,
            price_per_unit=price,
            status="active",
        )
        session.add(listing)
        session.flush()
        total = _money(price * units)
        reference = f"LIST-{listing.id}"
        _notify(session, seller.id, "market", "Listing created", f"{units} {holding.deal.name} units are listed at R{float(price):,.2f} each.", reference)
        _audit(session, "listing_created", f"Listed {units} {holding.deal.name} units at R{float(price):,.2f}.", seller.id, reference=reference)
        return ListingResult(listing.id, seller.id, holding.deal_id, holding.deal.name, units, float(price), float(total))


def get_active_listings():
    with session_scope() as session:
        return (
            session.query(SecondaryListing)
            .options(joinedload(SecondaryListing.deal), joinedload(SecondaryListing.seller))
            .filter(SecondaryListing.status == "active")
            .order_by(SecondaryListing.created_at.desc(), SecondaryListing.id.desc())
            .all()
        )


def get_user_listings(user_id: int):
    with session_scope() as session:
        _require_user(session, user_id)
        return (
            session.query(SecondaryListing)
            .options(
                joinedload(SecondaryListing.deal),
                joinedload(SecondaryListing.seller),
                joinedload(SecondaryListing.buyer),
            )
            .filter(SecondaryListing.seller_id == int(user_id))
            .order_by(SecondaryListing.created_at.desc(), SecondaryListing.id.desc())
            .all()
        )


def cancel_secondary_listing(user_id: int, listing_id: int) -> CancellationResult:
    with session_scope() as session:
        seller = _require_user(session, user_id)
        listing = (
            session.query(SecondaryListing)
            .options(joinedload(SecondaryListing.deal))
            .filter(SecondaryListing.id == int(listing_id))
            .first()
        )
        if listing is None:
            raise PrometheusServiceError("Listing not found.")
        if listing.seller_id != seller.id:
            raise PrometheusServiceError("You can only cancel your own listing.")
        if listing.status != "active":
            raise PrometheusServiceError("Only active listings can be cancelled.")

        holding = session.query(Holding).filter(Holding.user_id == seller.id, Holding.deal_id == listing.deal_id).first()
        if holding is None:
            holding = Holding(user_id=seller.id, deal_id=listing.deal_id, units=0)
            session.add(holding)
        holding.units += listing.units
        listing.status = "cancelled"
        listing.closed_at = utc_now()
        reference = f"LIST-{listing.id}"
        _notify(session, seller.id, "market", "Listing cancelled", f"{listing.units} {listing.deal.name} units were returned to your portfolio.", reference)
        _audit(session, "listing_cancelled", f"Cancelled listing for {listing.units} {listing.deal.name} units.", seller.id, reference=reference)
        session.flush()
        return CancellationResult(listing.id, listing.units, listing.deal.name)


def buy_secondary_listing(buyer_id: int, listing_id: int) -> TradeResult:
    with session_scope() as session:
        buyer = _require_verified_user(session, buyer_id)
        buyer_wallet = _require_wallet(session, buyer.id)
        listing = (
            session.query(SecondaryListing)
            .options(joinedload(SecondaryListing.deal), joinedload(SecondaryListing.seller))
            .filter(SecondaryListing.id == int(listing_id))
            .first()
        )
        if listing is None:
            raise PrometheusServiceError("Listing not found.")
        if listing.status != "active":
            raise PrometheusServiceError("This listing is no longer available.")
        if listing.seller_id == buyer.id:
            raise PrometheusServiceError("You cannot buy your own listing.")

        seller = _require_user(session, listing.seller_id)
        seller_wallet = _require_wallet(session, seller.id)
        price = _money(listing.price_per_unit)
        gross = _money(price * listing.units)
        buyer_balance_before = _wallet_balance(session, buyer_wallet.id)
        if gross > buyer_balance_before:
            _audit(session, "secondary_purchase_rejected", f"Rejected secondary purchase of {listing.deal.name}; insufficient balance.", buyer.id, "warning")
            raise PrometheusServiceError(f"Insufficient wallet balance. Available: R{buyer_balance_before:,.2f}.")

        fee = _money(gross * SECONDARY_PLATFORM_FEE_RATE)
        net = _money(gross - fee)
        reference = _new_reference("TRD")

        buyer_holding = session.query(Holding).filter(Holding.user_id == buyer.id, Holding.deal_id == listing.deal_id).first()
        if buyer_holding is None:
            buyer_holding = Holding(user_id=buyer.id, deal_id=listing.deal_id, units=0)
            session.add(buyer_holding)
        buyer_holding.units += listing.units

        session.add(WalletTransaction(wallet_id=buyer_wallet.id, transaction_type="secondary_purchase", description=f"Secondary purchase: {listing.deal.name} ({listing.units} units @ R{float(price):,.2f})", amount=-gross, status="completed", reference=reference))
        session.add(WalletTransaction(wallet_id=seller_wallet.id, transaction_type="secondary_sale", description=f"Secondary sale: {listing.deal.name} ({listing.units} units @ R{float(price):,.2f})", amount=gross, status="completed", reference=reference))
        if fee > 0:
            session.add(WalletTransaction(wallet_id=seller_wallet.id, transaction_type="platform_fee", description=f"Secondary market platform fee ({SECONDARY_PLATFORM_FEE_RATE * 100:.0f}%)", amount=-fee, status="completed", reference=reference))

        listing.status = "sold"
        listing.buyer_id = buyer.id
        listing.closed_at = utc_now()
        trade = Trade(
            listing_id=listing.id,
            deal_id=listing.deal_id,
            seller_id=seller.id,
            buyer_id=buyer.id,
            units=listing.units,
            price_per_unit=price,
            gross_amount=gross,
            platform_fee=fee,
            net_to_seller=net,
            reference=reference,
            status="completed",
        )
        session.add(trade)
        _notify(session, buyer.id, "trade", "Secondary purchase completed", f"You bought {listing.units} {listing.deal.name} units for R{float(gross):,.2f}.", reference)
        _notify(session, seller.id, "trade", "Secondary sale completed", f"Your {listing.units} {listing.deal.name} units sold for R{float(gross):,.2f}; net after fee: R{float(net):,.2f}.", reference)
        _audit(session, "secondary_purchase", f"Bought {listing.units} {listing.deal.name} units from user {seller.id}.", buyer.id, reference=reference)
        _audit(session, "secondary_sale", f"Sold {listing.units} {listing.deal.name} units to user {buyer.id}.", seller.id, reference=reference)
        session.flush()

        buyer_balance_after = _wallet_balance(session, buyer_wallet.id)
        seller_balance_after = _wallet_balance(session, seller_wallet.id)
        return TradeResult(
            trade.id,
            listing.id,
            reference,
            listing.deal.name,
            seller.id,
            buyer.id,
            listing.units,
            float(price),
            float(gross),
            float(fee),
            float(net),
            float(buyer_balance_after),
            float(seller_balance_after),
        )


def get_trade_history(user_id: int):
    with session_scope() as session:
        _require_user(session, user_id)
        return (
            session.query(Trade)
            .options(joinedload(Trade.deal), joinedload(Trade.seller), joinedload(Trade.buyer))
            .filter(or_(Trade.seller_id == int(user_id), Trade.buyer_id == int(user_id)))
            .order_by(Trade.executed_at.desc(), Trade.id.desc())
            .all()
        )


def get_order_book(deal_id: int) -> OrderBookSnapshot:
    with session_scope() as session:
        deal = session.query(Deal).filter(Deal.id == int(deal_id)).first()
        if deal is None:
            raise PrometheusServiceError("Deal not found.")

        listings = session.query(SecondaryListing).filter(SecondaryListing.deal_id == deal.id, SecondaryListing.status == "active").all()
        bids = session.query(IndicativeBid).filter(IndicativeBid.deal_id == deal.id, IndicativeBid.status == "active").all()

        asks_by_price: dict[Decimal, list[int]] = {}
        for listing in listings:
            price = _money(listing.price_per_unit)
            data = asks_by_price.setdefault(price, [0, 0])
            data[0] += listing.units
            data[1] += 1
        bids_by_price: dict[Decimal, list[int]] = {}
        for bid in bids:
            price = _money(bid.price_per_unit)
            data = bids_by_price.setdefault(price, [0, 0])
            data[0] += bid.units
            data[1] += 1

        ask_levels = tuple(OrderLevel("ask", float(price), data[0], data[1]) for price, data in sorted(asks_by_price.items(), key=lambda x: x[0]))
        bid_levels = tuple(OrderLevel("bid", float(price), data[0], data[1]) for price, data in sorted(bids_by_price.items(), key=lambda x: x[0], reverse=True))
        recent_units = int(session.query(func.coalesce(func.sum(Trade.units), 0)).filter(Trade.deal_id == deal.id).scalar() or 0)
        return OrderBookSnapshot(
            deal_id=deal.id,
            deal_name=deal.name,
            indicative_value=float(deal.unit_price),
            best_bid=bid_levels[0].price if bid_levels else None,
            best_ask=ask_levels[0].price if ask_levels else None,
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            recent_traded_units=recent_units,
        )



def _risk_score(risk: str) -> float:
    return {"low": 0.2, "medium": 0.55, "high": 0.9}.get((risk or "").lower(), 0.55)


def _liquidity_snapshot_in_session(session, user_id: int, deal_id: int, proposed_price=None) -> LiquiditySnapshot:
    user = _require_user(session, user_id)
    deal = session.query(Deal).filter(Deal.id == int(deal_id)).first()
    if deal is None:
        raise PrometheusServiceError("Deal not found.")
    holding = session.query(Holding).filter(
        Holding.user_id == user.id,
        Holding.deal_id == deal.id,
        Holding.units > 0,
    ).first()
    if holding is None:
        raise PrometheusServiceError("Liquidity Intelligence requires a position in this opportunity.")

    price = float(proposed_price) if proposed_price not in (None, "") else float(deal.unit_price)
    if price <= 0 or price > float(MAX_LISTING_PRICE):
        raise PrometheusServiceError("Enter a valid proposed listing price.")

    listings = session.query(SecondaryListing).filter(
        SecondaryListing.deal_id == deal.id,
        SecondaryListing.status == "active",
    ).all()
    bids = session.query(IndicativeBid).filter(
        IndicativeBid.deal_id == deal.id,
        IndicativeBid.status == "active",
    ).all()
    trades = session.query(Trade).filter(
        Trade.deal_id == deal.id,
        Trade.status == "completed",
    ).all()

    best_bid = max((float(b.price_per_unit) for b in bids), default=None)
    best_ask = min((float(x.price_per_unit) for x in listings), default=None)
    reference = max(0.01, float(deal.unit_price))
    spread_anchor_bid = best_bid if best_bid is not None else reference * 0.96
    spread_anchor_ask = best_ask if best_ask is not None else reference * 1.04
    spread_pct = max(0.2, ((spread_anchor_ask - spread_anchor_bid) / reference) * 100)

    visible_bid_units = int(sum(int(b.units) for b in bids))
    visible_ask_units = int(sum(int(x.units) for x in listings))
    position_units = max(1, int(holding.units))
    demand_ratio = visible_bid_units / position_units
    recent_trade_units = int(sum(int(t.units) for t in trades))
    recent_trade_ratio = recent_trade_units / position_units
    active_user_listing = session.query(SecondaryListing).filter(
        SecondaryListing.seller_id == user.id,
        SecondaryListing.deal_id == deal.id,
        SecondaryListing.status == "active",
    ).order_by(SecondaryListing.created_at.asc()).first()
    listing_age_days = 0.0
    if active_user_listing is not None:
        created = _aware(active_user_listing.created_at)
        listing_age_days = max(0.0, (utc_now() - created).total_seconds() / 86400.0)

    discount_pct = ((reference - price) / reference) * 100
    observations = len(bids) + len(listings) + len(trades)
    features = LiquidityFeatures(
        price_discount_pct=discount_pct,
        demand_ratio=demand_ratio,
        spread_pct=spread_pct,
        recent_trade_ratio=recent_trade_ratio,
        listing_age_days=listing_age_days,
        risk_score=_risk_score(deal.risk),
    )
    forecast = forecast_liquidity(features, price, reference, observations)
    return LiquiditySnapshot(
        deal_id=deal.id,
        deal_name=deal.name,
        deal_code=deal.code,
        holding_units=position_units,
        reference_price=round(reference, 2),
        proposed_price=round(price, 2),
        best_bid=round(best_bid, 2) if best_bid is not None else None,
        best_ask=round(best_ask, 2) if best_ask is not None else None,
        visible_bid_units=visible_bid_units,
        visible_ask_units=visible_ask_units,
        market_observations=observations,
        forecast=forecast,
    )


def get_liquidity_snapshot(user_id: int, deal_id: int, proposed_price=None) -> LiquiditySnapshot:
    """Return explainable liquidity forecasts for one owned position."""
    with session_scope() as session:
        return _liquidity_snapshot_in_session(session, user_id, deal_id, proposed_price)


def get_portfolio_liquidity(user_id: int) -> PortfolioLiquiditySnapshot:
    """Aggregate position forecasts into a portfolio liquidity stress view."""
    with session_scope() as session:
        _require_user(session, user_id)
        holdings = session.query(Holding).options(joinedload(Holding.deal)).filter(
            Holding.user_id == int(user_id), Holding.units > 0
        ).all()
        weighted = []
        for holding in holdings:
            snapshot = _liquidity_snapshot_in_session(session, user_id, holding.deal_id, holding.deal.unit_price)
            weighted.append((float(holding.cost_basis), snapshot.forecast))
        return portfolio_liquidity_snapshot(weighted)


def get_exit_goal_plan(user_id: int, deal_id: int, target_days: int) -> ExitGoalResult:
    """Estimate an indicative price range associated with a desired exit horizon."""
    try:
        target = int(target_days)
    except (TypeError, ValueError):
        raise PrometheusServiceError("Choose a valid exit horizon.")
    if target not in {7, 14, 30}:
        raise PrometheusServiceError("Exit horizon must be 7, 14 or 30 days.")

    base = get_liquidity_snapshot(user_id, deal_id)
    ref = base.reference_price
    candidates = [ref * pct for pct in (0.90, 0.92, 0.94, 0.96, 0.98, 1.00, 1.02)]
    scored = []
    for price in candidates:
        snap = get_liquidity_snapshot(user_id, deal_id, price)
        probability = {
            7: snap.forecast.probability_7d,
            14: snap.forecast.probability_14d,
            30: snap.forecast.probability_30d,
        }[target]
        scored.append((price, probability))
    viable = [row for row in scored if row[1] >= 65.0]
    chosen = viable[-1] if viable else max(scored, key=lambda row: row[1])
    center, probability = chosen
    return ExitGoalResult(
        deal_id=base.deal_id,
        deal_name=base.deal_name,
        target_days=target,
        suggested_price_low=round(center * 0.985, 2),
        suggested_price_high=round(center * 1.015, 2),
        estimated_probability=round(probability, 1),
        note="Indicative simulated range only. A sale is never guaranteed and this is not financial advice.",
    )


def get_liquidity_model_validation():
    """Expose held-out simulated backtest metrics for the Transparency Centre."""
    return backtest_model()


def get_liquidity_model_card() -> dict:
    """Return a defensive copy of the model transparency card."""
    return {key: value for key, value in MODEL_CARD.items()}


def get_market_revision() -> MarketRevision:
    with session_scope() as session:
        active_listings = int(session.query(func.count(SecondaryListing.id)).filter(SecondaryListing.status == "active").scalar() or 0)
        active_bids = int(session.query(func.count(IndicativeBid.id)).filter(IndicativeBid.status == "active").scalar() or 0)
        completed_trades = int(session.query(func.count(Trade.id)).filter(Trade.status == "completed").scalar() or 0)
        newest_listing_id = int(session.query(func.coalesce(func.max(SecondaryListing.id), 0)).scalar() or 0)
        newest_trade_id = int(session.query(func.coalesce(func.max(Trade.id), 0)).scalar() or 0)
        return MarketRevision(active_listings, active_bids, completed_trades, newest_listing_id, newest_trade_id)
