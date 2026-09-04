# Back-adjusted pilot cash-equity data

These are reproducible derivatives of `data/stocks/`, not independently downloaded prices. Historical OHLC is back-adjusted and volume is inverse-adjusted for large ex-date discontinuities. Each `.adjustments.json` file records the factor and method; each manifest checksums the derived CSV.

The current pilot detects one 0.5 adjustment for HDFCBANK and one for RELIANCE. Dividends are not reinvested, so the benchmark is price-return rather than total-return. This adjustment method is adequate for the current research checkpoint but must be reconciled against an authoritative corporate-actions file before production use.
