"""Human-readable model transparency information for Prometheus One."""

MODEL_CARD = {
    "name": "Prometheus One Liquidity Intelligence",
    "version": "1.0-hackathon",
    "purpose": "Estimate simulated secondary-market sale probability, expected time-to-sale and pricing sensitivity for private-market positions.",
    "method": "Explainable logistic regression compared with a transparent rules baseline.",
    "data": "Deterministic simulated historical listings plus current prototype order-book, pricing and trade signals.",
    "inputs": (
        "Price discount/premium versus reference value",
        "Visible demand relative to the position size",
        "Bid/ask spread",
        "Recent completed prototype trading activity",
        "Listing age",
        "Asset risk category",
    ),
    "limitations": (
        "All current training/history data is simulated.",
        "Forecasts are estimates, not guarantees of a sale.",
        "Sparse market observations reduce confidence.",
        "The model does not execute trades or provide financial advice.",
    ),
}
