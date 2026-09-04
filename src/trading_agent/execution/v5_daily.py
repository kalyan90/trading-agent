"""V5 Step 1 strategy-neutral daily decision and paper-evaluation control plane."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
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
from trading_agent.execution.v4_paper import AppendOnlyJournal, PaperMode, PriceEvidence


DAILY_SLIPPAGE = 0.05


class DailyAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    DEFER = "DEFER"
    BLOCK = "BLOCK"


class TargetIntent(BaseModel):
    """Desired position supplied by a separately versioned deterministic policy."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    target_quantity: int = Field(ge=0)
    satisfiers: dict[str, bool] = Field(min_length=1)
    evidence_complete: bool = True
    detail: str = ""


class ClosingMark(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    session_date: date
    close: float = Field(gt=0)


class DailyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    action: DailyAction
    current_quantity: int = Field(ge=0)
    target_quantity: int = Field(ge=0)
    failed_satisfiers: tuple[str, ...] = ()
    detail: str = ""


class DailyOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    signal_date: date
    client_order_id: str


class DailyPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str
    signal_date: date
    decisions: tuple[DailyDecision, ...]
    orders: tuple[DailyOrder, ...]


class DailyMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_date: date
    cash: float
    market_value: float
    equity: float
    net_return_percent: float
    equity_high: float
    drawdown: float
    drawdown_percent: float
    fees: float
    positions: dict[str, int]
    benchmark_close: float
    benchmark_return_percent: float
    excess_return_percent: float


class DailyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    inception: date
    initial_capital: float = Field(default=100_000, gt=0)
    max_positions: int = Field(default=10, gt=0)
    max_order_value: float | None = Field(default=None, gt=0)
    mode: PaperMode = PaperMode.DRY_RUN
    dp_charge_per_sell: float = Field(default=0.0, ge=0)

    @property
    def target_allocation(self) -> float:
        return self.initial_capital / self.max_positions


def daily_order_id(signal_date: date, symbol: str, side: OrderSide) -> str:
    raw = f"v5.1|{signal_date.isoformat()}|{symbol}|{side.value}"
    return "v51-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class V5DailyCoordinator:
    """Evaluate daily intents, paper-fill later opens, and persist daily metrics."""

    def __init__(self, config: DailyConfig, journal_path: Path, state_path: Path):
        self.config = config
        self.journal = AppendOnlyJournal(journal_path)
        self.state_path = Path(state_path)
        self.kill_switch = False
        self.plans: dict[str, DailyPlan] = {}
        self.order_results: dict[str, OrderResult] = {}
        self.expected_positions: dict[str, int] = {}
        self.metrics: dict[date, DailyMetric] = {}
        self.fees = 0.0
        self.equity_high = config.initial_capital
        self.max_drawdown = 0.0
        self.benchmark_initial_close: float | None = None
        self.broker = PaperBroker(
            initial_cash=config.initial_capital,
            # The coordinator applies the buy limit. Broker capacity stays broad
            # so an appreciated position can always be reduced or liquidated.
            max_order_value=config.initial_capital,
        )
        if self.state_path.exists():
            self._restore()

    def _fee(self, price: float, quantity: int, side: OrderSide) -> float:
        schedule = V3_STEP5_FEE_SCHEDULE.model_copy(update={
            "dp_charge_per_sell": Decimal(str(self.config.dp_charge_per_sell)),
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
            "metrics": {day.isoformat(): value.model_dump(mode="json") for day, value in self.metrics.items()},
            "fees": self.fees,
            "equity_high": self.equity_high,
            "max_drawdown": self.max_drawdown,
            "benchmark_initial_close": self.benchmark_initial_close,
            "broker": self.broker.snapshot(),
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_path)

    def _restore(self) -> None:
        snapshot = json.loads(self.state_path.read_text(encoding="utf-8"))
        if DailyConfig.model_validate(snapshot["config"]) != self.config:
            raise ValueError("daily configuration differs from persisted state")
        self.kill_switch = bool(snapshot["kill_switch"])
        self.plans = {key: DailyPlan.model_validate(value) for key, value in snapshot["plans"].items()}
        self.order_results = {key: OrderResult.model_validate(value) for key, value in snapshot["order_results"].items()}
        self.expected_positions = {key: int(value) for key, value in snapshot["expected_positions"].items()}
        self.metrics = {date.fromisoformat(key): DailyMetric.model_validate(value)
                        for key, value in snapshot["metrics"].items()}
        self.fees = float(snapshot["fees"])
        self.equity_high = float(snapshot["equity_high"])
        self.max_drawdown = float(snapshot["max_drawdown"])
        self.benchmark_initial_close = snapshot["benchmark_initial_close"]
        self.broker = PaperBroker.restore(snapshot["broker"])

    def reconcile(self) -> dict[str, tuple[int, int]]:
        return self.broker.reconcile(self.expected_positions)

    def set_kill_switch(self, disabled: bool = True) -> None:
        self.kill_switch = disabled
        self.journal.append("kill_switch", {"disabled": disabled})
        self._save()

    def create_plan(self, signal_date: date, intents: Iterable[TargetIntent]) -> DailyPlan:
        if signal_date < self.config.inception:
            raise ValueError("daily signal predates inception")
        plan_id = f"v5.1-{signal_date.isoformat()}"
        if plan_id in self.plans:
            raise ValueError("duplicate daily decision")
        if self.plans and signal_date <= max(plan.signal_date for plan in self.plans.values()):
            raise ValueError("daily decisions must be chronological")
        intent_list = list(intents)
        symbols = [intent.symbol for intent in intent_list]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate target intent symbol")
        if sum(intent.target_quantity > 0 for intent in intent_list) > self.config.max_positions:
            raise ValueError("target intents exceed maximum positions")

        positions = self.broker.positions()
        mismatch = self.reconcile()
        global_block = self.kill_switch or bool(mismatch)
        decisions = []
        orders = []
        by_symbol = {intent.symbol: intent for intent in intent_list}
        for symbol in sorted(set(positions) | set(by_symbol)):
            current = positions.get(symbol, 0)
            intent = by_symbol.get(symbol)
            if intent is None:
                decisions.append(DailyDecision(
                    symbol=symbol, action=DailyAction.DEFER,
                    current_quantity=current, target_quantity=current,
                    detail="open position missing target intent",
                ))
                continue
            failed = tuple(sorted(name for name, passed in intent.satisfiers.items() if not passed))
            if global_block:
                action = DailyAction.BLOCK
                detail = "kill switch active" if self.kill_switch else "position reconciliation mismatch"
            elif not intent.evidence_complete:
                action = DailyAction.DEFER
                detail = intent.detail or "decision evidence incomplete"
            elif failed:
                action = DailyAction.BLOCK
                detail = intent.detail or "one or more trade satisfiers failed"
            elif intent.target_quantity > current:
                action = DailyAction.BUY
                detail = intent.detail
            elif intent.target_quantity < current:
                action = DailyAction.SELL
                detail = intent.detail
            else:
                action = DailyAction.HOLD
                detail = intent.detail
            decisions.append(DailyDecision(
                symbol=symbol, action=action, current_quantity=current,
                target_quantity=intent.target_quantity,
                failed_satisfiers=failed, detail=detail,
            ))
            if action in (DailyAction.BUY, DailyAction.SELL):
                side = OrderSide.BUY if action == DailyAction.BUY else OrderSide.SELL
                orders.append(DailyOrder(
                    symbol=symbol, side=side,
                    quantity=abs(intent.target_quantity - current),
                    signal_date=signal_date,
                    client_order_id=daily_order_id(signal_date, symbol, side),
                ))
        orders.sort(key=lambda item: (item.side != OrderSide.SELL, item.symbol))
        plan = DailyPlan(
            plan_id=plan_id, signal_date=signal_date,
            decisions=tuple(decisions), orders=tuple(orders),
        )
        self.plans[plan_id] = plan
        self.journal.append("daily_plan", plan.model_dump(mode="json"))
        self._save()
        return plan

    def execute(self, plan_id: str, as_of: date, prices: Iterable[PriceEvidence]) -> list[OrderResult]:
        if self.config.mode != PaperMode.PAPER:
            return []
        if self.kill_switch:
            raise RuntimeError("daily paper execution disabled by kill switch")
        if self.reconcile():
            raise RuntimeError("daily paper execution blocked by reconciliation mismatch")
        plan = self.plans[plan_id]
        if as_of <= plan.signal_date:
            raise ValueError("execution evidence must be later than signal date")
        price_list = list(prices)
        if len({item.symbol for item in price_list}) != len(price_list):
            raise ValueError("duplicate opening-price symbol")
        evidence = {item.symbol: item for item in price_list}
        results = []
        for order in plan.orders:
            if order.client_order_id in self.order_results:
                results.append(self.order_results[order.client_order_id])
                continue
            mark = evidence.get(order.symbol)
            if mark is None or mark.session_date <= order.signal_date or mark.session_date > as_of:
                self.journal.append("daily_order_deferred", {
                    "client_order_id": order.client_order_id,
                    "as_of": as_of.isoformat(),
                })
                continue
            adverse = mark.open + DAILY_SLIPPAGE if order.side == OrderSide.BUY else mark.open - DAILY_SLIPPAGE
            fee = self._fee(adverse, order.quantity, order.side)
            buy_limit = self.config.max_order_value or self.config.target_allocation
            if order.side == OrderSide.BUY and adverse * order.quantity > buy_limit:
                result = OrderResult(
                    broker_order_id="daily-coordinator-rejected",
                    client_order_id=order.client_order_id,
                    status=OrderStatus.REJECTED,
                    reason="buy order value exceeds daily risk limit",
                )
            else:
                if order.side == OrderSide.SELL:
                    self.broker.max_order_value = max(
                        self.broker.max_order_value, adverse * order.quantity,
                    )
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
            self.journal.append("daily_order_result", result.model_dump(mode="json"))
            results.append(result)
        mismatch = self.reconcile()
        self.journal.append("daily_reconciliation", {
            "as_of": as_of.isoformat(), "mismatches": mismatch,
        })
        self._save()
        return results

    def mark_to_market(
        self,
        session_date: date,
        marks: Iterable[ClosingMark],
        *,
        benchmark_close: float,
    ) -> DailyMetric:
        if session_date < self.config.inception:
            raise ValueError("daily mark predates inception")
        if session_date in self.metrics:
            raise ValueError("duplicate daily metric")
        if self.metrics and session_date <= max(self.metrics):
            raise ValueError("daily metrics must be chronological")
        if benchmark_close <= 0:
            raise ValueError("benchmark close must be positive")
        mark_list = list(marks)
        if len({item.symbol for item in mark_list}) != len(mark_list):
            raise ValueError("duplicate closing-mark symbol")
        mark_map = {item.symbol: item for item in mark_list if item.session_date == session_date}
        positions = self.broker.positions()
        missing = sorted(set(positions) - set(mark_map))
        if missing:
            raise ValueError("open positions lack exact-date closing marks: " + ", ".join(missing))
        for symbol, mark in mark_map.items():
            self.broker.mark(symbol, mark.close)
        market_value = sum(quantity * mark_map[symbol].close for symbol, quantity in positions.items())
        cash = self.broker.available_cash()
        equity = cash + market_value
        self.equity_high = max(self.equity_high, equity)
        drawdown = self.equity_high - equity
        self.max_drawdown = max(self.max_drawdown, drawdown)
        if self.benchmark_initial_close is None:
            self.benchmark_initial_close = benchmark_close
        benchmark_return = (benchmark_close / self.benchmark_initial_close - 1) * 100
        net_return = (equity / self.config.initial_capital - 1) * 100
        metric = DailyMetric(
            session_date=session_date, cash=round(cash, 2),
            market_value=round(market_value, 2), equity=round(equity, 2),
            net_return_percent=round(net_return, 6),
            equity_high=round(self.equity_high, 2), drawdown=round(drawdown, 2),
            drawdown_percent=round(drawdown / self.equity_high * 100 if self.equity_high else 0, 6),
            fees=round(self.fees, 2), positions=positions,
            benchmark_close=benchmark_close,
            benchmark_return_percent=round(benchmark_return, 6),
            excess_return_percent=round(net_return - benchmark_return, 6),
        )
        self.metrics[session_date] = metric
        self.journal.append("daily_metric", metric.model_dump(mode="json"))
        self._save()
        return metric

    def status(self) -> dict:
        latest = self.metrics[max(self.metrics)] if self.metrics else None
        return {
            "inception": self.config.inception.isoformat(),
            "mode": self.config.mode.value,
            "decision_days": len(self.plans),
            "metric_days": len(self.metrics),
            "positions": self.broker.positions(),
            "cash": round(self.broker.available_cash(), 2),
            "fees": round(self.fees, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "latest_metric": latest.model_dump(mode="json") if latest else None,
            "pending_orders": sum(
                order.client_order_id not in self.order_results
                for plan in self.plans.values() for order in plan.orders
            ),
            "reconciliation": self.reconcile(),
            "kill_switch": self.kill_switch,
            "live_adapter": "disabled",
        }
