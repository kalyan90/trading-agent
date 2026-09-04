# Research data

Source files and derived files are kept separate.

```text
data/
├── NIFTY 50_Historical_*.csv   # original NIFTY 50 downloads
├── index/                      # additional index histories
├── futures/                    # contract-level derivatives history
├── universe/                   # dated constituent snapshots
├── stocks/                     # raw NSE EQ bhavcopy histories
└── stocks_adjusted/            # derived back-adjusted histories
```

See the folder notes for detail: [`futures`](futures/README.md), [`universe`](universe/README.md), [`stocks`](stocks/README.md), and [`stocks_adjusted`](stocks_adjusted/README.md).

## Principles

- Raw exchange values are never silently overwritten.
- Downloads are explicit and never occur during imports or tests.
- Missing prices are not fabricated.
- Futures expiry, settlement, volume, open interest, and historical lots remain contract-specific.
- Membership becomes usable only on its as-of date.
- Pilot equity manifests record source, retrieval time, coverage, row count, adjustment status, and SHA-256.

## Equity schema

| Field | Meaning |
|---|---|
| `date` | ISO exchange session |
| `symbol`, `series` | NSE symbol and market series (`EQ` for the pilot) |
| `open/high/low/close` | Daily prices |
| `previous_close` | NSE prior-close reference |
| `volume`, `value`, `trades` | Activity fields from the archive |
| `isin` | Security identifier when supplied |

## Corporate actions

V3 Step 4 derives a separate adjusted dataset. It prefers an NSE ex-date reference; otherwise it snaps a large discontinuity only to a standard split/bonus factor. Earlier OHLC is multiplied by that factor and volume is inverse-adjusted. Every event and method is recorded.

The pilot has one 0.5 factor for HDFCBANK and one for RELIANCE. Dividends are not reinvested, so benchmarks are price-return rather than total-return. Inferred events need authoritative reconciliation before production use.

## Coverage and reserve

- Ten pilot stocks, 1,653 common sessions each, 2020-01-01 through 2026-09-03.
- Development ends 2025-08-29.
- The final 250 common sessions begin 2025-09-01 and remain reserved.
- The 2026-09-04 constituent snapshot is not unbiased historical membership.

Reproduction commands are in [`../scripts/README.md`](../scripts/README.md).
## V3 Step 5 coverage and provenance

The Step 5 downloader accepts NIFTY 50, NIFTY Next 50, and NIFTY BANK groups and
uses their deduplicated symbol union. Raw bhavcopies, adjusted files, adjustment
sidecars, and SHA-256 manifests remain separate. `stocks_step5_raw/` and
`stocks_step5_adjusted/` contain 105 symbols acquired on 2026-09-04. Seven recent
or renamed listings have fewer than the minimum 540 rows; no earlier history was
fabricated. The constituent snapshot supports only retrospective, survivorship-
biased diagnostics.

## Step 6 availability limits

Historical index constituent files were not acquired. NSE Indices publishes current
constituents, reconstitution notices, and a paid historical constituent data product;
the repository does not silently reconstruct missing intervals from press releases.
Step 6 therefore reports `retrospective_current_snapshot` or
`long_history_static_cohort` modes only.

No authoritative per-security dividend series was acquired, so reported benchmarks
remain price-return benchmarks. The engine accepts only verified dividend events
with source URLs when such data becomes available. Existing inferred split/bonus
sidecars remain warnings/adjustments and are not relabeled as authoritative
confirmation. DP fees are configurable sell-side broker scenarios, not statutory
truth; Step 5 statutory rates and effective-date metadata remain unchanged.

## V4 Step 1 reuse

V4 Step 1 reuses the validated adjusted Step 5 histories without regenerating them.
The 2026-09-04 constituent snapshot is still retrospective for every earlier cohort;
no historical membership is inferred. A stock needs its own 252 prior observations,
a row on the global month-end session, and the no-lookahead liquidity gate before it
can be ranked. Late listings and missing rows affect only that stock. Dividends are
not included because an authoritative event series is unavailable, so both strategy
and benchmark are labeled price-return results.

## V4 Step 2 regime input

The overlay uses the stored official NIFTY 50 price-return files named
`NIFTY 50_Historical_PR_*.csv`. They are normalized and deduplicated by date; only
rows before 2025-09-01 enter development evaluation. Exactly 200 observations ending
on the signal date are required. A missing month-end row or insufficient history is
risk-off; nothing is forward-filled or read from a later date.

## V4 Step 3 prospective provenance

Prospective evidence begins no earlier than the locked 2026-09-04 inception.
Historical adjusted constituent prices and NIFTY 50 closes may warm the frozen
252/21 momentum and 200-session regime indicators, but replay/warm-up records are
never journaled as prospective performance. The 2025-09-01 historical reserve is
not consumed by Step 3.

Every prospective input must carry an explicit exchange session date. Missing,
same-close, future, or stale next-open prices are skipped or deferred rather than
filled. Constituent membership evidence is required as of the decision; the stored
2026-09-04 snapshot must not be projected backward. NIFTY 50 index data supplies
only regime and benchmark context—not a tradable V4 instrument.

`generate_v4_step3_input.py` separates the two evidence cutoffs: rankings and the
regime use rows no later than `signal_date`, while execution prices use the first
available stock open strictly after that date and no later than `as_of`. `SMA`
means simple moving average; `RS` means relative strength; `12−1` means 252-session
momentum with the latest 21 sessions skipped; `PIT` means point in time.
