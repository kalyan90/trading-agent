# Scripts and reproducibility

Scripts are explicit entry points; importing the package never downloads data or runs experiments.

## Baseline and index comparisons

```bash
uv run trading-agent
uv run python scripts/compare_banknifty.py
```

The BANKNIFTY comparison does not read its reserved holdout.

## Index, futures, and membership downloads

```bash
uv run python scripts/download_nse_index.py --start-year 2020 --end-year 2026
uv run python scripts/download_nse_futures.py --start-year 2020 --end-year 2026
uv run python scripts/download_nse_futures.py \
  --symbol RELIANCE --instrument-type FUTSTK --start-year 2020 --end-year 2026
uv run python scripts/download_index_constituents.py
```

Membership output is an as-of snapshot; it must not be projected backward as historical membership.

## Cash-equity preparation

The interactive NSE history API is supported but may return 503 responses. Historical research therefore uses official daily bhavcopies:

```bash
uv run python scripts/download_nse_bhavcopy_equities.py \
  --universe data/universe/nifty_100_bank_constituents_2026-09-04.csv \
  --pilot --start 2020-01-01 --end 2026-09-03

uv run python scripts/validate_equity_data.py \
  --data-dir data/stocks --remove-identical-duplicates
uv run python scripts/adjust_equity_data.py
uv run python scripts/validate_equity_data.py --data-dir data/stocks_adjusted
```

The pipeline rejects holiday responses carrying the wrong exchange date. Only byte-identical duplicates can be removed automatically; conflicting rows fail. Raw files remain separate, every CSV has a checksum manifest, and inferred corporate-action factors have sidecars.

## V3 Step 4 comparison

```bash
uv run python scripts/run_v3_step4.py --data-dir data/stocks_adjusted
```

It reports shared-capital and per-symbol results, current-snapshot index groups, yearly P&L, drawdown, exposure, turnover, charges, benchmark-relative performance, and fixed friction scenarios. Stress scenarios rerun the chronological gate, so higher costs can reduce trading and losses; that is gate sensitivity, not a benefit from costs.

## Paper validation

```bash
uv run python scripts/validate_paper_execution.py
```

This validates risk rejection, persisted idempotency after restart, and position reconciliation. It does not connect to a broker or submit exchange orders.

## Log policy

New experiments require new version-specific logs. Do not overwrite frozen evidence after changing strategy, data, accounting, or evaluation behavior.
## V3 Step 5

Download and evaluate a deduplicated raw universe (network required):

```bash
uv run python scripts/download_nse_bhavcopy_equities.py --universe data/universe/nifty_100_bank_constituents_2026-09-04.csv --indexes "NIFTY 50" "NIFTY NEXT 50" "NIFTY BANK" --start 2020-01-01 --end 2026-09-03 --output-dir data/stocks_step5_raw
uv run python scripts/validate_equity_data.py --data-dir data/stocks_step5_raw
uv run python scripts/adjust_equity_data.py --input-dir data/stocks_step5_raw --output-dir data/stocks_step5_adjusted
uv run python scripts/run_v3_step5.py --data-dir data/stocks_step5_adjusted
```

The downloader checks requested exchange dates, EQ series, group membership, and
deduplicates overlaps. Adjustment refuses a raw file whose manifest checksum does
not match. `run_v3_step5.py` never evaluates the 250-session tail.

## V3 Step 6 dynamic calendar

```bash
uv run python scripts/run_v3_step6.py
uv run pytest -q
```

The runner declares three same-date cohorts (2020–2021, 2022–2023, and 2024
through 2025-08-29), verifies exact group-calendar equality inside each comparison,
and runs a 2020-through-cutoff long-history cohort with base, doubled slippage,
doubled statutory costs, and illustrative ₹15.50/₹25 sell-side DP scenarios. It
uses current membership only in the explicitly labeled retrospective/static mode.
The fixed reserve begins 2025-09-01 and is rejected as an evaluation end date.

## V4 Step 1 relative strength

```bash
uv run python scripts/run_v4_step1.py
uv run pytest -q
```

This command runs only the predeclared 12-minus-1-month, top-10, monthly hypothesis.
It does not search lookbacks, skip periods, portfolio sizes, weights, rebalance
frequencies, or filters. Month-end close creates the rank; each order waits for its
own next available open. Fixed cohorts and group tables enforce identical calendars,
and the evaluation end must precede 2025-09-01.

## V4 Step 2 regime overlay

```bash
uv run python scripts/run_v4_step2.py
uv run pytest -q
```

This adds exactly one overlay to immutable Step 1: risk-on when the official NIFTY
50 month-end close is strictly above its 200-session SMA through that close. Missing
dates/history are risk-off. The runner verifies identical Step 1/Step 2 calendars,
benchmark entry dates, and benchmark P&L. No alternate period, buffer, partial
exposure, stop, or volatility target is tested.

## V4 Step 3 prospective paper workflow

Step 3 accepts explicit local JSON evidence and never defaults an evidence date to
today. Dry-run is the default; `paper` uses only the deterministic local broker.
There is no live adapter.

```bash
uv run python scripts/run_v4_step3_paper.py plan \
  --as-of 2026-10-01 --signal-date 2026-09-30 \
  --inception 2026-09-04 --capital 100000 --mode dry-run \
  --input /path/to/month-plan.json --data-dir data/stocks_step5_adjusted \
  --state var/v4-step3/state.json --journal var/v4-step3/journal.jsonl

uv run python scripts/run_v4_step3_paper.py status \
  --as-of 2026-10-01 --inception 2026-09-04 --capital 100000 \
  --state var/v4-step3/state.json --journal var/v4-step3/journal.jsonl
```

Input JSON contains `regime_close`, `regime_sma200`, `candidates` (symbol, rank,
momentum, membership/history flags), and `prices` (symbol, session date, open).
The append-only JSONL journal records decision plans, candidates, regime evidence,
targets, skips, order results, deferrals, kill-switch changes, and reconciliation.
The atomic JSON state records plans, broker state, idempotent order results,
expected positions, cash, fees, and drawdown state for restart.

The locked policy is monthly 12-minus-1 positive relative strength, at most ten
positions, NIFTY 50 close strictly above its 200-session SMA, sell-before-buy, and
per-symbol next-open execution. At default capital, each target is ₹10,000. Ranking
continues below an unaffordable candidate until ten affordable names or the list is
exhausted. Whole shares only; no leverage, fractional shares, or forced allocation.

Operational assessment remains false until at least 12 complete prospective months
after the explicit inception. Acceptance additionally requires zero duplicate or
reconciliation failures, positive net return after all costs, maximum drawdown no
greater than 20%, a declared benchmark comparison, and no parameter changes during
observation.
