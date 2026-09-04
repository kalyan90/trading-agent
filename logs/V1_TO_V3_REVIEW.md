# V1 to V3 research review

## What made nominal profit?

V1 development made ₹1,363.35 under its selected risk-adjusted configuration, but
its one-time final holdout lost ₹362.45. V2 development made ₹584.60. V3 Step 1
made ₹634.55; Step 2 NIFTY futures made ₹49,260 unconstrained and ₹46,860.87 in
the funded model; Step 3 BANKNIFTY made ₹834.10 spot and ₹11,550.57 funded futures.
Step 4 lost ₹70,833.50. Step 5 combined lost ₹12,978.48. Step 6’s corrected dynamic
long-history cohort made ₹725,369.01, but the latest 2024-to-cutoff cohort lost
₹121,724.51.

## What beat its benchmark?

No promoted version established broad benchmark superiority. V1’s final holdout
beat rate was 0%. V2, Steps 1–5, and Step 6 long-history all materially lagged their
matching passive benchmarks. In Step 6, none of the three fixed combined cohorts
beat its benchmark. A few subgroup/window results beat weak or negative passive
comparators, but that is not consistent benchmark capture.

## Holdouts and overfitting

V1 is the only consumed final holdout and it failed. Later NIFTY, BANKNIFTY, and
equity reserves remain untouched. The frozen parameters prevent direct indicator
optimization after failures, so there is no demonstrated parameter-mining leakage.
However, repeated architecture/instrument experiments use the same development era,
creating research-selection risk. Step 4/5 current-constituent tests have explicit
survivorship bias. Step 5 also had an intersection-calendar distortion; Step 6 fixes
that without rewriting the frozen evidence. No future candle or future snapshot is
silently accessed by the chronology-safe modes.

## Did conservatism or low exposure explain failure?

Partly, but not sufficiently. V2 and Steps 1–3 had low exposure (roughly 7–33%), so
they captured little of strong passive trends. Step 6 raises combined exposure to
58.57% and produces nominal profit, yet still trails the benchmark by ₹1.84 million
and suffers 27.94% drawdown. The issue is therefore not just excessive caution:
timing, gates, exits, and missed trend participation remain economically weak.

## Did the model have too much or too little information?

The signal has too little market context for robust ranking: it sees only each
symbol’s OHLCV-derived trend/momentum state, not cross-sectional opportunity cost,
fundamentals, dividends, corporate-action certainty, sector risk, or historical
membership. Conversely, the research program has many evaluation views and
instrument/accounting variants, which creates too many researcher degrees of
freedom even though signal parameters stayed frozen. More inputs are not automatically
better; only point-in-time, authoritative data with predeclared hypotheses would be
defensible.

## Honest conclusion

Trend-Momentum sometimes earns nominal development profit and survives higher costs,
but it has not demonstrated repeatable benchmark-adjusted value, failed its only
consumed holdout ancestor, weakens sharply in the recent cohort, and breaches the
Step 6 drawdown rule. The Step 6 retirement rule is triggered. Retire this policy
from further promotion; preserve it as negative research evidence. Any successor
must be a genuinely new, predeclared hypothesis with fresh untouched evaluation—not
another tuning pass over these results.
