# V3 Step 5 adjusted equities

Back-adjusted derivatives of `../stocks_step5_raw/`. Each symbol has a CSV, a
manifest/checksum, and a corporate-action event sidecar. Adjustment uses the NSE
ex-date previous-close reference, falling back only to a documented standard
split/bonus factor for large discontinuities. All 105 files pass OHLC/date/checksum
validation; YESBANK retains two post-adjustment >35% moves as warnings.
