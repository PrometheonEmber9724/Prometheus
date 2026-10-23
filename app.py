"""Prometheus One — final V7 FNB Hackathon build.

Architecture:
    Flet UI -> services.py -> database.py -> models.py -> SQLite
                    -> liquidity/ explainable forecasting engine

Prometheus One preserves the stable V1–V6 private-market investment, wallet,
ownership, Deal Room, Portfolio Intelligence and atomic secondary-market flows,
then adds Prometheus Liquidity Intelligence: Liquidity Score, 7/14/30-day sale
probability, expected time-to-sale, pricing sensitivity, demand signals,
explainability, confidence, portfolio stress testing, a Liquidity Passport and
transparent simulated-model validation.
"""

import asyncio
from datetime import datetime

import flet as ft

from database import init_database
from seed import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    JUDGE_EMAIL,
    JUDGE_PASSWORD,
    SELLER_EMAIL,
    SELLER_PASSWORD,
    seed_demo_data,
)
from services import (
    PrometheusServiceError,
    authenticate_user,
    buy_secondary_listing,
    cancel_secondary_listing,
    create_secondary_listing,
    create_user,
    deposit_funds,
    get_active_listings,
    get_audit_events,
    get_deal,
    get_deal_suitability,
    get_deals,
    get_holdings,
    get_exit_goal_plan,
    get_liquidity_model_card,
    get_liquidity_model_validation,
    get_liquidity_snapshot,
    get_market_revision,
    get_portfolio_liquidity,
    get_notifications,
    get_order_book,
    get_portfolio_intelligence,
    get_portfolio_total,
    get_trade_history,
    get_unread_notification_count,
    get_user_listings,
    get_user_profile,
    get_wallet,
    get_wallet_transactions,
    invest_in_deal,
    mark_all_notifications_read,
    mark_notification_read,
    run_scenario,
    set_demo_kyc_status,
    update_user_profile,
    withdraw_funds,
)


# ---------------------------------------------------------------------------
# Visual system — official pitch-deck reference (dark + light)
# ---------------------------------------------------------------------------

DARK_PALETTE = {
    "BG": "#070B18",
    "SIDEBAR": "#0A0F20",
    "SURFACE": "#111727",
    "SURFACE_2": "#151C2F",
    "SURFACE_3": "#1B2440",
    "BORDER": "#28324D",
    "TEXT": "#F5F7FF",
    "MUTED": "#91A0BA",
    "BRAND": "#2AD6B3",
    "BRAND_SOFT": "#103C3B",
    "CYAN": "#38C8F5",
    "BLUE": "#4E7CFF",
    "VIOLET": "#7C5CFF",
    "AMBER": "#F4B850",
    "TEAL": "#2AD6B3",
    "TEAL_DARK": "#103C3B",
    "RED": "#FF6B83",
    "RED_DARK": "#50202D",
    "HIGHLIGHT_SURFACE": "#151C2F",
    "BUTTON_TEXT": "#07131C",
}

LIGHT_PALETTE = {
    "BG": "#F5F7FC",
    "SIDEBAR": "#FFFFFF",
    "SURFACE": "#FFFFFF",
    "SURFACE_2": "#F1F4FB",
    "SURFACE_3": "#E9EEFA",
    "BORDER": "#DDE5F2",
    "TEXT": "#10203F",
    "MUTED": "#66758E",
    "BRAND": "#12B99A",
    "BRAND_SOFT": "#E2F8F3",
    "CYAN": "#24B7E8",
    "BLUE": "#3E72F6",
    "VIOLET": "#715AF8",
    "AMBER": "#B77A08",
    "TEAL": "#12A98E",
    "TEAL_DARK": "#DDF7F1",
    "RED": "#D9506A",
    "RED_DARK": "#FBE6EA",
    "HIGHLIGHT_SURFACE": "#F0F4FD",
    "BUTTON_TEXT": "#FFFFFF",
}

# Active palette values. They are intentionally mutable so the complete UI can
# switch between the official dark and light deck systems without duplicating
# view code.
BG = DARK_PALETTE["BG"]
SIDEBAR = DARK_PALETTE["SIDEBAR"]
SURFACE = DARK_PALETTE["SURFACE"]
SURFACE_2 = DARK_PALETTE["SURFACE_2"]
SURFACE_3 = DARK_PALETTE["SURFACE_3"]
BORDER = DARK_PALETTE["BORDER"]
TEXT = DARK_PALETTE["TEXT"]
MUTED = DARK_PALETTE["MUTED"]
BRAND = DARK_PALETTE["BRAND"]
BRAND_SOFT = DARK_PALETTE["BRAND_SOFT"]
CYAN = DARK_PALETTE["CYAN"]
BLUE = DARK_PALETTE["BLUE"]
VIOLET = DARK_PALETTE["VIOLET"]
AMBER = DARK_PALETTE["AMBER"]
TEAL = DARK_PALETTE["TEAL"]
TEAL_DARK = DARK_PALETTE["TEAL_DARK"]
RED = DARK_PALETTE["RED"]
RED_DARK = DARK_PALETTE["RED_DARK"]
HIGHLIGHT_SURFACE = DARK_PALETTE["HIGHLIGHT_SURFACE"]
BUTTON_TEXT = DARK_PALETTE["BUTTON_TEXT"]


def apply_palette(palette: dict) -> None:
    global BG, SIDEBAR, SURFACE, SURFACE_2, SURFACE_3, BORDER, TEXT, MUTED
    global BRAND, BRAND_SOFT, CYAN, BLUE, VIOLET, AMBER, TEAL, TEAL_DARK
    global RED, RED_DARK, HIGHLIGHT_SURFACE, BUTTON_TEXT
    for name in (
        "BG", "SIDEBAR", "SURFACE", "SURFACE_2", "SURFACE_3", "BORDER",
        "TEXT", "MUTED", "BRAND", "BRAND_SOFT", "CYAN", "BLUE", "VIOLET",
        "AMBER", "TEAL", "TEAL_DARK", "RED", "RED_DARK",
        "HIGHLIGHT_SURFACE", "BUTTON_TEXT",
    ):
        globals()[name] = palette[name]


def _money(value: float) -> str:
    return f"R{value:,.2f}"


async def main(page: ft.Page):
    page.title = "Prometheus One — Private Markets"
    page.window.width = 1440
    page.window.height = 920
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=BLUE)
    is_dark_mode = True

    current_user_id: int | None = None
    current_view = "login"
    current_deal_id: int | None = None
    live_market_column: ft.Column | None = None
    live_market_status: ft.Text | None = None
    last_market_revision = None

    # ------------------------------------------------------------------
    # Shared UI helpers
    # ------------------------------------------------------------------

    def show_message(message: str, error: bool = False) -> None:
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(value=message, color=TEXT),
                bgcolor=RED_DARK if error else TEAL_DARK,
            )
        )

    def require_user_id() -> int:
        if current_user_id is None:
            raise PrometheusServiceError("Please sign in first.")
        return current_user_id

    def spectrum_rule(height: int = 3):
        return ft.Row(
            spacing=0,
            controls=[
                ft.Container(expand=True, height=height, bgcolor=BRAND),
                ft.Container(expand=True, height=height, bgcolor=CYAN),
                ft.Container(expand=True, height=height, bgcolor=BLUE),
                ft.Container(expand=True, height=height, bgcolor=VIOLET),
            ],
        )

    def brand_lockup(compact: bool = False):
        return ft.Row(
            spacing=8,
            controls=[
                ft.Text(value="◆", color=CYAN, size=13 if compact else 17),
                ft.Text(
                    value="PROMETHEUS ONE",
                    color=TEXT,
                    size=13 if compact else 16,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        )

    def theme_toggle_button():
        label = "Light" if is_dark_mode else "Dark"
        icon = ft.Icons.LIGHT_MODE if is_dark_mode else ft.Icons.DARK_MODE
        return secondary_button(label, toggle_theme, icon)

    def toggle_theme(e=None):
        nonlocal is_dark_mode
        is_dark_mode = not is_dark_mode
        apply_palette(DARK_PALETTE if is_dark_mode else LIGHT_PALETTE)
        page.bgcolor = BG
        page.theme_mode = ft.ThemeMode.DARK if is_dark_mode else ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed=BLUE)
        rerender_current()

    def set_view(name: str, deal_id: int | None = None) -> None:
        nonlocal current_view, current_deal_id
        current_view = name
        current_deal_id = deal_id

    def primary_button(label: str, handler, icon=None, disabled: bool = False):
        return ft.Button(
            content=label,
            icon=icon,
            on_click=handler,
            disabled=disabled,
            bgcolor=BRAND,
            color=BUTTON_TEXT,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=18, vertical=13),
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

    def secondary_button(label: str, handler, icon=None, disabled: bool = False):
        return ft.Button(
            content=label,
            icon=icon,
            on_click=handler,
            disabled=disabled,
            bgcolor=SURFACE_2,
            color=TEXT,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                side=ft.BorderSide(width=1, color=BORDER),
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

    def panel(content, padding=18, col=None, bgcolor=None, border_color=None):
        if bgcolor is None:
            bgcolor = SURFACE
        if border_color is None:
            border_color = BORDER
        c = ft.Container(
            padding=padding,
            bgcolor=bgcolor,
            border=ft.Border.all(1, border_color),
            border_radius=16,
            content=content,
        )
        if col is not None:
            c.col = col
        return c

    def chip(label: str, tone: str = "neutral"):
        colors = {
            "neutral": (SURFACE_3, MUTED),
            "brand": (BRAND_SOFT, BRAND),
            "blue": (SURFACE_3, BLUE),
            "intelligence": (SURFACE_3, VIOLET),
            "positive": (TEAL_DARK, TEAL),
            "warning": (SURFACE_3, AMBER),
            "danger": (RED_DARK, RED),
        }
        bg, fg = colors.get(tone, colors["neutral"])
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            bgcolor=bg,
            border_radius=20,
            content=ft.Text(value=label, size=10, color=fg, weight=ft.FontWeight.BOLD),
        )

    def metric_card(label: str, value: str, note: str = "", tone: str = "neutral", col=None):
        value_color = TEAL if tone == "positive" else TEXT
        return panel(
            ft.Column(
                spacing=7,
                controls=[
                    ft.Text(value=label.upper(), size=10, color=MUTED, weight=ft.FontWeight.BOLD),
                    ft.Text(value=value, size=27, color=value_color, weight=ft.FontWeight.BOLD),
                    ft.Text(value=note, size=11, color=MUTED) if note else ft.Container(height=0),
                ],
            ),
            padding=16,
            col=col,
        )

    def section_title(title: str, subtitle: str | None = None):
        controls = [ft.Text(value=title, size=22, color=TEXT, weight=ft.FontWeight.BOLD)]
        if subtitle:
            controls.append(ft.Text(value=subtitle, size=12, color=MUTED))
        return ft.Column(spacing=3, controls=controls)

    def bullet(text: str, color=None):
        if color is None:
            color = MUTED
        return ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Text(value="•", color=BRAND, size=16),
                ft.Text(value=text, size=12, color=color, expand=True),
            ],
        )

    def status_tone(risk: str):
        risk = (risk or "").lower()
        if risk == "low":
            return "positive"
        if risk in {"med", "medium"}:
            return "brand"
        return "danger"

    def page_heading(title: str, subtitle: str, eyebrow: str | None = None):
        controls = []
        if eyebrow:
            controls.append(ft.Text(value=eyebrow.upper(), size=10, color=BRAND, weight=ft.FontWeight.BOLD))
        controls.extend(
            [
                ft.Text(value=title, size=32, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Text(value=subtitle, size=13, color=MUTED),
            ]
        )
        return ft.Column(spacing=5, controls=controls)

    def nav_item(label: str, icon, active: bool, handler, badge: str | None = None):
        controls = [
            ft.Icon(icon, size=18, color=BRAND if active else MUTED),
            ft.Text(value=label, size=12, color=TEXT if active else MUTED, weight=ft.FontWeight.BOLD if active else None, expand=True),
        ]
        if badge:
            controls.append(chip(badge, "brand"))
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=11),
            bgcolor=SURFACE_3 if active else None,
            border_radius=10,
            on_click=handler,
            content=ft.Row(spacing=10, controls=controls),
        )

    def logout() -> None:
        nonlocal current_user_id, current_deal_id
        current_user_id = None
        current_deal_id = None
        render_login()

    def build_sidebar(active: str):
        user_id = require_user_id()
        profile = get_user_profile(user_id)
        wallet = get_wallet(user_id)
        unread = get_unread_notification_count(user_id)
        items = [
            ("overview", "Overview", ft.Icons.HOME, render_overview, None),
            ("marketplace", "Marketplace", ft.Icons.STORE, render_marketplace, None),
            ("portfolio", "Portfolio", ft.Icons.PIE_CHART, render_portfolio, None),
            ("liquidity", "Liquidity Intelligence", ft.Icons.ANALYTICS, render_liquidity, None),
            ("secondary", "Secondary Market", ft.Icons.SWAP_HORIZ, render_secondary, None),
            ("wallet", "Wallet", ft.Icons.ACCOUNT_BALANCE_WALLET, render_wallet, None),
            ("learn", "Learn", ft.Icons.MENU_BOOK, render_learn, None),
            ("notifications", "Notifications", ft.Icons.NOTIFICATIONS, render_notifications, str(unread) if unread else None),
            ("profile", "Profile / KYC", ft.Icons.PERSON, render_profile, None),
            ("demo_guide", "Judge Demo", ft.Icons.INFO, render_demo_guide, None),
        ]
        return ft.Container(
            width=240,
            bgcolor=SIDEBAR,
            padding=18,
            content=ft.Column(
                expand=True,
                controls=[
                    brand_lockup(),
                    ft.Text(value="PRIVATE MARKETS", color=MUTED, size=8, weight=ft.FontWeight.BOLD),
                    spectrum_rule(2),
                    ft.Container(height=16),
                    chip("FINAL HACKATHON BUILD", "brand"),
                    ft.Container(height=10),
                    *[
                        nav_item(label, icon, active == key, lambda e, fn=fn: fn(), badge)
                        for key, label, icon, fn, badge in items
                    ],
                    ft.Container(expand=True),
                    panel(
                        ft.Column(
                            spacing=5,
                            controls=[
                                ft.Text(value=profile.name, color=TEXT, weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(value=profile.email, color=MUTED, size=9),
                                ft.Text(value=f"Cash {_money(wallet)}", color=TEAL, size=11, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        padding=12,
                        bgcolor=HIGHLIGHT_SURFACE,
                    ),
                    ft.Container(height=8),
                    ft.Row(controls=[theme_toggle_button(), secondary_button("Logout", lambda e: logout(), ft.Icons.LOGOUT)]),
                ],
            ),
        )

    def build_mobile_nav(active: str):
        unread = get_unread_notification_count(require_user_id())
        entries = [
            ("overview", "Home", ft.Icons.HOME, render_overview),
            ("marketplace", "Market", ft.Icons.STORE, render_marketplace),
            ("portfolio", "Portfolio", ft.Icons.PIE_CHART, render_portfolio),
            ("liquidity", "Liquidity", ft.Icons.ANALYTICS, render_liquidity),
            ("secondary", "Resale", ft.Icons.SWAP_HORIZ, render_secondary),
            ("wallet", "Wallet", ft.Icons.ACCOUNT_BALANCE_WALLET, render_wallet),
            ("notifications", f"Alerts{f' {unread}' if unread else ''}", ft.Icons.NOTIFICATIONS, render_notifications),
            ("demo_guide", "Demo", ft.Icons.INFO, render_demo_guide),
        ]
        return ft.Container(
            bgcolor=SIDEBAR,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
            padding=8,
            content=ft.Row(
                wrap=True,
                spacing=6,
                controls=[
                    ft.Container(
                        padding=8,
                        bgcolor=SURFACE_3 if active == key else None,
                        border_radius=8,
                        on_click=lambda e, fn=fn: fn(),
                        content=ft.Row(
                            spacing=5,
                            controls=[
                                ft.Icon(icon, size=15, color=BRAND if active == key else MUTED),
                                ft.Text(value=label, size=10, color=TEXT if active == key else MUTED),
                            ],
                        ),
                    )
                    for key, label, icon, fn in entries
                ],
            ),
        )

    def build_shell(active: str, heading, body_controls: list):
        desktop = (page.width or 1440) >= 1050
        # ListView is used instead of a nested scrollable Column. This is more
        # reliable in the Flet iOS/Android clients, where touch scrolling can be
        # lost when an AUTO-scrolling Column is nested inside another expanded
        # Column. The same control also keeps desktop scrolling predictable.
        main = ft.Container(
            expand=True,
            padding=ft.Padding.all(28 if desktop else 16),
            content=ft.ListView(
                expand=True,
                spacing=18,
                controls=[
                    spectrum_rule(2),
                    ft.Row(
                        controls=[
                            heading,
                            ft.Container(expand=True),
                            chip("SIMULATED PROTOTYPE", "neutral"),
                        ],
                    ),
                    *body_controls,
                    ft.Container(height=6),
                    ft.Text(
                        value="Prototype only • simulated money, opportunities, KYC, bids and returns • no real financial transaction is processed.",
                        size=9,
                        color=MUTED,
                    ),
                    ft.Container(height=12),
                ],
            ),
        )
        if desktop:
            shell = ft.Row(expand=True, spacing=0, controls=[build_sidebar(active), main])
        else:
            shell = ft.Column(
                expand=True,
                spacing=8,
                controls=[
                    ft.Container(
                        padding=ft.Padding.only(left=16, right=16, top=12),
                        content=ft.Row(
                            controls=[
                                brand_lockup(compact=True),
                                ft.Container(expand=True),
                                theme_toggle_button(),
                                secondary_button("Profile", lambda e: render_profile(), ft.Icons.PERSON),
                                secondary_button("Logout", lambda e: logout(), ft.Icons.LOGOUT),
                            ]
                        ),
                    ),
                    ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=build_mobile_nav(active)),
                    main,
                ],
            )
        return ft.SafeArea(expand=True, content=shell)

    def display_view(active: str, heading, body_controls: list):
        page.clean()
        page.add(build_shell(active, heading, body_controls))

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def render_login() -> None:
        nonlocal current_user_id
        current_user_id = None
        set_view("login")
        email_field = ft.TextField(label="Email", width=390, filled=True, fill_color=SURFACE_2)
        password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            width=390,
            filled=True,
            fill_color=SURFACE_2,
        )

        def do_login(email: str, password: str):
            nonlocal current_user_id
            try:
                profile = authenticate_user(email, password)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            current_user_id = profile.id
            render_overview()

        def handle_login(e):
            do_login(email_field.value, password_field.value)

        page.clean()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.ListView(
                    expand=True,
                    padding=24,
                    spacing=0,
                    controls=[
                        ft.ResponsiveRow(
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                            ft.Container(
                                col={"xs": 12, "lg": 6},
                                padding=28,
                                content=ft.Column(
                                    spacing=14,
                                    controls=[
                                        brand_lockup(),
                                        spectrum_rule(3),
                                        chip("PROMETHEUS ONE • FINAL HACKATHON BUILD", "brand"),
                                        ft.Text(value="Private markets,", size=42, color=TEXT, weight=ft.FontWeight.BOLD),
                                        ft.Text(value="made accessible.", size=42, color=BLUE, weight=ft.FontWeight.BOLD),
                                        ft.Text(
                                            value="Fractional private-market access, structured resale infrastructure and explainable Liquidity Intelligence that helps investors understand the path back out.",
                                            size=16,
                                            color=MUTED,
                                        ),
                                        ft.Container(height=8),
                                        ft.ResponsiveRow(
                                            controls=[
                                                metric_card("Primary access", "R250+", "Illustrative unit prices", col={"xs": 12, "sm": 4}),
                                                metric_card("Deals", "5", "Cross-sector demo", col={"xs": 12, "sm": 4}),
                                                metric_card("Liquidity", "Predictive", "7/14/30-day forecasts", col={"xs": 12, "sm": 4}),
                                            ]
                                        ),
                                        panel(
                                            ft.Column(
                                                spacing=5,
                                                controls=[
                                                    ft.Text(value="CORE INNOVATION", size=10, color=VIOLET, weight=ft.FontWeight.BOLD),
                                                    ft.Text(value="Liquidity Intelligence forecasts sale probability, expected time-to-sale and pricing sensitivity using transparent simulated-data modelling.", color=TEXT, size=12),
                                                ],
                                            ),
                                            bgcolor=HIGHLIGHT_SURFACE,
                                        ),
                                    ],
                                ),
                            ),
                            ft.Container(
                                col={"xs": 12, "lg": 5},
                                content=panel(
                                    ft.Column(
                                        spacing=14,
                                        controls=[
                                            ft.Row(controls=[ft.Text(value="Sign in", size=26, color=TEXT, weight=ft.FontWeight.BOLD), ft.Container(expand=True), theme_toggle_button()]),
                                            ft.Text(value="Use the dedicated judge account for the complete showcase journey.", size=12, color=MUTED),
                                            email_field,
                                            password_field,
                                            primary_button("Sign in", handle_login, ft.Icons.LOGIN),
                                            ft.Divider(color=BORDER),
                                            primary_button("Open Judge Demo", lambda e: do_login(JUDGE_EMAIL, JUDGE_PASSWORD), ft.Icons.INFO),
                                            ft.Row(
                                                wrap=True,
                                                controls=[
                                                    secondary_button("Demo Buyer", lambda e: do_login(DEMO_EMAIL, DEMO_PASSWORD)),
                                                    secondary_button("Market Seller", lambda e: do_login(SELLER_EMAIL, SELLER_PASSWORD)),
                                                ],
                                            ),
                                            ft.TextButton(content="Create prototype account", on_click=lambda e: render_signup()),
                                            ft.Text(value="Judge: judge@prometheus.demo • PrometheusDemo26!", size=10, color=MUTED),
                                        ],
                                    ),
                                    padding=24,
                                ),
                            ),
                            ],
                        ),
                    ],
                ),
            )
        )

    def render_signup() -> None:
        nonlocal current_user_id
        set_view("signup")
        name_field = ft.TextField(label="Name", width=390, filled=True, fill_color=SURFACE_2)
        email_field = ft.TextField(label="Email", width=390, filled=True, fill_color=SURFACE_2)
        password_field = ft.TextField(label="Password (8+ characters)", password=True, can_reveal_password=True, width=390, filled=True, fill_color=SURFACE_2)
        risk_field = ft.TextField(label="Risk profile: Conservative, Balanced, or Growth", value="Balanced", width=390, filled=True, fill_color=SURFACE_2)

        def handle_signup(e):
            nonlocal current_user_id
            try:
                profile = create_user(name_field.value, email_field.value, password_field.value, risk_field.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            current_user_id = profile.id
            show_message("Prototype account created with R15,000 simulated cash. Complete demo KYC before investing.")
            render_overview()

        page.clean()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.ListView(
                    expand=True,
                    padding=24,
                    spacing=0,
                    controls=[
                        panel(
                            ft.Column(
                            spacing=14,
                            controls=[
                                ft.Row(controls=[brand_lockup(compact=True), ft.Container(expand=True), theme_toggle_button()]),
                                spectrum_rule(2),
                                ft.Text(value="Create prototype account", size=28, color=TEXT, weight=ft.FontWeight.BOLD),
                                ft.Text(value="Each user receives a separate wallet, ledger, portfolio, KYC state and notification stream.", size=12, color=MUTED),
                                name_field,
                                email_field,
                                password_field,
                                risk_field,
                                primary_button("Create account", handle_signup, ft.Icons.PERSON_ADD),
                                ft.TextButton(content="Back to sign in", on_click=lambda e: render_login()),
                            ],
                        ),
                            padding=28,
                        ),
                    ],
                ),
            )
        )

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def compact_deal_card(deal, col=None):
        return panel(
            ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        controls=[
                            chip(deal.sector.upper(), "neutral"),
                            ft.Container(expand=True),
                            chip(f"{deal.risk.upper()} RISK", status_tone(deal.risk)),
                        ]
                    ),
                    ft.Text(value=deal.name, size=18, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text(value=deal.blurb, size=11, color=MUTED, max_lines=3),
                    ft.ProgressBar(value=deal.funded_pct / 100, color=TEAL, bgcolor=SURFACE_3),
                    ft.Row(
                        controls=[
                            ft.Column(spacing=1, controls=[ft.Text(value="UNIT", size=9, color=MUTED), ft.Text(value=f"R{deal.unit_price:,.0f}", color=TEXT, weight=ft.FontWeight.BOLD)]),
                            ft.Container(expand=True),
                            ft.Column(spacing=1, controls=[ft.Text(value="FUNDED", size=9, color=MUTED), ft.Text(value=f"{deal.funded_pct:.0f}%", color=TEAL, weight=ft.FontWeight.BOLD)]),
                        ]
                    ),
                    secondary_button("Open Deal Room", lambda e, deal_id=deal.id: render_deal_detail(deal_id), ft.Icons.ARROW_FORWARD),
                ],
            ),
            col=col,
        )

    def render_overview() -> None:
        set_view("overview")
        user_id = require_user_id()
        profile = get_user_profile(user_id)
        wallet = get_wallet(user_id)
        portfolio = get_portfolio_total(user_id)
        intelligence = get_portfolio_intelligence(user_id)
        unread = get_unread_notification_count(user_id)
        revision = get_market_revision()
        featured = get_deals()[:3]
        notes = get_notifications(user_id, 4)

        diagnostics = [bullet(item) for item in intelligence.recommendations]
        if not diagnostics:
            diagnostics = [bullet("No portfolio diagnostics yet.")]

        body = [
            panel(
                ft.ResponsiveRow(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "lg": 8},
                            content=ft.Column(
                                spacing=9,
                                controls=[
                                    chip("PRIVATE MARKETS • MADE ACCESSIBLE", "brand"),
                                    ft.Text(value="One platform across the", size=34, color=TEXT, weight=ft.FontWeight.BOLD),
                                    ft.Text(value="investment journey.", size=34, color=BLUE, weight=ft.FontWeight.BOLD),
                                    ft.Text(value="Discover, understand, invest, track and resell simulated private-market positions through one institutional-style experience.", size=14, color=MUTED),
                                    ft.Row(
                                        wrap=True,
                                        controls=[
                                            primary_button("Explore Marketplace", lambda e: render_marketplace(), ft.Icons.STORE),
                                            secondary_button("Judge Demo Guide", lambda e: render_demo_guide(), ft.Icons.INFO),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "lg": 4},
                            content=panel(
                                ft.Column(
                                    spacing=7,
                                    controls=[
                                        ft.Text(value="YOUR ACCESS PROFILE", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                                        ft.Text(value=profile.risk_profile, size=24, color=TEXT, weight=ft.FontWeight.BOLD),
                                        ft.Text(value=f"KYC: {profile.kyc_status.replace('_', ' ').title()}", color=TEAL if profile.kyc_status == "verified" else AMBER, size=12),
                                        ft.Text(value="Access is paired with risk context, scenario analysis and portfolio diagnostics.", size=11, color=MUTED),
                                    ],
                                ),
                                bgcolor=HIGHLIGHT_SURFACE,
                            ),
                        ),
                    ],
                ),
                padding=24,
            ),
            ft.ResponsiveRow(
                controls=[
                    metric_card("Available cash", _money(wallet), "Ledger-derived balance", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Portfolio value", _money(portfolio), f"{intelligence.holding_count} active holding(s)", "positive", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Portfolio health", f"{intelligence.score}/100", intelligence.status, col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Market activity", str(revision.active_listings), f"active asks • {unread} unread alert(s)", col={"xs": 12, "sm": 6, "xl": 3}),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(
                            spacing=9,
                            controls=[
                                section_title("Portfolio Intelligence", "Transparent rules, not predictive AI."),
                                ft.Text(value=f"Largest sector: {intelligence.largest_sector} ({intelligence.largest_sector_pct:.1f}%)", color=TEXT, size=12),
                                ft.Text(value=f"High-risk exposure: {intelligence.high_risk_pct:.1f}%", color=TEXT, size=12),
                                ft.Text(value=f"Long lock-ins (>24m): {intelligence.long_lock_in_pct:.1f}%", color=TEXT, size=12),
                                ft.Text(value=f"Income exposure: {intelligence.income_exposure_pct:.1f}%", color=TEXT, size=12),
                                *diagnostics,
                                secondary_button("Open Portfolio", lambda e: render_portfolio()),
                            ],
                        ),
                        col={"xs": 12, "lg": 7},
                    ),
                    panel(
                        ft.Column(
                            spacing=8,
                            controls=[
                                section_title("Recent alerts", "Account, investment and market events."),
                                *[
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text(value=n.title, color=TEXT, weight=ft.FontWeight.BOLD, size=11),
                                            ft.Text(value=n.message, color=MUTED, size=10, max_lines=2),
                                        ],
                                    )
                                    for n in notes
                                ],
                                secondary_button("View Notifications", lambda e: render_notifications()),
                            ],
                        ),
                        col={"xs": 12, "lg": 5},
                    ),
                ]
            ),
            section_title("Featured opportunities", "Five simulated opportunities power the showcase; these three are highlighted."),
            ft.ResponsiveRow(controls=[compact_deal_card(d, {"xs": 12, "md": 6, "xl": 4}) for d in featured]),
        ]
        display_view("overview", page_heading(f"Welcome, {profile.name}", "Your private-market capital, risk and market activity at a glance.", "OVERVIEW"), body)

    # ------------------------------------------------------------------
    # Marketplace / Deal Room / Scenario Lab / Suitability
    # ------------------------------------------------------------------

    def render_marketplace() -> None:
        set_view("marketplace")
        deals = get_deals()
        body = [
            panel(
                ft.Column(
                    spacing=7,
                    controls=[
                        ft.Text(value="CURATED SIMULATED OPPORTUNITIES", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Five opportunities. Five sectors. One diligence workflow.", size=24, color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Open a Deal Room to inspect the thesis, risks, use of funds, capital timeline, suitability context, scenario analysis and secondary-market snapshot.", size=12, color=MUTED),
                    ],
                ),
                bgcolor=HIGHLIGHT_SURFACE,
            ),
            ft.ResponsiveRow(controls=[compact_deal_card(d, {"xs": 12, "md": 6, "xl": 4}) for d in deals]),
        ]
        display_view("marketplace", page_heading("Marketplace", "Fractional private-market opportunities denominated in ZAR.", "DISCOVER"), body)

    def render_deal_detail(deal_id: int) -> None:
        set_view("deal_room", deal_id)
        user_id = require_user_id()
        try:
            deal = get_deal(deal_id)
            book = get_order_book(deal_id)
            suitability = get_deal_suitability(user_id, deal_id)
        except PrometheusServiceError as exc:
            show_message(str(exc), error=True)
            render_marketplace()
            return

        units_field = ft.TextField(label="Units", value="1", width=130, filled=True, fill_color=SURFACE_2)
        total_text = ft.Text(value=f"Total {_money(deal.unit_price)}", color=TEXT, weight=ft.FontWeight.BOLD)

        def recalculate(e):
            try:
                units = max(0, int(units_field.value or "0"))
                total_text.value = f"Total {_money(units * deal.unit_price)}"
            except ValueError:
                total_text.value = "Total —"
            total_text.update()

        units_field.on_change = recalculate

        def handle_invest(e):
            try:
                result = invest_in_deal(user_id, deal.id, units_field.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message(f"Invested {_money(result.cost)} in {result.deal_name}. Wallet: {_money(result.wallet_balance)}.")
            render_portfolio()

        scenario_amount = ft.TextField(label="Investment (ZAR)", value="5000", width=190, filled=True, fill_color=SURFACE_2)
        scenario_shock = ft.TextField(label="Valuation change %", value="0", width=170, filled=True, fill_color=SURFACE_2)
        scenario_delay = ft.TextField(label="Exit delay months", value="0", width=170, filled=True, fill_color=SURFACE_2)
        scenario_output = ft.Column(spacing=4, controls=[ft.Text(value="Adjust assumptions and run the scenario.", color=MUTED, size=11)])

        def handle_scenario(e):
            try:
                result = run_scenario(deal.id, scenario_amount.value, scenario_shock.value, scenario_delay.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            sign = "+" if result.projected_gain >= 0 else "−"
            scenario_output.controls = [
                ft.Text(value=_money(result.projected_value), size=28, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Text(value=f"Illustrative change {sign}{_money(abs(result.projected_gain))}", color=TEAL if result.projected_gain >= 0 else RED, size=12),
                ft.Text(value=f"Static demo rate {result.annual_return_pct:.1f}% p.a. • base {result.horizon_months}m • delay +{result.exit_delay_months}m", color=MUTED, size=10),
                ft.Text(value=result.disclaimer, color=MUTED, size=9),
            ]
            scenario_output.update()

        timeline = []
        for i, m in enumerate(deal.milestones):
            timeline.append(
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(width=12, height=12, border_radius=6, bgcolor=BRAND if m.phase == "current" else SURFACE_3, border=ft.Border.all(1, BRAND)),
                                ft.Container(width=1, height=34, bgcolor=BORDER) if i < len(deal.milestones) - 1 else ft.Container(height=0),
                            ],
                        ),
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Row(controls=[ft.Text(value=m.title, color=TEXT, weight=ft.FontWeight.BOLD, size=12), chip(m.timing_label, "neutral")]),
                                ft.Text(value=m.description, color=MUTED, size=10),
                            ],
                            expand=True,
                        ),
                    ],
                )
            )

        bid = f"R{book.best_bid:,.2f}" if book.best_bid is not None else "—"
        ask = f"R{book.best_ask:,.2f}" if book.best_ask is not None else "—"
        caution_controls = [bullet(c) for c in suitability.cautions]

        left = ft.Container(
            col={"xs": 12, "lg": 8},
            content=ft.Column(
                spacing=16,
                controls=[
                    panel(
                        ft.Column(
                            spacing=9,
                            controls=[
                                ft.Row(wrap=True, controls=[chip(deal.sector.upper()), chip(deal.type.upper()), chip(f"{deal.risk.upper()} RISK", status_tone(deal.risk))]),
                                ft.Text(value=deal.name, size=31, color=TEXT, weight=ft.FontWeight.BOLD),
                                ft.Text(value=f"{deal.issuer} • {deal.geography}", color=BRAND, size=11),
                                ft.Text(value=deal.blurb, color=MUTED, size=13),
                            ],
                        ),
                        padding=22,
                    ),
                    ft.ResponsiveRow(
                        controls=[
                            metric_card("Unit price", _money(deal.unit_price), col={"xs": 6, "md": 3}),
                            metric_card("Funding", f"{deal.funded_pct:.1f}%", col={"xs": 6, "md": 3}),
                            metric_card("Lock-in", deal.lock_in, col={"xs": 6, "md": 3}),
                            metric_card("Bid / ask", f"{bid} / {ask}", "Indicative / executable", col={"xs": 6, "md": 3}),
                        ]
                    ),
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title("Deal Room", "Institutional-style diligence in plain language."),
                                ft.Text(value="INVESTMENT THESIS", size=9, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Text(value=deal.investment_thesis, color=TEXT, size=12),
                                ft.Text(value="USE OF FUNDS", size=9, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Text(value=deal.use_of_funds, color=MUTED, size=12),
                                ft.Text(value="KEY RISKS", size=9, color=BRAND, weight=ft.FontWeight.BOLD),
                                *[bullet(x.strip()) for x in deal.key_risks.split(";") if x.strip()],
                                ft.Text(value="SIMULATED DOCUMENT SET", size=9, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Text(value=deal.key_documents, color=MUTED, size=11),
                            ],
                        )
                    ),
                    panel(ft.Column(spacing=6, controls=[section_title("Capital Timeline", "What happens after capital is committed."), *timeline])),
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title("Scenario Lab", "Transparent what-if analysis — not a prediction engine."),
                                ft.Row(wrap=True, controls=[scenario_amount, scenario_shock, scenario_delay, primary_button("Run Scenario", handle_scenario, ft.Icons.CALCULATE)]),
                                panel(scenario_output, padding=14, bgcolor=HIGHLIGHT_SURFACE),
                            ],
                        )
                    ),
                ],
            ),
        )

        right = ft.Container(
            col={"xs": 12, "lg": 4},
            content=ft.Column(
                spacing=14,
                controls=[
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                ft.Text(value="INVESTMENT ORDER", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Text(value=_money(deal.unit_price), size=31, color=TEXT, weight=ft.FontWeight.BOLD),
                                ft.Text(value="per unit", color=MUTED, size=11),
                                units_field,
                                total_text,
                                primary_button("Invest", handle_invest, ft.Icons.TRENDING_UP),
                                ft.Text(value=f"Projected label: {deal.projected}. Returns are simulated and not guaranteed.", size=9, color=MUTED),
                            ],
                        ),
                        bgcolor=HIGHLIGHT_SURFACE,
                    ),
                    panel(
                        ft.Column(
                            spacing=8,
                            controls=[
                                ft.Text(value="SUITABILITY SNAPSHOT", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Row(controls=[chip(suitability.risk_fit.upper(), "positive" if suitability.risk_fit != "Above profile" else "danger"), chip(f"PROFILE: {suitability.risk_profile.upper()}")]),
                                ft.Text(value=suitability.summary, size=11, color=TEXT),
                                *caution_controls,
                                ft.Text(value="Educational rules-based context only; not financial advice or a recommendation.", size=9, color=MUTED),
                            ],
                        )
                    ),
                    panel(
                        ft.Column(
                            spacing=8,
                            controls=[
                                ft.Text(value="SECONDARY MARKET SNAPSHOT", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Row(controls=[ft.Column(controls=[ft.Text(value="BEST BID", size=9, color=MUTED), ft.Text(value=bid, color=TEAL, weight=ft.FontWeight.BOLD)]), ft.Container(expand=True), ft.Column(controls=[ft.Text(value="BEST ASK", size=9, color=MUTED), ft.Text(value=ask, color=TEXT, weight=ft.FontWeight.BOLD)])]),
                                ft.Text(value=f"{book.recent_traded_units} prototype units recorded in completed secondary trades.", size=10, color=MUTED),
                                secondary_button("Open Secondary Market", lambda e: render_secondary()),
                            ],
                        )
                    ),
                ],
            ),
        )

        body = [
            ft.TextButton(content="← Back to Marketplace", on_click=lambda e: render_marketplace()),
            ft.ResponsiveRow(spacing=16, run_spacing=16, controls=[left, right]),
        ]
        display_view("marketplace", page_heading("Deal Room", "Understand the opportunity before committing simulated capital.", "DILIGENCE"), body)

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    def render_portfolio() -> None:
        set_view("portfolio")
        user_id = require_user_id()
        holdings = get_holdings(user_id)
        intelligence = get_portfolio_intelligence(user_id)

        sector_values: dict[str, float] = {}
        for h in holdings:
            sector_values[h.deal.sector] = sector_values.get(h.deal.sector, 0.0) + float(h.cost_basis)
        total = max(1.0, intelligence.total_value)

        allocation_controls = []
        for sector, value in sorted(sector_values.items(), key=lambda x: x[1], reverse=True):
            pct = value / total
            allocation_controls.extend(
                [
                    ft.Row(controls=[ft.Text(value=sector, color=TEXT, size=11, expand=True), ft.Text(value=f"{pct*100:.1f}% • {_money(value)}", color=MUTED, size=10)]),
                    ft.ProgressBar(value=pct, color=TEAL, bgcolor=SURFACE_3),
                ]
            )

        holding_cards = []
        for h in holdings:
            holding_cards.append(
                panel(
                    ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Column(spacing=2, controls=[ft.Text(value=h.deal.name, color=TEXT, size=16, weight=ft.FontWeight.BOLD), ft.Text(value=f"{h.deal.sector} • {h.deal.type}", color=MUTED, size=10)], expand=True),
                                    chip(f"{h.deal.risk.upper()} RISK", status_tone(h.deal.risk)),
                                ]
                            ),
                            ft.Row(
                                controls=[
                                    ft.Column(controls=[ft.Text(value="UNITS", size=9, color=MUTED), ft.Text(value=str(h.units), color=TEXT, weight=ft.FontWeight.BOLD)]),
                                    ft.Column(controls=[ft.Text(value="VALUE", size=9, color=MUTED), ft.Text(value=_money(h.cost_basis), color=TEAL, weight=ft.FontWeight.BOLD)]),
                                    ft.Column(controls=[ft.Text(value="LOCK-IN", size=9, color=MUTED), ft.Text(value=h.deal.lock_in, color=TEXT, weight=ft.FontWeight.BOLD)]),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(value="Next capital milestones", size=9, color=BRAND, weight=ft.FontWeight.BOLD),
                            *[ft.Text(value=f"{'●' if m.phase == 'current' else '○'} {m.timing_label} — {m.title}", color=MUTED, size=9) for m in h.deal.milestones[:3]],
                            ft.Row(wrap=True, controls=[
                                secondary_button("Liquidity Passport", lambda e, deal_id=h.deal.id: render_liquidity(deal_id)),
                                secondary_button("Open Deal Room", lambda e, deal_id=h.deal.id: render_deal_detail(deal_id)),
                            ]),
                        ],
                    ),
                    col={"xs": 12, "lg": 6},
                )
            )

        body = [
            ft.ResponsiveRow(
                controls=[
                    metric_card("Portfolio value", _money(intelligence.total_value), col={"xs": 12, "sm": 6, "xl": 3}, tone="positive"),
                    metric_card("Health score", f"{intelligence.score}/100", intelligence.status, col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Sectors", str(intelligence.sector_count), "Diversification breadth", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("High-risk exposure", f"{intelligence.high_risk_pct:.1f}%", col={"xs": 12, "sm": 6, "xl": 3}),
                ]
            ),
            panel(ft.Row(wrap=True, controls=[
                ft.Column(spacing=2, controls=[ft.Text(value="PROMETHEUS LIQUIDITY INTELLIGENCE", color=VIOLET, size=10, weight=ft.FontWeight.BOLD), ft.Text(value="Stress-test exit potential across the portfolio and inspect a Liquidity Passport for each position.", color=MUTED, size=11)]),
                primary_button("Open Liquidity Intelligence", lambda e: render_liquidity(), ft.Icons.ANALYTICS),
            ]), bgcolor=HIGHLIGHT_SURFACE),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(spacing=8, controls=[section_title("Portfolio Intelligence", "Rules-based diagnostics — not investment advice."), *[bullet(x) for x in intelligence.recommendations]]),
                        col={"xs": 12, "lg": 7},
                    ),
                    panel(
                        ft.Column(spacing=6, controls=[section_title("Sector allocation", "Based on simulated cost-basis values."), *(allocation_controls or [ft.Text(value="No holdings yet.", color=MUTED)])]),
                        col={"xs": 12, "lg": 5},
                    ),
                ]
            ),
            section_title("Your holdings", "Each position includes the capital timeline established in its Deal Room."),
            ft.ResponsiveRow(controls=holding_cards) if holding_cards else panel(ft.Column(controls=[ft.Text(value="No holdings yet.", color=MUTED), primary_button("Browse Marketplace", lambda e: render_marketplace())])),
        ]
        display_view("portfolio", page_heading("Portfolio", "Understand concentration, risk, lock-ins and the journey of your private-market capital.", "TRACK"), body)

    # ------------------------------------------------------------------
    # Secondary market
    # ------------------------------------------------------------------

    def build_order_book_control(book):
        bids = list(book.bid_levels[:3])
        asks = list(book.ask_levels[:3])
        bid_rows = [ft.Row(controls=[ft.Text(value=f"R{x.price:,.2f}", color=TEAL, width=80), ft.Text(value=f"{x.units}u", color=MUTED), ft.Text(value=f"{x.orders} interest", color=MUTED, size=9)]) for x in bids]
        ask_rows = [ft.Row(controls=[ft.Text(value=f"R{x.price:,.2f}", color=TEXT, width=80), ft.Text(value=f"{x.units}u", color=MUTED), ft.Text(value=f"{x.orders} ask(s)", color=MUTED, size=9)]) for x in asks]
        spread = "—"
        if book.best_bid is not None and book.best_ask is not None and book.best_ask:
            spread = f"{((book.best_ask - book.best_bid) / book.best_ask) * 100:.1f}%"
        return panel(
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(controls=[ft.Column(spacing=1, controls=[ft.Text(value=book.deal_name, color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value=f"Indicative value R{book.indicative_value:,.2f}", size=9, color=MUTED)], expand=True), chip(f"SPREAD {spread}")]),
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Column(expand=True, controls=[ft.Text(value="INDICATIVE BIDS", size=9, color=TEAL, weight=ft.FontWeight.BOLD), *(bid_rows or [ft.Text(value="No bids", color=MUTED, size=10)])]),
                            ft.Column(expand=True, controls=[ft.Text(value="ACTIVE ASKS", size=9, color=RED, weight=ft.FontWeight.BOLD), *(ask_rows or [ft.Text(value="No asks", color=MUTED, size=10)])]),
                        ],
                    ),
                    ft.Text(value=f"Completed secondary volume: {book.recent_traded_units} unit(s)", size=9, color=MUTED),
                ],
            )
        )

    def make_listing_control(listing, user_id: int):
        own = listing.seller_id == user_id

        def handle_buy(e):
            try:
                result = buy_secondary_listing(user_id, listing.id)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message(f"Bought {result.units} units of {result.deal_name} for {_money(result.gross_amount)}. Trade {result.reference}.")
            render_secondary()

        return panel(
            ft.Row(
                wrap=True,
                controls=[
                    ft.Column(spacing=2, controls=[ft.Text(value=listing.deal.name, color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value=f"Seller: {listing.seller.name} • {listing.units} units", color=MUTED, size=10)]),
                    ft.Column(controls=[ft.Text(value="PRICE / UNIT", color=MUTED, size=8), ft.Text(value=f"R{float(listing.price_per_unit):,.2f}", color=TEXT, weight=ft.FontWeight.BOLD)]),
                    ft.Column(controls=[ft.Text(value="TOTAL", color=MUTED, size=8), ft.Text(value=_money(listing.total_value), color=TEAL, weight=ft.FontWeight.BOLD)]),
                    primary_button("Buy" if not own else "Your listing", handle_buy, disabled=own),
                ],
            ),
            padding=14,
        )

    def render_secondary() -> None:
        nonlocal live_market_column, live_market_status, last_market_revision
        set_view("secondary")
        user_id = require_user_id()
        holdings = get_holdings(user_id)
        my_listings = get_user_listings(user_id)
        trades = get_trade_history(user_id)
        deals = get_deals()
        active_listings = get_active_listings()
        last_market_revision = get_market_revision()

        live_market_status = ft.Text(value="Near-live refresh active • checking every 4 seconds", size=10, color=TEAL)
        live_market_column = ft.Column(
            spacing=10,
            controls=[
                ft.ResponsiveRow(controls=[ft.Container(col={"xs": 12, "lg": 6}, content=build_order_book_control(get_order_book(d.id))) for d in deals]),
                section_title("Executable active asks", "These are real listings inside the prototype database; indicative bids are simulated and non-binding."),
                *([make_listing_control(x, user_id) for x in active_listings] or [panel(ft.Text(value="No active resale asks.", color=MUTED))]),
            ],
        )

        create_controls = []
        for h in holdings:
            units_field = ft.TextField(label="Units", value="1", width=95, filled=True, fill_color=SURFACE_2)
            price_field = ft.TextField(label="Price / unit", value=f"{h.deal.unit_price:.0f}", width=135, filled=True, fill_color=SURFACE_2)

            def make_handler(deal_id, units_control, price_control):
                def handler(e):
                    try:
                        result = create_secondary_listing(user_id, deal_id, units_control.value, price_control.value)
                    except PrometheusServiceError as exc:
                        show_message(str(exc), error=True)
                        return
                    show_message(f"Listed {result.units} {result.deal_name} units for {_money(result.total_value)}.")
                    render_secondary()
                return handler

            create_controls.append(
                panel(
                    ft.Row(
                        wrap=True,
                        controls=[
                            ft.Column(spacing=2, controls=[ft.Text(value=h.deal.name, color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value=f"{h.units} available unit(s)", color=MUTED, size=10)]),
                            units_field,
                            price_field,
                            primary_button("List", make_handler(h.deal.id, units_field, price_field)),
                        ],
                    ),
                    padding=12,
                )
            )

        my_listing_controls = []
        for listing in my_listings:
            def make_cancel_handler(listing_id):
                def handle(e):
                    try:
                        result = cancel_secondary_listing(user_id, listing_id)
                    except PrometheusServiceError as exc:
                        show_message(str(exc), error=True)
                        return
                    show_message(f"Cancelled listing; {result.restored_units} unit(s) returned to your portfolio.")
                    render_secondary()
                return handle

            my_listing_controls.append(
                ft.Row(
                    wrap=True,
                    controls=[
                        ft.Text(value=listing.deal.name, color=TEXT, weight=ft.FontWeight.BOLD, width=260),
                        ft.Text(value=f"{listing.units} @ R{float(listing.price_per_unit):,.2f}", color=MUTED),
                        chip(listing.status.upper(), "positive" if listing.status == "sold" else "brand"),
                        secondary_button("Cancel", make_cancel_handler(listing.id), disabled=listing.status != "active"),
                    ],
                )
            )

        trade_controls = []
        for trade in trades[:10]:
            side = "BUY" if trade.buyer_id == user_id else "SELL"
            counterparty = trade.seller.name if side == "BUY" else trade.buyer.name
            trade_controls.append(
                ft.Row(
                    controls=[
                        chip(side, "positive" if side == "BUY" else "brand"),
                        ft.Text(value=trade.deal.name, color=TEXT, width=230),
                        ft.Text(value=f"{trade.units}u", color=MUTED),
                        ft.Text(value=_money(float(trade.gross_amount)), color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Text(value=f"Counterparty: {counterparty}", color=MUTED, size=9, expand=True),
                    ]
                )
            )

        body = [
            panel(ft.Row(wrap=True, controls=[ft.Column(spacing=2, controls=[ft.Text(value="FROM PRICE DISCOVERY TO EXIT INTELLIGENCE", color=VIOLET, size=10, weight=ft.FontWeight.BOLD), ft.Text(value="Use current simulated market depth to forecast sale probability and time-to-sale.", color=MUTED, size=10)]), primary_button("Open Liquidity Intelligence", lambda e: render_liquidity(), ft.Icons.ANALYTICS)]), padding=12, bgcolor=HIGHLIGHT_SURFACE),
            panel(ft.Row(controls=[live_market_status, ft.Container(expand=True), chip("INDICATIVE BIDS ≠ EXECUTABLE", "neutral")]), padding=12, bgcolor=HIGHLIGHT_SURFACE),
            live_market_column,
            ft.Divider(color=BORDER),
            section_title("List your holdings", "Units are reserved when listed so they cannot be double-sold."),
            *(create_controls or [panel(ft.Text(value="No available holdings to list.", color=MUTED))]),
            ft.Divider(color=BORDER),
            section_title("My listings", "Cancel an active listing to return reserved units to your portfolio."),
            panel(ft.Column(spacing=10, controls=my_listing_controls or [ft.Text(value="No listings yet.", color=MUTED)])),
            section_title("Trade history", "Buyer, seller, cash and ownership settle atomically in the service layer."),
            panel(ft.Column(spacing=10, controls=trade_controls or [ft.Text(value="No completed trades yet.", color=MUTED)])),
        ]
        display_view("secondary", page_heading("Secondary Market", "Price discovery and user-to-user resale infrastructure for simulated private-market units.", "CONTROL / EXIT"), body)

    async def market_refresh_loop():
        nonlocal last_market_revision
        while True:
            await asyncio.sleep(4)
            if current_user_id is None or current_view != "secondary" or live_market_column is None:
                continue
            try:
                revision = await asyncio.to_thread(get_market_revision)
                if revision == last_market_revision:
                    if live_market_status is not None:
                        live_market_status.value = f"Near-live refresh active • checked {datetime.now().strftime('%H:%M:%S')}"
                        live_market_status.update()
                    continue
                listings = await asyncio.to_thread(get_active_listings)
                deals = await asyncio.to_thread(get_deals)
                books = [await asyncio.to_thread(get_order_book, d.id) for d in deals]
                user_id = current_user_id
                live_market_column.controls = [
                    ft.ResponsiveRow(controls=[ft.Container(col={"xs": 12, "lg": 6}, content=build_order_book_control(book)) for book in books]),
                    section_title("Executable active asks", "Market changed; active asks were refreshed from the prototype database."),
                    *([make_listing_control(x, user_id) for x in listings] or [panel(ft.Text(value="No active resale asks.", color=MUTED))]),
                ]
                live_market_column.update()
                if live_market_status is not None:
                    live_market_status.value = f"Market changed • refreshed {datetime.now().strftime('%H:%M:%S')}"
                    live_market_status.update()
                last_market_revision = revision
            except Exception:
                if live_market_status is not None:
                    live_market_status.value = "Near-live refresh temporarily unavailable; manual navigation still works."
                    live_market_status.update()

    # ------------------------------------------------------------------
    # Wallet / ledger
    # ------------------------------------------------------------------

    def render_wallet() -> None:
        set_view("wallet")
        user_id = require_user_id()
        balance = get_wallet(user_id)
        transactions = get_wallet_transactions(user_id)
        amount_field = ft.TextField(label="Amount (ZAR)", value="1000", width=180, filled=True, fill_color=SURFACE_2)

        def handle_deposit(e):
            try:
                result = deposit_funds(user_id, amount_field.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message(f"Deposited {_money(result.amount)}. Wallet: {_money(result.wallet_balance)}.")
            render_wallet()

        def handle_withdraw(e):
            try:
                result = withdraw_funds(user_id, amount_field.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message(f"Withdrew {_money(result.amount)}. Wallet: {_money(result.wallet_balance)}.")
            render_wallet()

        rows = []
        for tx in transactions:
            amount = float(tx.amount)
            positive = amount >= 0
            rows.append(
                ft.Row(
                    controls=[
                        ft.Container(width=8, height=8, border_radius=4, bgcolor=TEAL if positive else BRAND),
                        ft.Column(spacing=1, controls=[ft.Text(value=tx.description, color=TEXT, weight=ft.FontWeight.BOLD, size=11), ft.Text(value=f"{tx.created_at.strftime('%d %b %Y, %H:%M')} • {tx.transaction_type.replace('_', ' ').title()} • {tx.reference or '—'}", color=MUTED, size=9)], expand=True),
                        ft.Text(value=f"{'+' if positive else '−'}R{abs(amount):,.2f}", color=TEAL if positive else TEXT, weight=ft.FontWeight.BOLD),
                        chip(tx.status.upper(), "positive" if tx.status == "completed" else "brand"),
                    ]
                )
            )

        body = [
            ft.ResponsiveRow(
                controls=[
                    metric_card("Available cash", _money(balance), "Sum of completed ledger entries", "positive", col={"xs": 12, "lg": 5}),
                    panel(
                        ft.Column(
                            spacing=9,
                            controls=[
                                ft.Text(value="SIMULATED CASH MOVEMENT", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                                ft.Row(wrap=True, controls=[amount_field, primary_button("Deposit", handle_deposit, ft.Icons.DOWNLOAD), secondary_button("Withdraw", handle_withdraw, ft.Icons.UPLOAD)]),
                                ft.Text(value="Prototype only. No bank, card or payment rail is connected.", size=9, color=MUTED),
                            ],
                        ),
                        col={"xs": 12, "lg": 7},
                    ),
                ]
            ),
            section_title("Wallet ledger", "Every simulated Rand movement is traceable; balances are derived from ledger entries."),
            panel(ft.Column(spacing=11, controls=rows or [ft.Text(value="No wallet activity yet.", color=MUTED)])),
        ]
        display_view("wallet", page_heading("Wallet & Activity", "A ledger-first wallet designed for traceability rather than mutable balances.", "MONEY MOVEMENT"), body)

    # ------------------------------------------------------------------
    # Learn / money confidence
    # ------------------------------------------------------------------

    def render_learn() -> None:
        set_view("learn")
        modules = [
            ("01", "Private Markets 101", "Private-market assets are not continuously traded on a public exchange. Access, information and exit mechanics can differ materially from listed shares."),
            ("02", "Risk & projected returns", "Targets and projected returns are not guarantees. Investors should distinguish fixed contractual cash flows from target or unrealised growth assumptions."),
            ("03", "Understanding lock-ins", "A stated lock-in describes how long capital may be committed. Secondary-market availability does not guarantee an early exit."),
            ("04", "Secondary-market mechanics", "Prometheus reserves listed units, settles buyer/seller ownership atomically and records both sides of the simulated cash movement."),
        ]
        body = [
            panel(
                ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text(value="MONEY CONFIDENCE", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Access is useful only when investors understand what they are accessing.", size=25, color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Prometheus embeds plain-language education into the investment journey rather than separating learning from decision-making.", color=MUTED, size=12),
                    ],
                ),
                bgcolor=HIGHLIGHT_SURFACE,
            ),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(
                            spacing=8,
                            controls=[chip(num, "brand"), ft.Text(value=title, size=18, color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value=desc, color=MUTED, size=11)],
                        ),
                        col={"xs": 12, "md": 6},
                    )
                    for num, title, desc in modules
                ]
            ),
            panel(
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text(value="RESPONSIBLE PROTOTYPE DISCLOSURE", size=10, color=BRAND, weight=ft.FontWeight.BOLD),
                        bullet("All investments, balances, bids, returns and KYC states in this build are simulated."),
                        bullet("Prometheus One is not an authorised live investment service and does not process real money."),
                        bullet("Scenario Lab and Portfolio Intelligence provide educational context, not financial advice."),
                    ],
                )
            ),
        ]
        display_view("learn", page_heading("Learn", "Private-market concepts embedded into the product journey.", "UNDERSTAND"), body)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def render_notifications() -> None:
        set_view("notifications")
        user_id = require_user_id()
        notifications = get_notifications(user_id)

        def handle_mark_all(e):
            count = mark_all_notifications_read(user_id)
            show_message(f"Marked {count} notification(s) as read.")
            render_notifications()

        rows = []
        for n in notifications:
            def make_read_handler(notification_id):
                def handle(e):
                    try:
                        mark_notification_read(user_id, notification_id)
                    except PrometheusServiceError as exc:
                        show_message(str(exc), error=True)
                        return
                    render_notifications()
                return handle

            rows.append(
                panel(
                    ft.Row(
                        controls=[
                            ft.Container(width=9, height=9, border_radius=5, bgcolor=BRAND if not n.is_read else SURFACE_3),
                            ft.Column(spacing=2, controls=[ft.Text(value=n.title, color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value=n.message, color=MUTED, size=11), ft.Text(value=f"{n.created_at.strftime('%d %b %Y, %H:%M')} • {n.category.title()} • {n.reference or '—'}", color=MUTED, size=9)], expand=True),
                            secondary_button("Mark read", make_read_handler(n.id), disabled=n.is_read),
                        ]
                    ),
                    padding=14,
                )
            )
        body = [
            ft.Row(controls=[ft.Text(value=f"{get_unread_notification_count(user_id)} unread", color=BRAND, weight=ft.FontWeight.BOLD), ft.Container(expand=True), secondary_button("Mark all read", handle_mark_all)]),
            *rows,
        ]
        display_view("notifications", page_heading("Notifications", "Investment, account and market events stay attached to the user who generated them.", "EVENTS"), body)

    # ------------------------------------------------------------------
    # Profile / KYC / security audit
    # ------------------------------------------------------------------

    def render_profile() -> None:
        set_view("profile")
        user_id = require_user_id()
        profile = get_user_profile(user_id)
        audits = get_audit_events(user_id, 20)
        name_field = ft.TextField(label="Name", value=profile.name, width=350, filled=True, fill_color=SURFACE_2)
        risk_field = ft.TextField(label="Risk profile", value=profile.risk_profile, width=350, filled=True, fill_color=SURFACE_2)

        def handle_save(e):
            try:
                updated = update_user_profile(user_id, name_field.value, risk_field.value)
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message(f"Profile updated. Risk profile: {updated.risk_profile}.")
            render_profile()

        def handle_kyc(e):
            try:
                set_demo_kyc_status(user_id, "verified")
            except PrometheusServiceError as exc:
                show_message(str(exc), error=True)
                return
            show_message("Demo KYC marked verified. No real identity check was performed.")
            render_profile()

        audit_rows = [
            ft.Row(
                controls=[
                    ft.Text(value=a.created_at.strftime("%d %b %H:%M"), color=MUTED, size=9, width=100),
                    chip(a.event_type.replace("_", " ").upper(), "neutral"),
                    ft.Text(value=a.description, color=MUTED, size=10, expand=True),
                ]
            )
            for a in audits
        ]

        body = [
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title("Investor profile", "Profile state is used by the rules-based suitability context."),
                                ft.Text(value=f"Email: {profile.email}", color=MUTED, size=11),
                                ft.Row(controls=[chip(f"KYC {profile.kyc_status.upper()}", "positive" if profile.kyc_status == "verified" else "brand"), chip(profile.risk_profile.upper(), "neutral")]),
                                name_field,
                                risk_field,
                                ft.Row(wrap=True, controls=[primary_button("Save Profile", handle_save), secondary_button("Complete Demo KYC", handle_kyc)]),
                                ft.Divider(color=BORDER),
                                ft.Row(
                                    wrap=True,
                                    controls=[
                                        secondary_button("Logout of Prometheus One", lambda e: logout(), ft.Icons.LOGOUT),
                                        ft.Text(value="Ends the current local app session and returns to sign in.", color=MUTED, size=9),
                                    ],
                                ),
                                ft.Text(value="KYC is simulated and no identity documents are collected.", color=MUTED, size=9),
                            ],
                        ),
                        col={"xs": 12, "lg": 6},
                    ),
                    panel(
                        ft.Column(
                            spacing=7,
                            controls=[
                                section_title("Security controls", "Prototype SSDLC controls already implemented."),
                                bullet("PBKDF2-HMAC-SHA256 salted password hashing"),
                                bullet("Temporary account lock after repeated failed sign-ins"),
                                bullet("Input limits and service-layer business validation"),
                                bullet("Per-user ownership boundaries and audit events"),
                                bullet("Atomic secondary-market settlement with rollback"),
                                bullet("Append-only wallet ledger used as the balance source of truth"),
                            ],
                        ),
                        col={"xs": 12, "lg": 6},
                    ),
                ]
            ),
            section_title("Recent security / activity audit", "User-specific prototype audit events."),
            panel(ft.Column(spacing=8, controls=audit_rows or [ft.Text(value="No audit events yet.", color=MUTED)])),
        ]
        display_view("profile", page_heading("Profile / KYC / Security", "Identity state, risk profile and transparent security controls.", "TRUST"), body)

    # ------------------------------------------------------------------
    # Judge demo guide
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Prometheus Liquidity Intelligence
    # ------------------------------------------------------------------

    def render_liquidity(deal_id: int | None = None, proposed_price=None, target_days: int = 14) -> None:
        user_id = require_user_id()
        holdings = get_holdings(user_id)
        if not holdings:
            set_view("liquidity")
            display_view(
                "liquidity",
                page_heading("Liquidity Intelligence", "Forecast simulated exit conditions before listing.", "EXIT INTELLIGENTLY"),
                [panel(ft.Column(controls=[ft.Text(value="No holdings yet.", color=TEXT, weight=ft.FontWeight.BOLD), ft.Text(value="Invest in a marketplace opportunity first to generate a Liquidity Passport.", color=MUTED), primary_button("Browse Marketplace", lambda e: render_marketplace())]))],
            )
            return

        selected_id = int(deal_id or current_deal_id or holdings[0].deal.id)
        if selected_id not in {h.deal.id for h in holdings}:
            selected_id = holdings[0].deal.id
        set_view("liquidity", selected_id)

        try:
            snapshot = get_liquidity_snapshot(user_id, selected_id, proposed_price)
            portfolio_liq = get_portfolio_liquidity(user_id)
            validation = get_liquidity_model_validation()
            model_card = get_liquidity_model_card()
            exit_plan = get_exit_goal_plan(user_id, selected_id, target_days)
        except PrometheusServiceError as exc:
            show_message(str(exc), error=True)
            return

        forecast = snapshot.forecast
        reference_snapshot = get_liquidity_snapshot(user_id, selected_id, snapshot.reference_price)
        score_delta = forecast.liquidity_score - reference_snapshot.forecast.liquidity_score
        p30_delta = forecast.probability_30d - reference_snapshot.forecast.probability_30d
        curve = [
            get_liquidity_snapshot(user_id, selected_id, snapshot.reference_price * multiplier)
            for multiplier in (0.92, 0.96, 1.00, 1.04, 1.08)
        ]
        price_field = ft.TextField(
            label="Proposed listing price / unit",
            value=f"{snapshot.proposed_price:.2f}",
            width=220,
            filled=True,
            fill_color=SURFACE_2,
        )

        def simulate(e=None):
            render_liquidity(selected_id, price_field.value, target_days)

        def quick_price(multiplier: float):
            return lambda e: render_liquidity(selected_id, snapshot.reference_price * multiplier, target_days)

        def target_handler(days: int):
            return lambda e: render_liquidity(selected_id, snapshot.proposed_price, days)

        holding_buttons = []
        for holding in holdings:
            active = holding.deal.id == selected_id
            holding_buttons.append(
                ft.Container(
                    padding=10,
                    bgcolor=SURFACE_3 if active else SURFACE_2,
                    border_radius=9,
                    on_click=lambda e, did=holding.deal.id: render_liquidity(did),
                    content=ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(value=holding.deal.name, color=TEXT, size=11, weight=ft.FontWeight.BOLD),
                            ft.Text(value=f"{holding.units} units • {_money(holding.cost_basis)}", color=VIOLET if active else MUTED, size=9),
                        ],
                    ),
                )
            )

        probability_controls = []
        for label, pct in (("7 DAYS", forecast.probability_7d), ("14 DAYS", forecast.probability_14d), ("30 DAYS", forecast.probability_30d)):
            probability_controls.append(
                panel(
                    ft.Column(
                        spacing=7,
                        controls=[
                            ft.Text(value=label, color=MUTED, size=9, weight=ft.FontWeight.BOLD),
                            ft.Text(value=f"{pct:.1f}%", color=VIOLET, size=28, weight=ft.FontWeight.BOLD),
                            ft.ProgressBar(value=pct / 100.0, color=VIOLET, bgcolor=SURFACE_3),
                            ft.Text(value="Modeled probability of sale within horizon", color=MUTED, size=9),
                        ],
                    ),
                    col={"xs": 12, "md": 4},
                )
            )

        ladder_controls = []
        for label, pct in portfolio_liq.ladder:
            ladder_controls.extend([
                ft.Row(controls=[ft.Text(value=label, color=TEXT, size=10, expand=True), ft.Text(value=f"{pct:.1f}%", color=MUTED, size=10)]),
                ft.ProgressBar(value=pct / 100.0, color=CYAN, bgcolor=SURFACE_3),
            ])

        price_curve_controls = []
        for curve_snap in curve:
            pct = curve_snap.forecast.probability_30d
            price_curve_controls.extend([
                ft.Row(controls=[
                    ft.Text(value=_money(curve_snap.proposed_price), color=TEXT, size=10, width=105),
                    ft.ProgressBar(value=pct / 100.0, color=VIOLET, bgcolor=SURFACE_3, expand=True),
                    ft.Text(value=f"{pct:.1f}%", color=MUTED, size=10, width=55),
                ]),
            ])

        market_depth = ft.ResponsiveRow(
            controls=[
                metric_card("Best bid", _money(snapshot.best_bid) if snapshot.best_bid is not None else "—", f"{snapshot.visible_bid_units} visible bid units", col={"xs": 12, "sm": 6}),
                metric_card("Best ask", _money(snapshot.best_ask) if snapshot.best_ask is not None else "—", f"{snapshot.visible_ask_units} visible ask units", col={"xs": 12, "sm": 6}),
            ]
        )

        body = [
            panel(
                ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(wrap=True, controls=[chip("PROMETHEUS LIQUIDITY INTELLIGENCE", "brand"), chip("SIMULATED DATA", "neutral"), chip(f"CONFIDENCE: {forecast.confidence.upper()}", "positive" if forecast.confidence == "High" else "neutral")]),
                        ft.Text(value="Most investment platforms focus on getting investors in. Prometheus One also helps them understand the path back out.", color=TEXT, size=17, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Forecasts are decision-support estimates, not guarantees or financial advice.", color=MUTED, size=10),
                    ],
                ),
                bgcolor=HIGHLIGHT_SURFACE,
            ),
            section_title("Choose a position", "Each owned asset receives its own Liquidity Passport."),
            ft.Row(wrap=True, spacing=8, controls=holding_buttons),
            ft.ResponsiveRow(
                controls=[
                    metric_card("Liquidity Score", f"{forecast.liquidity_score}/100", f"{forecast.demand_signal.title()} demand signal", tone="positive" if forecast.liquidity_score >= 65 else "neutral", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Expected time-to-sale", f"{forecast.expected_days_low}–{forecast.expected_days_high} days", "Modeled range under current inputs", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Demand signal", forecast.demand_signal, f"{snapshot.market_observations} market observations", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Data quality", forecast.data_quality, "Confidence is shown explicitly", col={"xs": 12, "sm": 6, "xl": 3}),
                ]
            ),
            section_title("Sale probability", "Probability increases with more competitive pricing and stronger simulated demand."),
            ft.ResponsiveRow(controls=probability_controls),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title("Interactive pricing simulator", "Change the proposed price and recalculate the exit forecast."),
                                ft.Text(value=f"Reference value: {_money(snapshot.reference_price)}", color=MUTED, size=10),
                                price_field,
                                ft.Row(wrap=True, controls=[primary_button("Run simulation", simulate, ft.Icons.ANALYTICS), secondary_button("−5%", quick_price(0.95)), secondary_button("Reference", quick_price(1.00)), secondary_button("+5%", quick_price(1.05))]),
                                ft.Divider(color=BORDER),
                                ft.Row(wrap=True, controls=[chip(forecast.pricing_label.upper(), "brand"), ft.Text(value=forecast.pricing_guidance, color=MUTED, size=10)]),
                            ],
                        ),
                        col={"xs": 12, "lg": 7},
                    ),
                    panel(
                        ft.Column(
                            spacing=8,
                            controls=[
                                section_title("Exit Goal Planner", "Choose how quickly you would like to explore an exit."),
                                ft.Row(wrap=True, controls=[secondary_button("7 days", target_handler(7)), secondary_button("14 days", target_handler(14)), secondary_button("30 days", target_handler(30))]),
                                ft.Text(value=f"Target: {exit_plan.target_days} days", color=VIOLET, size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(value=f"Indicative range: {_money(exit_plan.suggested_price_low)}–{_money(exit_plan.suggested_price_high)}", color=TEXT, size=15, weight=ft.FontWeight.BOLD),
                                ft.Text(value=f"Modeled probability: {exit_plan.estimated_probability:.1f}%", color=TEAL, size=11),
                                ft.Text(value=exit_plan.note, color=MUTED, size=9),
                            ],
                        ),
                        col={"xs": 12, "lg": 5},
                    ),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(spacing=7, controls=[
                            section_title("Why did the score change?", "Comparison with the asset's reference-price forecast."),
                            ft.Text(value=f"Liquidity Score: {score_delta:+d} points", color=TEAL if score_delta >= 0 else AMBER, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(value=f"30-day sale probability: {p30_delta:+.1f} percentage points", color=TEAL if p30_delta >= 0 else AMBER, size=12),
                            ft.Text(value="The change is driven primarily by the proposed price input; demand, spread, trading activity and risk remain visible in the factor explanation below.", color=MUTED, size=10),
                        ]),
                        col={"xs": 12, "lg": 5},
                    ),
                    panel(
                        ft.Column(spacing=7, controls=[section_title("Price / Liquidity Curve", "30-day modeled sale probability across five price points."), *price_curve_controls]),
                        col={"xs": 12, "lg": 7},
                    ),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    panel(
                        ft.Column(spacing=7, controls=[section_title("Why this score?", "Explainability is part of the product, not a hidden model detail."), ft.Text(value="POSITIVE FACTORS", color=TEAL, size=9, weight=ft.FontWeight.BOLD), *[bullet(x, TEAL) for x in forecast.positive_factors], ft.Text(value="CONSTRAINTS", color=AMBER, size=9, weight=ft.FontWeight.BOLD), *[bullet(x, AMBER) for x in forecast.negative_factors]]),
                        col={"xs": 12, "lg": 7},
                    ),
                    panel(ft.Column(spacing=8, controls=[section_title("Market depth", "Current prototype order-book signals feeding the forecast."), market_depth, ft.Text(value=f"Proposed price: {_money(snapshot.proposed_price)} • Holding: {snapshot.holding_units} units", color=MUTED, size=10)]), col={"xs": 12, "lg": 5}),
                ]
            ),
            section_title("Portfolio Liquidity Stress Test", "What proportion of the portfolio may reasonably become liquid under modeled horizons?"),
            ft.ResponsiveRow(
                controls=[
                    metric_card("Portfolio liquidity", f"{portfolio_liq.weighted_score}/100", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("7-day potential", f"{portfolio_liq.liquid_7d_pct:.1f}%", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("30-day potential", f"{portfolio_liq.liquid_30d_pct:.1f}%", col={"xs": 12, "sm": 6, "xl": 3}),
                    metric_card("Concentration risk", portfolio_liq.concentration_risk, f"{portfolio_liq.illiquid_30d_pct:.1f}% modeled outside 30d", col={"xs": 12, "sm": 6, "xl": 3}),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    panel(ft.Column(spacing=7, controls=[section_title("Liquidity Ladder", "Portfolio value grouped by modeled exit horizon."), *ladder_controls]), col={"xs": 12, "lg": 6}),
                    panel(ft.Column(spacing=7, controls=[section_title("Stress-test summary", "Portfolio-level liquidity rather than position-level certainty."), ft.Text(value=portfolio_liq.summary, color=TEXT, size=12), ft.Text(value=f"90-day modeled potential: {portfolio_liq.liquid_90d_pct:.1f}%", color=CYAN, size=16, weight=ft.FontWeight.BOLD)]), col={"xs": 12, "lg": 6}),
                ]
            ),
            section_title("Transparency Centre", "How the model works, how it was tested and where it should not be trusted."),
            ft.ResponsiveRow(
                controls=[
                    panel(ft.Column(spacing=7, controls=[section_title("Held-out simulated backtest", "Validation dataset is separate from model training data."), metric_card("Model accuracy", f"{validation.model_accuracy:.1f}%", f"Baseline {validation.baseline_accuracy:.1f}%", tone="positive"), ft.Text(value=f"Brier score: {validation.brier_score:.3f} • held-out samples: {validation.sample_size}", color=MUTED, size=10)]), col={"xs": 12, "lg": 5}),
                    panel(ft.Column(spacing=6, controls=[section_title(model_card["name"], model_card["method"]), ft.Text(value=model_card["purpose"], color=TEXT, size=11), ft.Text(value="DATA", color=VIOLET, size=9, weight=ft.FontWeight.BOLD), ft.Text(value=model_card["data"], color=MUTED, size=10), ft.Text(value="LIMITATIONS", color=AMBER, size=9, weight=ft.FontWeight.BOLD), *[bullet(x, AMBER) for x in model_card["limitations"]]]), col={"xs": 12, "lg": 7}),
                ]
            ),
        ]
        display_view("liquidity", page_heading("Liquidity Intelligence", "Forecast sale probability, time-to-sale and pricing sensitivity before you list.", "EXIT INTELLIGENTLY"), body)

    # ------------------------------------------------------------------
    # Judge demo guide
    # ------------------------------------------------------------------

    def render_demo_guide() -> None:
        set_view("demo_guide")
        profile = get_user_profile(require_user_id())
        steps = [
            ("01", "Marketplace → Deal Room", "Open a private-market opportunity and show the thesis, risks, documents, capital timeline and suitability context.", render_marketplace),
            ("02", "Invest", "Demonstrate fractional participation and the ledger-backed ownership flow.", render_marketplace),
            ("03", "Portfolio Intelligence", "Show diversification, concentration, risk exposure and capital timelines across the seeded judge portfolio.", render_portfolio),
            ("04", "Secondary Market", "Show executable asks, indicative bids and atomic buyer/seller settlement.", render_secondary),
            ("05", "Liquidity Intelligence", "Change a proposed sale price and show Liquidity Score, 7/14/30-day probabilities, time-to-sale, pricing guidance and explainability.", render_liquidity),
            ("06", "Liquidity Passport + Stress Test", "Show position-level factors, portfolio liquidity horizons, concentration risk and the Transparency Centre.", render_liquidity),
        ]
        body = [
            panel(
                ft.Column(
                    spacing=7,
                    controls=[
                        chip("PROMETHEUS ONE • JUDGE DEMO", "brand"),
                        ft.Text(value=f"Recommended journey for {profile.name}", size=25, color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Text(value="The app is designed to pitch itself: Access → Understand → Trade → Exit Intelligently.", color=MUTED, size=12),
                        ft.Text(value="Credentials: judge@prometheus.demo / PrometheusDemo26!", color=TEAL, size=11, weight=ft.FontWeight.BOLD),
                    ],
                ),
                bgcolor=HIGHLIGHT_SURFACE,
            ),
            *[
                panel(
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            chip(num, "brand"),
                            ft.Column(spacing=3, controls=[ft.Text(value=title, color=TEXT, size=15, weight=ft.FontWeight.BOLD), ft.Text(value=desc, color=MUTED, size=11)], expand=True),
                            secondary_button("Open", lambda e, fn=fn: fn()),
                        ],
                    ),
                    padding=14,
                )
                for num, title, desc, fn in steps
            ],
            panel(
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text(value="THE V7 DIFFERENTIATOR", size=10, color=VIOLET, weight=ft.FontWeight.BOLD),
                        ft.Text(value="Prometheus One does not stop at access — it models the path back out.", size=17, color=TEXT, weight=ft.FontWeight.BOLD),
                        bullet("Explainable Liquidity Score and 7/14/30-day sale probability"),
                        bullet("Expected time-to-sale and interactive pricing sensitivity"),
                        bullet("Demand signal, Liquidity Passport and portfolio stress testing"),
                        bullet("Held-out simulated backtesting, confidence and transparent limitations"),
                    ],
                )
            ),
        ]
        display_view("demo_guide", page_heading("Judge Demo Guide", "A repeatable path through Prometheus One's strongest product evidence.", "SHOWCASE"), body)

    # ------------------------------------------------------------------
    # Responsive rerender
    # ------------------------------------------------------------------

    def rerender_current():
        if current_user_id is None:
            if current_view == "signup":
                render_signup()
            else:
                render_login()
            return
        mapping = {
            "overview": render_overview,
            "marketplace": render_marketplace,
            "portfolio": render_portfolio,
            "liquidity": render_liquidity,
            "secondary": render_secondary,
            "wallet": render_wallet,
            "learn": render_learn,
            "notifications": render_notifications,
            "profile": render_profile,
            "demo_guide": render_demo_guide,
        }
        if current_view == "deal_room" and current_deal_id is not None:
            render_deal_detail(current_deal_id)
        elif current_view == "liquidity" and current_deal_id is not None:
            render_liquidity(current_deal_id)
        else:
            mapping.get(current_view, render_overview)()

    def handle_resize(e):
        rerender_current()

    page.on_resize = handle_resize
    page.run_task(market_refresh_loop)
    render_login()


if __name__ == "__main__":
    init_database()
    seed_demo_data()
    ft.run(main)
