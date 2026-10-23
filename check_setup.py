"""Small setup diagnostic for Prometheus One V7."""

import sys


def main():
    print(f"Python: {sys.version.split()[0]}")
    try:
        import flet
        print(f"Flet: {getattr(flet, '__version__', 'installed')}")
        for name in ("run", "Button", "TextField", "Page"):
            if not hasattr(flet, name):
                raise RuntimeError(f"Flet is missing expected 1.x API: {name}")
    except Exception as exc:
        print(f"FAIL — Flet check: {exc}")
        raise SystemExit(1)

    try:
        from database import init_database
        from seed import seed_demo_data
        from services import get_deals, get_market_revision, get_wallet, authenticate_user, get_liquidity_snapshot, get_portfolio_liquidity
        from seed import DEMO_EMAIL, DEMO_PASSWORD, JUDGE_EMAIL, JUDGE_PASSWORD
        init_database()
        seed_demo_data()
        user = authenticate_user(DEMO_EMAIL, DEMO_PASSWORD)
        judge = authenticate_user(JUDGE_EMAIL, JUDGE_PASSWORD)
        deals = get_deals()
        revision = get_market_revision()
        print(f"Database: OK — {len(deals)} deals, demo wallet R{get_wallet(user.id):,.2f}, judge wallet R{get_wallet(judge.id):,.2f}")
        print(f"Market: OK — {revision.active_listings} active asks, {revision.active_bids} indicative bids")
        first_holding_deal = __import__("services").get_holdings(judge.id)[0].deal.id
        liq = get_liquidity_snapshot(judge.id, first_holding_deal)
        portfolio_liq = get_portfolio_liquidity(judge.id)
        print(f"Liquidity Intelligence: OK — score {liq.forecast.liquidity_score}/100, 30d {liq.forecast.probability_30d:.1f}%, portfolio {portfolio_liq.weighted_score}/100")
    except Exception as exc:
        print(f"FAIL — Prometheus setup: {exc}")
        raise SystemExit(1)

    print("PASS — Flet 1.x and Prometheus One look ready.")


if __name__ == "__main__":
    main()
