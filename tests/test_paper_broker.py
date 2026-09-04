from trading_agent.execution.broker import (
    OrderRequest, OrderSide, OrderStatus, PaperBroker,
)


def test_paper_broker_is_idempotent_and_tracks_cash_and_positions():
    broker = PaperBroker(initial_cash=100_000, max_order_value=50_000)
    broker.mark("RELIANCE", 2_000)
    order = OrderRequest(
        symbol="RELIANCE", side=OrderSide.BUY, quantity=10,
        client_order_id="signal-1",
    )
    first = broker.submit(order)
    second = broker.submit(order)
    assert first == second
    assert first.status == OrderStatus.FILLED
    assert broker.positions() == {"RELIANCE": 10}
    assert broker.available_cash() == 80_000


def test_paper_broker_enforces_pretrade_risk_limit():
    broker = PaperBroker(initial_cash=100_000, max_order_value=10_000)
    broker.mark("TCS", 4_000)
    result = broker.submit(OrderRequest(
        symbol="TCS", side=OrderSide.BUY, quantity=3,
        client_order_id="too-large",
    ))
    assert result.status == OrderStatus.REJECTED
    assert result.reason == "order value exceeds risk limit"
