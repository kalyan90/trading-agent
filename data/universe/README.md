# Stock-universe snapshots

This directory stores point-in-time constituent snapshots downloaded from NSE
Indices Limited. Each row records the snapshot date, index, symbol, company,
industry, series, and ISIN.

The public constituent files describe the membership current on the download
date. They must not be projected backward into older backtests. Historical
constituent data is a separate NSE Indices data product; obtain it before making
survivorship-bias-free claims about past index-member performance.

The loader rejects duplicate `(as_of, index_name, symbol)` rows. Lookup selects the
latest snapshot known on or before each date and deduplicates overlapping indexes.
A current snapshot projected backward is labeled `retrospective_current_snapshot`.

Refresh the forward research snapshot with:

```bash
uv run python scripts/download_index_constituents.py
```
