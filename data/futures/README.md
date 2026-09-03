# NIFTY Futures Contract History

Official NSE contract-wise daily price and volume data downloaded on 2026-09-03 from:

`https://www.nseindia.com/report-detail/fo_eq_security`

The files preserve every returned NIFTY `FUTIDX` expiry contract rather than constructing a continuous series prematurely.

| Calendar year | Contract-day rows | Distinct trading dates | Coverage |
|---:|---:|---:|---|
| 2020 | 764 | 252 | 2020-01-01 to 2020-12-31 |
| 2021 | 753 | 248 | 2021-01-01 to 2021-12-31 |
| 2022 | 746 | 247 | 2022-01-03 to 2022-12-30 |
| 2023 | 742 | 246 | 2023-01-02 to 2023-12-29 |
| 2024 | 752 | 249 | 2024-01-01 to 2024-12-31 |
| 2025 | 736 | 243 | 2025-01-01 to 2025-12-31 |
| 2026 | 501 | 167 | 2026-01-01 to 2026-09-03 |

Each row includes trade date, expiry, instrument, symbol, OHLC, last traded price, previous close, settlement price, traded quantity/value, open interest, change in open interest, the NSE-reported market lot, and underlying value.

Some historical source rows leave `market_lot` blank. The raw dump preserves that missing value; a later dated contract-metadata layer must resolve it rather than forward-filling without an explicit rule.

Some illiquid contract rows also contain blank OHLC or settlement fields. They remain in the raw archive, while the futures execution loader excludes them because they cannot provide a defensible fill or valuation price.

The public endpoint silently caps large responses. The downloader therefore uses 27-calendar-day chunks, retries transient failures, and deduplicates on date, expiry, instrument, and symbol.

To reproduce or extend the files:

```bash
uv run python scripts/download_nse_futures.py --start-year 2020 --end-year 2026
```

These are raw contract records. Do not calculate strategy returns until a deterministic contract-selection and rollover policy has created an auditable continuous execution series.
