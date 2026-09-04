# Documentation

Start with [`STRATEGY_GUIDE.md`](STRATEGY_GUIDE.md) for a plain-language explanation
of what the project trades, how V4 chooses stocks, and how results are judged.

Read [`LLM_DECISION_SUPPORT.md`](LLM_DECISION_SUPPORT.md) before adding an LLM. It
defines safe assistance, prohibited responsibilities, audit requirements, and a
future shadow-mode evaluation path. An LLM is not part of the frozen V4 signal.

[`DAILY_SYSTEM.md`](DAILY_SYSTEM.md) explains the V5 daily BUY/SELL/HOLD/DEFER/BLOCK
control plane and how it coexists with the monthly V4 baseline.

Detailed commands, data provenance, and experiment evidence remain in:

- [`../scripts/README.md`](../scripts/README.md)
- [`../data/README.md`](../data/README.md)
- [`../logs/README.md`](../logs/README.md)
