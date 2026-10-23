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

The innovation layer includes:

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


Prometheus can be run locally on a Windows computer after cloning or downloading this repository.

Prerequisites

Make sure the following are installed:

Python 3.11 or newer

Git, if cloning the repository

An internet connection for the initial dependency installation

No API keys or external database setup are required.


## 1. Get the Prometheus repository

Option A - Clone with Git

Open PowerShell, Command Prompt, or the VS Code terminal and run:

git clone https://github.com/PrometheonEmber9724/Prometheus.git
cd Prometheus

Option B - Download the ZIP

Click Code on this GitHub repository.

Select Download ZIP.

Extract the ZIP file.

Open the extracted Prometheus folder.

All commands below should be run from inside the Prometheus project folder.


## 2. Set up the application

Run:

setup_windows.bat

This creates a local Python virtual environment and installs the required dependencies from requirements.txt.


## 3. Launch Prometheus

Run:

run_windows.bat

Alternatively:
```
.\.venv\Scripts\python.exe app.py
```
Prometheus should then launch as a desktop application.


## 4. Demo Login

Use the preconfigured judge account:

Email: judge@prometheus.demo
Password: PrometheusDemo26!

The judge account includes seeded demo data for the wallet, portfolio, marketplace, secondary market, and Liquidity Intelligence features.


## 5. Optional Browser Version

To run Prometheus in a local web browser instead of the desktop application:

run_web_windows.bat

## 6. Recommended Demo Path

For the quickest overview of the platform, explore:

Marketplace
→ Deal Room
→ Portfolio
→ Secondary Market
→ Liquidity Intelligence
→ Liquidity Passport
→ Liquidity Stress Test

## Troubleshooting

If the application does not start, verify the setup with:

.\.venv\Scripts\python.exe check_setup.py

Then try launching again with:

.\.venv\Scripts\python.exe app.py


## Prometheus uses simulated demo data and is presented as a functioning end-to-end prototype of a private-markets investing platform.

