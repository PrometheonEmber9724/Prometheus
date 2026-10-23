"""Explainable liquidity forecasting for Prometheus.

The model is deliberately compact and auditable for a hackathon prototype.
It trains a deterministic logistic-regression classifier on simulated historical
listings, then combines the resulting probabilities with transparent rules to
produce a liquidity score, expected sale window, pricing guidance and factor
explanations.

This module does not execute trades or provide financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import random
from statistics import mean
from typing import Iterable


EPS = 1e-9
FEATURE_NAMES = (
    "price_discount_pct",
    "demand_ratio",
    "spread_pct",
    "recent_trade_ratio",
    "listing_age_days",
    "risk_score",
)


@dataclass(frozen=True)
class LiquidityFeatures:
    """Normalized market/listing inputs used by the model."""

    price_discount_pct: float
    demand_ratio: float
    spread_pct: float
    recent_trade_ratio: float
    listing_age_days: float
    risk_score: float


@dataclass(frozen=True)
class LiquidityForecast:
    """User-facing liquidity decision-support output."""

    liquidity_score: int
    probability_7d: float
    probability_14d: float
    probability_30d: float
    expected_days_low: int
    expected_days_high: int
    demand_signal: str
    confidence: str
    data_quality: str
    pricing_label: str
    pricing_guidance: str
    suggested_price_low: float
    suggested_price_high: float
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    model_probability: float


@dataclass(frozen=True)
class PortfolioLiquiditySnapshot:
    weighted_score: int
    liquid_7d_pct: float
    liquid_30d_pct: float
    liquid_90d_pct: float
    concentration_risk: str
    illiquid_30d_pct: float
    ladder: tuple[tuple[str, float], ...]
    summary: str


@dataclass(frozen=True)
class BacktestResult:
    sample_size: int
    model_accuracy: float
    baseline_accuracy: float
    brier_score: float
    coefficients: tuple[float, ...]
    intercept: float


def _sigmoid(z: float) -> float:
    z = max(-35.0, min(35.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def _scaled(f: LiquidityFeatures) -> tuple[float, ...]:
    """Scale features into roughly comparable ranges for stable training."""
    return (
        max(-20.0, min(20.0, f.price_discount_pct)) / 10.0,
        max(0.0, min(4.0, f.demand_ratio)) / 2.0,
        max(0.0, min(20.0, f.spread_pct)) / 10.0,
        max(0.0, min(4.0, f.recent_trade_ratio)) / 2.0,
        max(0.0, min(90.0, f.listing_age_days)) / 45.0,
        max(0.0, min(1.0, f.risk_score)),
    )


def _simulated_history(seed: int = 20261026, n: int = 900):
    """Create a deterministic synthetic history for model training/backtesting.

    The labels are generated from economically intuitive relationships plus
    bounded random variation. This is intentionally simulated data and is
    disclosed as such in the product UI and model card.
    """
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        f = LiquidityFeatures(
            price_discount_pct=rng.uniform(-12, 12),
            demand_ratio=rng.uniform(0.05, 3.2),
            spread_pct=rng.uniform(0.5, 15.0),
            recent_trade_ratio=rng.uniform(0.0, 2.8),
            listing_age_days=rng.uniform(0, 70),
            risk_score=rng.choice([0.2, 0.55, 0.9]),
        )
        x = _scaled(f)
        latent = (
            -0.35
            + 1.55 * x[0]
            + 1.15 * x[1]
            - 1.00 * x[2]
            + 0.85 * x[3]
            - 0.40 * x[4]
            - 0.55 * x[5]
            + rng.uniform(-0.7, 0.7)
        )
        probability = _sigmoid(latent)
        label = 1 if rng.random() < probability else 0
        rows.append((f, label))
    return rows


def _fit_logistic(rows, epochs: int = 650, lr: float = 0.12, l2: float = 0.025):
    weights = [0.0] * len(FEATURE_NAMES)
    intercept = 0.0
    for _ in range(epochs):
        grad_w = [0.0] * len(weights)
        grad_b = 0.0
        for f, y in rows:
            x = _scaled(f)
            p = _sigmoid(intercept + sum(w * v for w, v in zip(weights, x)))
            err = p - y
            grad_b += err
            for i, value in enumerate(x):
                grad_w[i] += err * value
        count = max(1, len(rows))
        intercept -= lr * grad_b / count
        for i in range(len(weights)):
            weights[i] -= lr * ((grad_w[i] / count) + l2 * weights[i])
    return tuple(weights), intercept


@lru_cache(maxsize=1)
def _trained_model():
    rows = _simulated_history()
    split = int(len(rows) * 0.78)
    train = rows[:split]
    test = rows[split:]
    weights, intercept = _fit_logistic(train)
    return weights, intercept, test


def _predict_probability(features: LiquidityFeatures) -> float:
    weights, intercept, _ = _trained_model()
    x = _scaled(features)
    return _sigmoid(intercept + sum(w * v for w, v in zip(weights, x)))


def _bounded_probability(value: float) -> float:
    return max(0.03, min(0.97, value))


def _risk_adjustment(risk_score: float) -> float:
    return 1.0 - (max(0.0, min(1.0, risk_score)) * 0.12)


def forecast_liquidity(
    features: LiquidityFeatures,
    proposed_price: float,
    reference_price: float,
    market_observations: int,
) -> LiquidityForecast:
    """Forecast liquidity outcomes for one proposed listing price."""
    base = _predict_probability(features)
    adjusted = _bounded_probability(base * _risk_adjustment(features.risk_score))

    # Convert the 30-day classifier into increasing horizon probabilities.
    p30 = adjusted
    p14 = _bounded_probability(1.0 - (1.0 - p30) ** (14.0 / 30.0))
    p7 = _bounded_probability(1.0 - (1.0 - p30) ** (7.0 / 30.0))

    score = int(round(100 * (0.55 * p30 + 0.25 * p14 + 0.20 * min(1.0, features.demand_ratio / 1.5))))
    score = max(0, min(100, score))

    # Expected wait window is deliberately broad to communicate uncertainty.
    midpoint = max(3.0, min(75.0, 34.0 * (1.0 - p30) + 5.0 + features.spread_pct * 0.55))
    low = max(2, int(round(midpoint * 0.72)))
    high = max(low + 2, int(round(midpoint * 1.35)))

    if features.demand_ratio >= 1.35:
        demand_signal = "STRONG"
    elif features.demand_ratio >= 0.70:
        demand_signal = "MODERATE"
    else:
        demand_signal = "WEAK"

    if market_observations >= 9:
        confidence = "High"
        data_quality = "High"
    elif market_observations >= 3:
        confidence = "Moderate"
        data_quality = "Moderate"
    else:
        confidence = "Low"
        data_quality = "Limited"

    reference_price = max(0.01, float(reference_price))
    price_ratio = proposed_price / reference_price
    if price_ratio <= 0.96:
        pricing_label = "Liquidity-forward"
    elif price_ratio <= 1.02:
        pricing_label = "Balanced"
    else:
        pricing_label = "Premium / slower"

    # Guidance range responds to demand and spread without pretending to optimize perfectly.
    demand_nudge = max(-0.035, min(0.025, (features.demand_ratio - 1.0) * 0.018))
    spread_nudge = min(0.04, features.spread_pct / 100.0 * 0.35)
    center = reference_price * (0.985 + demand_nudge - spread_nudge)
    suggested_low = max(reference_price * 0.90, center * 0.975)
    suggested_high = min(reference_price * 1.03, center * 1.025)
    pricing_guidance = (
        f"Indicative liquidity-oriented range R{suggested_low:,.2f}–R{suggested_high:,.2f}. "
        "Lower prices generally increase simulated buyer participation; this is decision support, not advice."
    )

    positives: list[str] = []
    negatives: list[str] = []
    if features.price_discount_pct >= 2.0:
        positives.append("Listing price is below the reference value, improving simulated buyer interest.")
    elif features.price_discount_pct <= -3.0:
        negatives.append("Listing price is meaningfully above the reference value, reducing simulated sale probability.")
    if features.demand_ratio >= 1.2:
        positives.append("Order-book demand is strong relative to the position size.")
    elif features.demand_ratio < 0.65:
        negatives.append("Visible demand is thin relative to the position size.")
    if features.spread_pct <= 4.0:
        positives.append("Bid/ask spread is relatively tight for the simulated market.")
    elif features.spread_pct >= 8.0:
        negatives.append("A wider bid/ask spread signals weaker price agreement.")
    if features.recent_trade_ratio >= 0.8:
        positives.append("Recent completed prototype trades support the liquidity signal.")
    elif features.recent_trade_ratio < 0.25:
        negatives.append("Limited recent trading history reduces confidence in the exit estimate.")
    if features.risk_score >= 0.8:
        negatives.append("Higher-risk private-market assets receive a conservative liquidity adjustment.")
    if not positives:
        positives.append("Pricing remains within a plausible range around the indicative value.")
    if not negatives:
        negatives.append("Private-market liquidity remains uncertain even when current signals are constructive.")

    return LiquidityForecast(
        liquidity_score=score,
        probability_7d=round(p7 * 100, 1),
        probability_14d=round(p14 * 100, 1),
        probability_30d=round(p30 * 100, 1),
        expected_days_low=low,
        expected_days_high=high,
        demand_signal=demand_signal,
        confidence=confidence,
        data_quality=data_quality,
        pricing_label=pricing_label,
        pricing_guidance=pricing_guidance,
        suggested_price_low=round(suggested_low, 2),
        suggested_price_high=round(suggested_high, 2),
        positive_factors=tuple(positives),
        negative_factors=tuple(negatives),
        model_probability=round(base * 100, 1),
    )


def portfolio_liquidity_snapshot(weighted_forecasts: Iterable[tuple[float, LiquidityForecast]]) -> PortfolioLiquiditySnapshot:
    rows = [(float(w), f) for w, f in weighted_forecasts if float(w) > 0]
    total = sum(w for w, _ in rows)
    if total <= 0:
        return PortfolioLiquiditySnapshot(0, 0.0, 0.0, 0.0, "No portfolio", 0.0, tuple(), "Add an investment to generate portfolio liquidity diagnostics.")

    score = round(sum(w * f.liquidity_score for w, f in rows) / total)
    p7 = sum(w * f.probability_7d for w, f in rows) / total
    p30 = sum(w * f.probability_30d for w, f in rows) / total
    # 90-day view extrapolates conservatively from 30-day probability.
    p90 = sum(w * (100 * (1 - (1 - f.probability_30d / 100) ** 3)) for w, f in rows) / total
    illiquid = max(0.0, 100.0 - p30)

    fast = sum(w for w, f in rows if f.expected_days_high <= 14) / total * 100
    medium = sum(w for w, f in rows if 14 < f.expected_days_high <= 30) / total * 100
    slow = sum(w for w, f in rows if 30 < f.expected_days_high <= 60) / total * 100
    very_slow = max(0.0, 100.0 - fast - medium - slow)
    ladder = (
        ("≤ 14 days", round(fast, 1)),
        ("15–30 days", round(medium, 1)),
        ("31–60 days", round(slow, 1)),
        ("60+ days", round(very_slow, 1)),
    )

    concentration = "High" if illiquid >= 55 else "Moderate" if illiquid >= 35 else "Low"
    summary = (
        f"Approximately {p30:.0f}% of portfolio value has modeled 30-day exit potential under current simulated conditions. "
        f"Liquidity concentration risk is {concentration.lower()}."
    )
    return PortfolioLiquiditySnapshot(
        weighted_score=int(score),
        liquid_7d_pct=round(p7, 1),
        liquid_30d_pct=round(p30, 1),
        liquid_90d_pct=round(p90, 1),
        concentration_risk=concentration,
        illiquid_30d_pct=round(illiquid, 1),
        ladder=ladder,
        summary=summary,
    )


def backtest_model() -> BacktestResult:
    """Evaluate the deterministic model on held-out simulated listings."""
    weights, intercept, test = _trained_model()
    if not test:
        return BacktestResult(0, 0.0, 0.0, 0.0, weights, intercept)
    correct = 0
    baseline_correct = 0
    brier_values = []
    for f, y in test:
        x = _scaled(f)
        p = _sigmoid(intercept + sum(w * v for w, v in zip(weights, x)))
        pred = 1 if p >= 0.5 else 0
        correct += int(pred == y)
        # Transparent rules baseline: competitive price + adequate demand + manageable spread.
        rules_score = 0
        rules_score += 1 if f.price_discount_pct >= 0 else 0
        rules_score += 1 if f.demand_ratio >= 0.9 else 0
        rules_score += 1 if f.spread_pct <= 7.0 else 0
        rules_score += 1 if f.recent_trade_ratio >= 0.5 else 0
        baseline_pred = 1 if rules_score >= 2 else 0
        baseline_correct += int(baseline_pred == y)
        brier_values.append((p - y) ** 2)
    return BacktestResult(
        sample_size=len(test),
        model_accuracy=round(correct / len(test) * 100, 1),
        baseline_accuracy=round(baseline_correct / len(test) * 100, 1),
        brier_score=round(mean(brier_values), 3),
        coefficients=tuple(round(w, 3) for w in weights),
        intercept=round(intercept, 3),
    )
