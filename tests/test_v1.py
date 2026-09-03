from datetime import datetime

from trading_agent.backtest import (
    calculate_buy_and_hold_benchmark,
    calculate_buy_price,
    calculate_sell_price,
)

from trading_agent.config import (
    StrategyType,
    TradingConfig,
)

from trading_agent.market import (
    MarketData,
)


def create_config(
    force_liquidation=False,
):
    return TradingConfig(
        symbol="NIFTY",

        minimum_confidence=0.7,

        max_position_size=1,

        initial_capital=1000,

        transaction_cost=20,

        slippage=5,

        force_liquidation=(
            force_liquidation
        ),

        sma_period=1,

        strategy=(
            StrategyType.SMA_CROSSOVER
        ),
    )


def create_market_data():

    return [
        MarketData(
            symbol="NIFTY",

            date=datetime(
                2026,
                1,
                1,
            ),

            open=100,
            high=102,
            low=98,
            close=100,

            volume=None,
        ),

        MarketData(
            symbol="NIFTY",

            date=datetime(
                2026,
                1,
                2,
            ),

            open=105,
            high=112,
            low=103,
            close=110,

            volume=None,
        ),

        MarketData(
            symbol="NIFTY",

            date=datetime(
                2026,
                1,
                3,
            ),

            open=115,
            high=122,
            low=113,
            close=120,

            volume=None,
        ),
    ]


def test_buy_slippage():

    assert (
        calculate_buy_price(
            100,
            5,
        )
        == 105
    )


def test_sell_slippage():

    assert (
        calculate_sell_price(
            100,
            5,
        )
        == 95
    )


def test_benchmark_mark_to_market():

    market_data = (
        create_market_data()
    )

    config = (
        create_config(
            force_liquidation=False
        )
    )

    (
        benchmark_pnl,
        benchmark_return,
        benchmark_drawdown,
        benchmark_profit_dd,
    ) = (
        calculate_buy_and_hold_benchmark(
            market_data,
            config,
            benchmark_start_index=0,
        )
    )

    # Buy:
    # 100 + 5 slippage = 105
    #
    # Initial entry cost:
    # 105 + 10 transaction cost
    #
    # Cash:
    # 1000 - 115 = 885
    #
    # Final mark:
    # 885 + 120 = 1005
    #
    # P&L:
    # +5

    assert benchmark_pnl == 5

    assert benchmark_return == 0.5

    assert benchmark_drawdown >= 0

    assert benchmark_profit_dd >= 0


def test_benchmark_forced_liquidation():

    market_data = (
        create_market_data()
    )

    config = (
        create_config(
            force_liquidation=True
        )
    )

    (
        benchmark_pnl,
        _,
        _,
        _,
    ) = (
        calculate_buy_and_hold_benchmark(
            market_data,
            config,
            benchmark_start_index=0,
        )
    )

    # Buy execution:
    # 100 + 5 = 105
    #
    # Entry cost:
    # 10
    #
    # Sell execution:
    # 120 - 5 = 115
    #
    # Exit cost:
    # 10
    #
    # Result:
    # 115 - 105 - 20
    # = -10

    assert benchmark_pnl == -10