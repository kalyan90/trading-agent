"""Deterministic restart, idempotency, risk, and reconciliation smoke test."""

from trading_agent.execution.broker import OrderRequest, OrderSide, PaperBroker


def main():
    broker = PaperBroker(initial_cash=1_000_000, max_order_value=200_000)
    broker.mark("RELIANCE", 1_500)
    request = OrderRequest(
        symbol="RELIANCE", side=OrderSide.BUY, quantity=100,
        client_order_id="paper-20260904-reliance-buy-1",
    )
    first = broker.submit(request)
    restored = PaperBroker.restore(broker.snapshot())
    duplicate = restored.submit(request)
    too_large = restored.submit(OrderRequest(
        symbol="RELIANCE", side=OrderSide.BUY, quantity=200,
        client_order_id="paper-20260904-reliance-buy-2",
    ))
    mismatch = restored.reconcile({"RELIANCE": 99})
    print(f"initial_order={first.status} broker_id={first.broker_order_id}")
    print(f"restart_duplicate_same_result={duplicate == first}")
    print(f"risk_rejection={too_large.status} reason={too_large.reason}")
    print(f"position_mismatch={mismatch}")
    print(f"cash={restored.available_cash():.2f} positions={restored.positions()}")
    print("live_adapter_enabled=False")


if __name__ == "__main__":
    main()
