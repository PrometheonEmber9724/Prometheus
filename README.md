# Prometheus One

**Ember Capital - Final FNB Hackathon Build**  
**Private Markets. Made Accessible.**  
**Access → Understand → Trade → Exit Intelligently**

Prometheus One is a fractional private-markets investment prototype that helps investors discover opportunities, understand them, invest, monitor a portfolio, trade through a structured secondary market, and model the path back out through **Prometheus Liquidity Intelligence**.

> Most investment platforms focus on getting investors in. Prometheus One also helps them understand the path back out.

## Core product journey

1. **Marketplace** - discover simulated private-market opportunities.
2. **Deal Room** - review thesis, use of funds, risks, documents, scenario analysis and capital timeline.
3. **Fractional Invest** - invest in units with KYC gating and wallet-ledger accounting.
4. **Portfolio Intelligence** - review concentration, risk, income/growth mix and capital journey.
5. **Secondary Market** - list holdings, view indicative bids and executable asks, and settle simulated trades atomically.
6. **Liquidity Intelligence** - forecast sale probability, time-to-sale and pricing sensitivity before listing.

## Prometheus Liquidity Intelligence

The V7 innovation layer includes:

- Liquidity Score (0–100)
- 7 / 14 / 30-day modeled sale probability
- Expected time-to-sale range
- Smart pricing guidance
- Interactive price simulator
- Demand signal
- Explainable positive/negative factors
- Confidence and data-quality labels
- Liquidity Passport for each holding
- Exit Goal Planner
- Price / Liquidity Curve
- Portfolio Liquidity Stress Test
- Liquidity Ladder and concentration risk
- Held-out simulated backtesting
- Model Card / Transparency Centre

The model is intentionally explainable. A deterministic logistic-regression classifier is trained on simulated historical listings and compared with a transparent rules baseline. Current prototype data is simulated; forecasts are decision-support estimates, not guarantees or financial advice.

## Architecture

```text
Flet UI
   ↓
services.py
   ├── Core platform logic
   │     • Investing
   │     • Wallet / ledger
   │     • Ownership
   │     • Portfolio
   │     • Secondary market
   │
   └── liquidity/
         • Explainable logistic regression
         • Liquidity scoring
         • Pricing simulation
         • Portfolio stress testing
         • Backtesting / transparency
   ↓
database.py
   ↓
models.py / SQLAlchemy
   ↓
SQLite prototype
```

The UI does not mutate the database directly. Business rules live in the service layer and secondary-market settlement occurs inside a transaction boundary.

## Quick start - Windows

### 1. Setup

```powershell
setup_windows.bat
```

### 2. Launch desktop app

```powershell
run_windows.bat
```

Alternative:

```powershell
.\.venv\Scripts\python.exe app.py
```

### Optional browser launch

```powershell
run_web_windows.bat
```

## Judge demo account

```text
Email:    judge@prometheus.demo
Password: PrometheusDemo26!
```

The account is pre-seeded with a diversified simulated portfolio, wallet history, secondary-market context and Liquidity Intelligence inputs.

Recommended judge path:

```text
Marketplace
→ Deal Room
→ Portfolio
→ Secondary Market
→ Liquidity Intelligence
→ Liquidity Passport
→ Portfolio Stress Test
→ Transparency Centre
```

## Other demo accounts

```text
Demo buyer
Email: demo@prometheus.local
Password: Prometheus123!

Market seller
Email: seller@prometheus.local
Password: Seller123!
```

## Run verification tests

```powershell
run_tests_windows.bat
```

The test suite verifies the stable investment / wallet / ownership / secondary-market rules and the V7 predictive liquidity layer, including pricing sensitivity and model validation.

## Security / integrity controls

- Salted PBKDF2-HMAC-SHA256 passwords
- Temporary lockout after repeated failed sign-in attempts
- Simulated KYC gating
- Ledger-derived wallet balances
- Reserved units prevent double-selling
- Atomic buyer/seller settlement
- Ownership checks
- User notifications and audit events
- Bounded validation on monetary and unit inputs
- Explainable predictive outputs with confidence and limitations

## Prototype disclosure

Prometheus One is a hackathon prototype. Money, private-market opportunities, KYC, bids, historical listings, model training data and forecasts are simulated. No real financial transaction is processed, no sale is guaranteed, and Liquidity Intelligence does not constitute financial advice.
