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
