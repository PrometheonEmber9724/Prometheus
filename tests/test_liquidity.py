"""Isolated Prometheus One Liquidity Intelligence tests."""

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DB = Path(tempfile.gettempdir()) / "prometheus_one_liquidity_test.db"
TEST_DB.unlink(missing_ok=True)
os.environ["PROMETHEUS_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from database import init_database  # noqa: E402
from models import engine  # noqa: E402
from seed import JUDGE_EMAIL, JUDGE_PASSWORD, seed_demo_data  # noqa: E402
from services import (  # noqa: E402
    authenticate_user,
    get_exit_goal_plan,
    get_holdings,
    get_liquidity_model_card,
    get_liquidity_model_validation,
    get_liquidity_snapshot,
    get_portfolio_liquidity,
)


def main():
    init_database()
    seed_demo_data()
    judge = authenticate_user(JUDGE_EMAIL, JUDGE_PASSWORD)
    holdings = get_holdings(judge.id)
    assert len(holdings) == 5

    deal_id = holdings[0].deal.id
    reference = float(holdings[0].deal.unit_price)
    base = get_liquidity_snapshot(judge.id, deal_id, reference)
    discounted = get_liquidity_snapshot(judge.id, deal_id, reference * 0.95)
    premium = get_liquidity_snapshot(judge.id, deal_id, reference * 1.05)

    for snap in (base, discounted, premium):
        f = snap.forecast
        assert 0 <= f.liquidity_score <= 100
        assert 0 <= f.probability_7d <= f.probability_14d <= f.probability_30d <= 100
        assert f.expected_days_low < f.expected_days_high
        assert f.demand_signal in {"WEAK", "MODERATE", "STRONG"}
        assert f.confidence in {"Low", "Moderate", "High"}
        assert f.positive_factors and f.negative_factors

    # The simulator must actually respond to price inputs.
    assert discounted.forecast.probability_30d > premium.forecast.probability_30d
    assert discounted.forecast.liquidity_score >= premium.forecast.liquidity_score

    # Portfolio-level stress metrics should be populated and bounded.
    portfolio = get_portfolio_liquidity(judge.id)
    assert 0 <= portfolio.weighted_score <= 100
    assert 0 <= portfolio.liquid_7d_pct <= portfolio.liquid_30d_pct <= portfolio.liquid_90d_pct <= 100
    assert len(portfolio.ladder) == 4
    assert portfolio.concentration_risk in {"Low", "Moderate", "High"}

    # Exit planner and transparency centre.
    plan = get_exit_goal_plan(judge.id, deal_id, 14)
    assert plan.suggested_price_low < plan.suggested_price_high
    assert 0 <= plan.estimated_probability <= 100
    validation = get_liquidity_model_validation()
    assert validation.sample_size > 100
    assert validation.model_accuracy >= validation.baseline_accuracy
    assert 0 <= validation.brier_score <= 1
    card = get_liquidity_model_card()
    assert "simulated" in card["data"].lower()
    assert any("financial advice" in item.lower() for item in card["limitations"])

    print(
        "PASS — Liquidity Intelligence forecasts, simulator, explainability, "
        "portfolio stress test, backtest and model card are working."
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        TEST_DB.unlink(missing_ok=True)
