# LLM Decision Support: Safe Scope and Future Design

## What an LLM is

A large language model (LLM) is software trained to work with language and other
structured or unstructured information. It can summarize, classify, explain, and
produce structured suggestions. It does not inherently know whether a market fact
is current or true, cannot guarantee calculations, and can confidently produce an
incorrect answer.

For this project, an LLM should be treated like a junior research and operations
assistant whose work must be sourced, constrained, validated, and audited.

## Is an LLM part of the V4 trading decision?

No. Frozen V4 decisions are entirely deterministic:

```text
validated market data
        ↓
fixed membership, momentum, regime, allocation, and execution rules
        ↓
paper plan and audit evidence
```

Adding an LLM vote, sentiment filter, news override, or discretionary ranking now
would create a different strategy. It would require a separately named future
version, predeclared evaluation rules, and new evidence. It must not silently alter
the ongoing V4 observation.

## Useful roles that do not change V4

An LLM can safely assist around the deterministic decision:

- explain a monthly plan in plain language;
- summarize why symbols were selected, skipped, or deferred using recorded fields;
- turn readiness blockers and reconciliation mismatches into an operator checklist;
- classify logs and suggest likely causes for investigation;
- draft a monthly observation report from immutable audit JSON;
- document code and data schemas;
- help a human query the system through natural language;
- review sourced corporate-action or membership notices without applying them
  automatically; and
- maintain a clearly separate backlog of future research hypotheses.

These outputs are advisory. The underlying JSON, calculations, and validations
remain authoritative.

## Responsibilities an LLM must not have

Within frozen V4, an LLM must not:

- add, remove, reorder, or veto candidates;
- change capital, position count, lookback, SMA period, fees, or slippage;
- invent a missing price, membership record, dividend, or corporate action;
- decide that stale or failed data is “probably fine”;
- override the kill switch or reconciliation failure;
- submit exchange or broker orders;
- consume the reserved holdout;
- rewrite past evidence or reports; or
- claim that paper or development performance proves profitability.

## A safe architecture

```text
Official sources → validated data → deterministic V4 engine → immutable audit
                                              ↓
                                      read-only LLM context
                                              ↓
                                  explanation / anomaly summary
                                              ↓
                                      explicit human review
```

The LLM receives the minimum necessary read-only data. Its output is stored
separately from strategy evidence and cannot call the paper coordinator or broker.
Every factual statement should point back to a source field, file checksum, or URL.

## Security and reliability controls

Market news, webpages, filings, CSV text, and even repository issues are untrusted
input. They may contain incorrect claims or text designed to manipulate an AI.

A future LLM component should therefore require:

- structured input and output schemas;
- a strict allowlist of read-only capabilities;
- source URL, publication time, exchange date, and retrieval time metadata;
- rejection of unsupported factual claims;
- deterministic recomputation of all numeric fields outside the LLM;
- separation of instructions from retrieved content;
- prompt and model-version logging;
- output length and token limits;
- no secrets, broker credentials, or write access;
- human approval for any external communication; and
- a switch that disables the LLM without affecting the trading engine.

LLM output must never be used as the only record of a decision.

## Possible future research: news or event context

A later research version could test whether explicitly defined, timestamped public
information adds value—for example, classifying exchange announcements available
before a signal cutoff. That experiment should begin in shadow mode:

1. Predeclare the information sources, timestamps, labels, model, prompt, and
   missing-data behavior.
2. Freeze a structured output schema and retain every raw source and model output.
3. Generate LLM observations without changing V4 positions.
4. Measure stability, factual accuracy, latency, coverage, and incremental value.
5. Compare against the unchanged deterministic baseline on untouched evidence.
6. Reject the feature if it relies on future publication, unstable model behavior,
   unverifiable claims, or economically insignificant improvements after costs.

Model upgrades and prompt changes are parameter changes. They must be versioned;
otherwise the experiment cannot be reproduced.

## Good and bad examples

Appropriate:

> “The plan skipped ABC because its estimated one-share cost exceeded the fixed
> ₹10,000 target. Source: plan `2026-09`, skip reason `unaffordable_target`.”

Inappropriate:

> “ABC looks promising in the news, so ignore the fixed target and buy it anyway.”

Appropriate:

> “The audit shows an expected/actual position mismatch in XYZ. Keep execution
> disabled and investigate the journal and broker state.”

Inappropriate:

> “The mismatch is probably harmless; continue trading.”

## Recommended first LLM feature

The safest first feature is a read-only monthly report explainer. It would accept
the immutable V4 operational report, produce a beginner-friendly summary, quote no
unverified market facts, and clearly distinguish strategy results from operational
warnings. It would have no access to order submission or strategy configuration.

This adds usability without contaminating the prospective V4 experiment.
