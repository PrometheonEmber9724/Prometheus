# Prometheus — Security & Responsible Intelligence Notes

Prometheus is a simulated hackathon prototype. Its security design demonstrates production-minded controls without claiming production readiness.

## Application controls

- Passwords use salted PBKDF2-HMAC-SHA256 hashing.
- Repeated failed logins trigger temporary lockout.
- Investment and secondary-market actions require verified simulated KYC.
- Wallet balances are derived from append-only transaction entries rather than directly mutated balances.
- Secondary listings reserve units before sale to prevent double-selling.
- Secondary settlement updates cash, ownership, listing status, trade record, notifications and audit events inside one service-layer transaction boundary.
- Business rules are isolated from the Flet UI.

## Liquidity Intelligence controls

- Training/history data is explicitly labelled simulated.
- Forecasts expose confidence and data quality.
- User-facing factor explanations accompany predictions.
- A held-out simulated backtest is visible in the Transparency Centre.
- A rules baseline is reported alongside the explainable logistic-regression model.
- The model does not execute trades.
- Forecasts do not guarantee a sale and do not constitute financial advice.

## Production pathway

A production deployment would require regulated KYC/AML integrations, secure secrets management, production authentication/session controls, PostgreSQL or equivalent managed persistence, monitoring, penetration testing, independent model validation, privacy/data-governance controls, and the relevant South African financial-services regulatory approvals.
