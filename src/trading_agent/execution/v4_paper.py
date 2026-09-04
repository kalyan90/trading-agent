"""V4 Step 3 prospective, broker-neutral paper-trading coordination.

This module cannot connect to a live broker.  It creates durable plans and can
optionally send deterministic orders to the local :class:`PaperBroker` only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from trading_agent.core.fees import (
    OrderSide as FeeSide,
    V3_STEP5_FEE_SCHEDULE,
    calculate_cash_equity_fees,
)
from trading_agent.execution.broker import (
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    PaperBroker,
)


DEFAULT_INCEPTION = date(2026, 9, 4)
DEFAULT_CAPITAL = 100_000.0
DEFAULT_MAX_POSITIONS = 10
SLIPPAGE = 0.05


class PaperMode(str, Enum):
    DRY_RUN = "dry-run"
    PAPER = "paper"


class SkipReason(str, Enum):
    UNAFFORDABLE_TARGET = "unaffordable_target"
    INSUFFICIENT_CASH = "insufficient_available_cash"
    MISSING_STALE_PRICE = "missing_or_stale_price"
    INSUFFICIENT_HISTORY = "insufficient_history"
    MEMBERSHIP = "membership"
    REGIME_OFF = "regime_off"


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    rank: int = Field(gt=0)
    momentum: float
    member: bool = True
    has_history: bool = True


class PriceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    session_date: date
    open: float = Field(gt=0)


class Skip(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    rank: int | None = None
    reason: SkipReason
    detail: str = ""


class PlannedOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    signal_date: date
    earliest_fill_date: date
    adverse_price: float = Field(gt=0)
    estimated_fee: float = Field(ge=0)
    client_order_id: str
    status: str = "pending"


class DecisionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str
    created_at: datetime
    inception: date
    signal_date: date
    mode: PaperMode
    initial_capital: float
    target_allocation: float
    regime_close: float | None
    regime_sma200: float | None
    regime_on: bool
    ranked_candidates: tuple[Candidate, ...]
    target_quantities: dict[str, int]
    orders: tuple[PlannedOrder, ...]
    skips: tuple[Skip, ...]
    warmup_only: bool = False


class PaperConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial_capital: float = Field(default=DEFAULT_CAPITAL, gt=0)
    max_positions: int = Field(default=DEFAULT_MAX_POSITIONS, gt=0)
    max_order_value: float | None = Field(default=None, gt=0)
    inception: date = DEFAULT_INCEPTION
    mode: PaperMode = PaperMode.DRY_RUN
    dp_charge_per_sell: float = Field(default=0.0, ge=0)
    max_price_age_days: int = Field(default=7, ge=0)

    @property
    def target_allocation(self) -> float:
        return self.initial_capital / self.max_positions


def client_order_id(signal_date: date, symbol: str, side: OrderSide) -> str:
    raw = f"v4.3|{signal_date.isoformat()}|{symbol}|{side.value}"
    return "v43-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class AppendOnlyJournal:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, event: str, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"event": event, "payload": payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class V4PaperCoordinator:
    """Durable coordinator for dry-run planning and deterministic local fills."""

    def __init__(self, config: PaperConfig, journal_path: Path, state_path: Path):
        self.config = config
        self.journal = AppendOnlyJournal(journal_path)
        self.state_path = Path(state_path)
        self.kill_switch = False
        self.plans: dict[str, DecisionPlan] = {}
        self.order_results: dict[str, OrderResult] = {}
        self.expected_positions: dict[str, int] = {}
        self.fees = 0.0
        self.equity_high = config.initial_capital
        self.max_drawdown = 0.0
        self.broker = PaperBroker(
            initial_cash=config.initial_capital,
            max_order_value=config.max_order_value or config.target_allocation,
        )
        if self.state_path.exists():
            self._restore()

    def _fee(self, price: float, quantity: int, side: OrderSide) -> float:
        schedule = V3_STEP5_FEE_SCHEDULE.model_copy(update={
            "dp_charge_per_sell": self.config.dp_charge_per_sell,
        })
        fee_side = FeeSide.BUY if side == OrderSide.BUY else FeeSide.SELL
        return float(calculate_cash_equity_fees(price, quantity, fee_side, schedule).total)

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "config": self.config.model_dump(mode="json"),
            "kill_switch": self.kill_switch,
            "plans": {key: value.model_dump(mode="json") for key, value in self.plans.items()},
            "order_results": {key: value.model_dump(mode="json") for key, value in self.order_results.items()},
            "expected_positions": self.expected_positions,
            "fees": self.fees,
            "equity_high": self.equity_high,
            "max_drawdown": self.max_drawdown,
            "broker": self.broker.snapshot(),
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_path)

    def _restore(self) -> None:
        snapshot = json.loads(self.state_path.read_text(encoding="utf-8"))
        stored = PaperConfig.model_validate(snapshot["config"])
        if stored != self.config:
            raise ValueError("paper configuration differs from persisted state")
        self.kill_switch = bool(snapshot["kill_switch"])
        self.plans = {key: DecisionPlan.model_validate(value) for key, value in snapshot["plans"].items()}
        self.order_results = {key: OrderResult.model_validate(value) for key, value in snapshot["order_results"].items()}
        self.expected_positions = {key: int(value) for key, value in snapshot["expected_positions"].items()}
        self.fees = float(snapshot["fees"])
        self.equity_high = float(snapshot["equity_high"])
        self.max_drawdown = float(snapshot["max_drawdown"])
        self.broker = PaperBroker.restore(snapshot["broker"])

    def set_kill_switch(self, disabled: bool = True) -> None:
        self.kill_switch = disabled
        self.journal.append("kill_switch", {"disabled": disabled})
        self._save()

    def create_plan(
        self,
        *,
        signal_date: date,
        as_of: date,
        candidates: Iterable[Candidate],
        prices: Iterable[PriceEvidence],
        regime_close: float | None,
        regime_sma200: float | None,
        historical_warmup: bool = False,
    ) -> DecisionPlan:
        if not historical_warmup and signal_date < self.config.inception:
            raise ValueError("prospective decision predates locked inception")
        if not historical_warmup and as_of < self.config.inception:
            raise ValueError("prospective evidence predates locked inception")
        plan_id = f"v4.3-{signal_date:%Y-%m}"
        if plan_id in self.plans:
            raise ValueError("duplicate month decision")
        ranked = tuple(sorted(candidates, key=lambda item: (item.rank, item.symbol)))
        price_map = {item.symbol: item for item in prices}
        regime_on = (
            regime_close is not None and regime_sma200 is not None
            and regime_close > regime_sma200
        )
        skips: list[Skip] = []
        targets: dict[str, int] = {}
        available_cash = self.broker.available_cash()
        positions = self.broker.positions()
        if not regime_on:
            for item in ranked:
                skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.REGIME_OFF))
        else:
            for item in ranked:
                if len(targets) >= self.config.max_positions:
                    break
                if not item.member:
                    skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.MEMBERSHIP))
                    continue
                if not item.has_history:
                    skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.INSUFFICIENT_HISTORY))
                    continue
                evidence = price_map.get(item.symbol)
                if (evidence is None or evidence.session_date <= signal_date
                        or evidence.session_date > as_of
                        or (as_of - evidence.session_date).days > self.config.max_price_age_days):
                    skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.MISSING_STALE_PRICE))
                    continue
                adverse = evidence.open + SLIPPAGE
                one_fee = self._fee(adverse, 1, OrderSide.BUY)
                if adverse + one_fee > self.config.target_allocation:
                    skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.UNAFFORDABLE_TARGET))
                    continue
                quantity = int(self.config.target_allocation / adverse)
                while quantity and adverse * quantity + self._fee(adverse, quantity, OrderSide.BUY) > self.config.target_allocation:
                    quantity -= 1
                required = adverse * quantity + self._fee(adverse, quantity, OrderSide.BUY)
                current_value = positions.get(item.symbol, 0) * adverse
                incremental = max(0.0, required - current_value)
                if quantity <= 0 or incremental > available_cash:
                    skips.append(Skip(symbol=item.symbol, rank=item.rank, reason=SkipReason.INSUFFICIENT_CASH))
                    continue
                targets[item.symbol] = quantity
                available_cash -= incremental

        orders: list[PlannedOrder] = []
        all_symbols = sorted(set(positions) | set(targets))
        for symbol in all_symbols:
            evidence = price_map.get(symbol)
            current = positions.get(symbol, 0)
            target = targets.get(symbol, 0)
            difference = target - current
            if difference == 0 or evidence is None or evidence.session_date <= signal_date:
                continue
            side = OrderSide.BUY if difference > 0 else OrderSide.SELL
            adverse = evidence.open + SLIPPAGE if side == OrderSide.BUY else evidence.open - SLIPPAGE
            quantity = abs(difference)
            orders.append(PlannedOrder(
                symbol=symbol, side=side, quantity=quantity,
                signal_date=signal_date, earliest_fill_date=evidence.session_date,
                adverse_price=adverse, estimated_fee=self._fee(adverse, quantity, side),
                client_order_id=client_order_id(signal_date, symbol, side),
            ))
        orders.sort(key=lambda order: (order.side != OrderSide.SELL, order.symbol))
        plan = DecisionPlan(
            plan_id=plan_id, created_at=datetime.combine(as_of, datetime.min.time()),
            inception=self.config.inception, signal_date=signal_date,
            mode=self.config.mode, initial_capital=self.config.initial_capital,
            target_allocation=self.config.target_allocation,
            regime_close=regime_close, regime_sma200=regime_sma200,
            regime_on=regime_on, ranked_candidates=ranked,
            target_quantities=targets, orders=tuple(orders), skips=tuple(skips),
            warmup_only=historical_warmup,
        )
        if not historical_warmup:
            self.plans[plan_id] = plan
            self.journal.append("decision_plan", plan.model_dump(mode="json"))
            self._save()
        return plan

    def execute(self, plan_id: str, as_of: date, prices: Iterable[PriceEvidence]) -> list[OrderResult]:
        if self.config.mode != PaperMode.PAPER:
            return []
        if self.kill_switch:
            raise RuntimeError("paper execution disabled by kill switch")
        plan = self.plans[plan_id]
        if as_of < self.config.inception:
            raise ValueError("execution predates locked inception")
        evidence = {item.symbol: item for item in prices}
        results = []
        for order in plan.orders:
            if order.client_order_id in self.order_results:
                results.append(self.order_results[order.client_order_id])
                continue
            mark = evidence.get(order.symbol)
            if mark is None or mark.session_date < order.earliest_fill_date or mark.session_date > as_of:
                self.journal.append("order_deferred", {"client_order_id": order.client_order_id, "as_of": as_of.isoformat()})
                continue
            adverse = mark.open + SLIPPAGE if order.side == OrderSide.BUY else mark.open - SLIPPAGE
            if adverse * order.quantity > self.broker.max_order_value:
                result = OrderResult(
                    broker_order_id="coordinator-rejected", client_order_id=order.client_order_id,
                    status=OrderStatus.REJECTED, reason="order value exceeds risk limit",
                )
            else:
                fee = self._fee(adverse, order.quantity, order.side)
                self.broker.mark(order.symbol, adverse)
                result = self.broker.submit(OrderRequest(
                    symbol=order.symbol, side=order.side, quantity=order.quantity,
                    client_order_id=order.client_order_id, estimated_fee=fee,
                ))
            self.order_results[order.client_order_id] = result
            if result.status == OrderStatus.FILLED:
                signed = order.quantity if order.side == OrderSide.BUY else -order.quantity
                self.expected_positions[order.symbol] = self.expected_positions.get(order.symbol, 0) + signed
                if self.expected_positions[order.symbol] == 0:
                    self.expected_positions.pop(order.symbol)
                self.fees += result.fee
            self.journal.append("order_result", result.model_dump(mode="json"))
            results.append(result)
        mismatch = self.reconcile()
        self.journal.append("reconciliation", {"as_of": as_of.isoformat(), "mismatches": mismatch})
        self._save()
        return results

    def reconcile(self) -> dict[str, tuple[int, int]]:
        return self.broker.reconcile(self.expected_positions)

    def status(self, as_of: date) -> dict:
        positions = self.broker.positions()
        market_value = sum(quantity * self.broker.prices.get(symbol, 0.0) for symbol, quantity in positions.items())
        equity = self.broker.available_cash() + market_value
        self.equity_high = max(self.equity_high, equity)
        drawdown = self.equity_high - equity
        self.max_drawdown = max(self.max_drawdown, drawdown)
        months = (as_of.year - self.config.inception.year) * 12 + as_of.month - self.config.inception.month
        if as_of.day < self.config.inception.day:
            months -= 1
        months = max(0, months)
        pending = sum(
            order.client_order_id not in self.order_results
            for plan in self.plans.values() for order in plan.orders
        )
        skips = sum(len(plan.skips) for plan in self.plans.values())
        return {
            "inception": self.config.inception.isoformat(),
            "as_of": as_of.isoformat(),
            "months_observed": months,
            "initial_capital": self.config.initial_capital,
            "cash": round(self.broker.available_cash(), 2),
            "equity": round(equity, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "positions": positions,
            "pending_or_deferred_orders": pending,
            "skips": skips,
            "fees": round(self.fees, 2),
            "reconciliation": self.reconcile(),
            "kill_switch": self.kill_switch,
            "eligible_for_assessment": months >= 12,
            "live_adapter": "disabled",
        }


def live_broker_adapter(*_args, **_kwargs):
    raise RuntimeError("live broker adapter is intentionally unavailable in V4 Step 3")
