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
