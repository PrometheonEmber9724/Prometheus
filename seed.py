"""Deterministic demo data for Prometheus One — final hackathon build."""

from decimal import Decimal

from database import session_scope
from models import (
    Deal,
    DealMilestone,
    Holding,
    IndicativeBid,
    Notification,
    SecondaryListing,
    User,
    Wallet,
    WalletTransaction,
)
from security import hash_password


DEMO_EMAIL = "demo@prometheus.local"
DEMO_PASSWORD = "Prometheus123!"
SELLER_EMAIL = "seller@prometheus.local"
SELLER_PASSWORD = "Seller123!"
JUDGE_EMAIL = "judge@prometheus.demo"
JUDGE_PASSWORD = "PrometheusDemo26!"

DEMO_DEALS = [
    dict(
        code="SPV-014", name="Solstice Robotics", sector="Technology",
        type="Pre-IPO Equity", risk="high",
        blurb="Warehouse automation robotics scaling into East Africa ahead of a planned 2028 listing.",
        total_raise=5_000_000, funded=3_260_000, unit_price=500,
        lock_in="36 months", lock_in_months=36,
        projected="18–24% p.a. (target, unrealised)",
        geography="South Africa / East Africa", issuer="Solstice Robotics SPV",
        investment_thesis=(
            "A growth-stage automation company expanding warehouse robotics into under-served African logistics markets, "
            "with revenue growth tied to regional e-commerce and industrial automation demand."
        ),
        use_of_funds="Manufacturing capacity; East African market entry; sales engineering; working capital.",
        key_risks="Execution risk; customer concentration; hardware supply-chain risk; pre-IPO valuation risk.",
        key_documents="Information memorandum; cap-table summary; management presentation; risk disclosure.",
        base_return_pct=20.0, base_horizon_months=36, income_style="growth",
    ),
    dict(
        code="BND-208", name="Karoo Wind Bond", sector="Renewable Energy",
        type="Unlisted Corporate Bond", risk="low",
        blurb="5-year senior bond funding turbine expansion at an operating Northern Cape wind farm.",
        total_raise=8_000_000, funded=6_120_000, unit_price=250,
        lock_in="60 months (fixed term)", lock_in_months=60,
        projected="11.4% p.a. (fixed coupon)",
        geography="Northern Cape, South Africa", issuer="Karoo Wind Energy SPV",
        investment_thesis="Senior debt exposure to an operating renewable-energy asset with contracted power revenues.",
        use_of_funds="Turbine expansion; grid-connection works; maintenance reserve; transaction costs.",
        key_risks="Operational downtime; counterparty risk; grid curtailment; refinancing risk.",
        key_documents="Bond terms; security package summary; operating report; risk disclosure.",
        base_return_pct=11.4, base_horizon_months=60, income_style="income",
    ),
    dict(
        code="PEF-091", name="Meridian Logistics Fund II", sector="Logistics",
        type="Private Equity Fund", risk="high",
        blurb="Growth-stage fund acquiring mid-size freight and cold-chain operators across the SADC region.",
        total_raise=20_000_000, funded=9_840_000, unit_price=1000,
        lock_in="5–7 years", lock_in_months=72,
        projected="20%+ IRR (target, unrealised)",
        geography="SADC", issuer="Meridian Logistics Fund II",
        investment_thesis="A buy-and-build strategy targeting fragmented regional logistics and cold-chain operators.",
        use_of_funds="Platform acquisitions; bolt-on transactions; systems integration; expansion capital.",
        key_risks="Leverage; integration risk; fuel and FX exposure; delayed exits; valuation risk.",
        key_documents="Fund memorandum; strategy summary; fee schedule; risk disclosure.",
        base_return_pct=20.0, base_horizon_months=72, income_style="growth",
    ),
    dict(
        code="PDB-055", name="Highveld Health Debt", sector="Healthcare",
        type="Private Debt", risk="med",
        blurb="Senior secured lending facility for a private day-clinic network expanding into underserved towns.",
        total_raise=6_000_000, funded=4_770_000, unit_price=500,
        lock_in="24 months", lock_in_months=24,
        projected="14.2% p.a. (fixed coupon)",
        geography="Gauteng / Mpumalanga / Limpopo", issuer="Highveld Health Finance SPV",
        investment_thesis="Secured private-debt exposure to a clinic network serving high-demand secondary healthcare markets.",
        use_of_funds="Clinic fit-outs; medical equipment; working capital; expansion into underserved towns.",
        key_risks="Collections risk; medical-aid concentration; expansion execution; collateral recovery.",
        key_documents="Facility summary; security package; borrower overview; risk disclosure.",
        base_return_pct=14.2, base_horizon_months=24, income_style="income",
    ),
    dict(
        code="INF-132", name="Vaal Grain Silo Note", sector="Agriculture",
        type="Unlisted Infrastructure Bond", risk="med",
        blurb="Financing new silo capacity for a commercial grain co-operative ahead of harvest season.",
        total_raise=4_500_000, funded=1_980_000, unit_price=250,
        lock_in="18 months", lock_in_months=18,
        projected="13.8% p.a. (fixed coupon)",
        geography="Free State / Gauteng", issuer="Vaal Grain Infrastructure SPV",
        investment_thesis="Short-duration infrastructure debt linked to storage capacity supporting established grain flows.",
        use_of_funds="Silo construction; handling equipment; civil works; contingency reserve.",
        key_risks="Commodity-cycle exposure; construction delays; weather impacts; counterparty concentration.",
        key_documents="Note terms; construction budget; co-operative overview; risk disclosure.",
        base_return_pct=13.8, base_horizon_months=18, income_style="income",
    ),
]

MILESTONES = {
    "SPV-014": [
        (1, "Raise closes", "Final subscriptions are allocated and the SPV closes the round.", "current", "Q4 2026"),
        (2, "Expansion capital deployed", "Manufacturing and market-entry budget is released against milestones.", "upcoming", "Q1–Q2 2027"),
        (3, "East Africa commercial update", "Management reports customer wins, recurring revenue and deployment progress.", "upcoming", "Q4 2027"),
        (4, "Strategic exit window", "Illustrative liquidity event window subject to market conditions and company performance.", "upcoming", "2028+"),
    ],
    "BND-208": [
        (1, "Bond allocation", "Investor allocations settle and expansion funding is ring-fenced.", "current", "Q4 2026"),
        (2, "Turbine works", "Expansion and grid-connection works progress under the operating plan.", "upcoming", "2027"),
        (3, "Coupon cycle", "Fixed-coupon payments are simulated according to the note terms.", "upcoming", "Semi-annual"),
        (4, "Principal maturity", "Principal is due at fixed-term maturity, subject to issuer performance.", "upcoming", "2031"),
    ],
    "PEF-091": [
        (1, "Fund close", "Capital commitments are finalised for the investment period.", "current", "2026"),
        (2, "Platform acquisitions", "The manager deploys capital into freight and cold-chain operators.", "upcoming", "2027–2028"),
        (3, "Value creation", "Integration, technology and route-density initiatives are implemented.", "upcoming", "2028–2030"),
        (4, "Exit programme", "Portfolio exits are pursued as market conditions permit.", "upcoming", "2031–2033"),
    ],
    "PDB-055": [
        (1, "Facility drawdown", "Borrower drawdowns fund agreed expansion milestones.", "current", "Q4 2026"),
        (2, "Clinic openings", "New day-clinic capacity comes online in target towns.", "upcoming", "2027"),
        (3, "Coupon cycle", "Fixed-coupon payments are simulated under the facility terms.", "upcoming", "Quarterly"),
        (4, "Facility maturity", "Principal is due at the end of the 24-month term.", "upcoming", "Q4 2028"),
    ],
    "INF-132": [
        (1, "Construction funding", "Capital is released against silo construction milestones.", "current", "Q4 2026"),
        (2, "Commissioning", "New storage capacity is commissioned ahead of harvest flows.", "upcoming", "H1 2027"),
        (3, "Operating season", "Storage utilisation and operating performance are reported.", "upcoming", "2027 harvest"),
        (4, "Note maturity", "Principal is due at the end of the 18-month term.", "upcoming", "H1 2028"),
    ],
}

INDICATIVE_BIDS = {
    "SPV-014": [("Investor Interest #441", 4, "505.00"), ("Investor Interest #182", 7, "500.00"), ("Investor Interest #773", 10, "490.00")],
    "BND-208": [("Income Desk #112", 12, "242.00"), ("Investor Interest #835", 8, "238.00")],
    "PEF-091": [("Investor Interest #309", 2, "980.00"), ("Investor Interest #171", 4, "950.00")],
    "PDB-055": [("Income Desk #226", 5, "500.00"), ("Investor Interest #614", 8, "492.00")],
    "INF-132": [("Investor Interest #728", 10, "248.00"), ("Investor Interest #327", 15, "240.00")],
}


def _ensure_wallet(session, user: User, amount: Decimal):
    wallet = session.query(Wallet).filter(Wallet.user_id == user.id).first()
    if wallet is None:
        wallet = Wallet(user_id=user.id, currency="ZAR")
        session.add(wallet)
        session.flush()
    reference = f"OPENING-{user.id}"
    if session.query(WalletTransaction).filter(WalletTransaction.reference == reference).first() is None:
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                transaction_type="opening_balance",
                description="Demo opening balance",
                amount=amount,
                status="completed",
                reference=reference,
            )
        )


def _ensure_welcome_notification(session, user: User):
    if session.query(Notification).filter(Notification.user_id == user.id).count() == 0:
        session.add(
            Notification(
                user_id=user.id,
                category="account",
                title="Prometheus One ready",
                message="Prometheus One includes Deal Rooms, Portfolio Intelligence, a near-live secondary market and explainable Liquidity Intelligence.",
                is_read=False,
            )
        )



def _ensure_judge_showcase(session, judge: User, deals: dict[str, Deal]):
    """Give the judge account a diversified, screenshot-ready simulated portfolio."""
    if session.query(Holding).filter(Holding.user_id == judge.id).count() == 0:
        portfolio = {
            "SPV-014": 4,
            "BND-208": 8,
            "PEF-091": 2,
            "PDB-055": 4,
            "INF-132": 6,
        }
        for code, units in portfolio.items():
            session.add(Holding(user_id=judge.id, deal_id=deals[code].id, units=units))

    wallet = session.query(Wallet).filter(Wallet.user_id == judge.id).first()
    if wallet is None:
        wallet = Wallet(user_id=judge.id, currency="ZAR")
        session.add(wallet)
        session.flush()

    historical = [
        ("JUDGE-INV-SPV", "Investment in Solstice Robotics (4 units)", Decimal("-2000.00")),
        ("JUDGE-INV-BND", "Investment in Karoo Wind Bond (8 units)", Decimal("-2000.00")),
        ("JUDGE-INV-PEF", "Investment in Meridian Logistics Fund II (2 units)", Decimal("-2000.00")),
        ("JUDGE-INV-PDB", "Investment in Highveld Health Debt (4 units)", Decimal("-2000.00")),
        ("JUDGE-INV-INF", "Investment in Vaal Grain Silo Note (6 units)", Decimal("-1500.00")),
    ]
    for reference, description, amount in historical:
        if session.query(WalletTransaction).filter(WalletTransaction.reference == reference).first() is None:
            session.add(
                WalletTransaction(
                    wallet_id=wallet.id,
                    transaction_type="investment",
                    description=description,
                    amount=amount,
                    status="completed",
                    reference=reference,
                )
            )

    existing_titles = {n.title for n in session.query(Notification).filter(Notification.user_id == judge.id).all()}
    showcase_notifications = [
        ("portfolio", "Portfolio diagnostics ready", "Your diversified demo portfolio is ready for Portfolio Intelligence."),
        ("market", "Secondary market active", "Live prototype asks and simulated indicative bids are available in the order book."),
        ("security", "Demo KYC verified", "This showcase account is pre-verified using simulated KYC. No identity documents were collected."),
        ("intelligence", "Liquidity Intelligence ready", "Your seeded portfolio is ready for sale-probability forecasts, pricing simulation and portfolio liquidity stress testing."),
    ]
    for category, title, message in showcase_notifications:
        if title not in existing_titles:
            session.add(Notification(user_id=judge.id, category=category, title=title, message=message, is_read=False))

def seed_demo_data():
    """Insert shared deals, showcase users, bids, milestones and listings."""
    with session_scope() as session:
        if session.query(Deal).count() == 0:
            session.add_all([Deal(**deal) for deal in DEMO_DEALS])
            session.flush()

        deals = {deal.code: deal for deal in session.query(Deal).all()}

        if session.query(DealMilestone).count() == 0:
            for code, milestones in MILESTONES.items():
                for sequence, title, description, phase, timing in milestones:
                    session.add(
                        DealMilestone(
                            deal_id=deals[code].id,
                            sequence=sequence,
                            title=title,
                            description=description,
                            phase=phase,
                            timing_label=timing,
                        )
                    )

        if session.query(IndicativeBid).count() == 0:
            for code, rows in INDICATIVE_BIDS.items():
                for bidder_label, units, price in rows:
                    session.add(
                        IndicativeBid(
                            deal_id=deals[code].id,
                            bidder_label=bidder_label,
                            units=units,
                            price_per_unit=Decimal(price),
                            status="active",
                        )
                    )

        demo = session.query(User).filter(User.email == DEMO_EMAIL).first()
        if demo is None:
            demo = User(
                name="Demo Investor",
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                kyc_status="verified",
                risk_profile="Balanced",
            )
            session.add(demo)
            session.flush()
        _ensure_wallet(session, demo, Decimal("15000.00"))
        _ensure_welcome_notification(session, demo)

        seller = session.query(User).filter(User.email == SELLER_EMAIL).first()
        if seller is None:
            seller = User(
                name="Market Seller",
                email=SELLER_EMAIL,
                password_hash=hash_password(SELLER_PASSWORD),
                kyc_status="verified",
                risk_profile="Growth",
            )
            session.add(seller)
            session.flush()
        _ensure_wallet(session, seller, Decimal("5000.00"))
        _ensure_welcome_notification(session, seller)

        judge = session.query(User).filter(User.email == JUDGE_EMAIL).first()
        if judge is None:
            judge = User(
                name="Prometheus One Judge Demo",
                email=JUDGE_EMAIL,
                password_hash=hash_password(JUDGE_PASSWORD),
                kyc_status="verified",
                risk_profile="Balanced",
            )
            session.add(judge)
            session.flush()
        _ensure_wallet(session, judge, Decimal("30000.00"))
        _ensure_welcome_notification(session, judge)
        _ensure_judge_showcase(session, judge, deals)

        if (
            session.query(Holding).filter(Holding.user_id == seller.id).count() == 0
            and session.query(SecondaryListing).filter(SecondaryListing.seller_id == seller.id).count() == 0
        ):
            inventory = {"SPV-014": 12, "BND-208": 20, "PDB-055": 10}
            holdings = {}
            for code, units in inventory.items():
                holding = Holding(user_id=seller.id, deal_id=deals[code].id, units=units)
                session.add(holding)
                session.flush()
                holdings[code] = holding

            listing_specs = [
                ("SPV-014", 3, Decimal("525.00")),
                ("BND-208", 6, Decimal("245.00")),
                ("PDB-055", 4, Decimal("510.00")),
            ]
            for code, units, price in listing_specs:
                holdings[code].units -= units
                session.add(
                    SecondaryListing(
                        seller_id=seller.id,
                        deal_id=deals[code].id,
                        units=units,
                        price_per_unit=price,
                        status="active",
                    )
                )
