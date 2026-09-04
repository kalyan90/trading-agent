# Stock-universe snapshots

This directory stores point-in-time constituent snapshots downloaded from NSE
Indices Limited. Each row records the snapshot date, index, symbol, company,
industry, series, and ISIN.

The public constituent files describe the membership current on the download
date. They must not be projected backward into older backtests. Historical
constituent data is a separate NSE Indices data product; obtain it before making
survivorship-bias-free claims about past index-member performance.

Refresh the forward research snapshot with:

```bash
uv run python scripts/download_index_constituents.py
```
