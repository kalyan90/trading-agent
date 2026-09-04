# Raw pilot cash-equity data

These files contain official NSE daily EQ-series bhavcopy rows for the fixed V3 Step 4 pilot. Coverage is 2020-01-01 through 2026-09-03. Each CSV has a JSON manifest containing source, retrieval time, adjustment status, date coverage, row count, and SHA-256 checksum.

The prices are raw and must not be used for performance comparisons without corporate-action handling. NSE holiday URLs occasionally returned a neighbouring session; the downloader now rejects payloads whose exchange date differs from the requested date. The preserved files were cleaned only where duplicate rows were byte-for-byte identical.

Run `scripts/validate_equity_data.py` before using or replacing this dataset.
