"""Versioned strategy and execution configuration."""

from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from trading_agent.core.fees import CashEquityFeeSchedule


class StrategyType(str, Enum):
    SMA_BASIC = "sma_basic"
    SMA_CROSSOVER = "sma_crossover"

    # V2 strategy.
    #
    # IMPORTANT:
    # This is intentionally NOT added to the
    # frozen V1 candidate strategy list.
    TREND_MOMENTUM = "trend_momentum"


class SelectorType(str, Enum):
    PNL = "pnl"
    RISK_ADJUSTED = "risk_adjusted"


class ExecutionConfig(BaseModel):
    initial_capital: float = Field(gt=0)

    position_size: int = Field(gt=0)

    transaction_cost: float = Field(ge=0)

    slippage: float = Field(ge=0)

    force_liquidation: bool = False
    fee_schedule: CashEquityFeeSchedule | None = None


class TradingConfig(BaseModel):
    symbol: str

    minimum_confidence: float = Field(
        ge=0,
        le=1,
    )

    max_position_size: int = Field(gt=0)

    initial_capital: float = Field(gt=0)

    transaction_cost: float = Field(ge=0)

    slippage: float = Field(ge=0)

    force_liquidation: bool = False
    fee_schedule: CashEquityFeeSchedule | None = None

    sma_period: int = Field(gt=0)

    fast_sma_period: int = Field(default=20, gt=0)
    slow_sma_period: int = Field(default=50, gt=0)
    rsi_period: int = Field(default=14, gt=0)
    macd_fast_period: int = Field(default=12, gt=0)
    macd_slow_period: int = Field(default=26, gt=0)
    macd_signal_period: int = Field(default=9, gt=0)
    atr_period: int = Field(default=14, gt=0)
    atr_stop_multiple: float = Field(default=2.0, gt=0)

    strategy: StrategyType


class V2Config(BaseModel):
    """Frozen deterministic V2; there is no candidate search space."""

    model_config = ConfigDict(frozen=True)

    symbol: str = "NIFTY"
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    minimum_train_pnl: float = 0
    minimum_train_trades: int = Field(default=5, gt=0)
    train_size: int = Field(default=250, gt=0)
    test_size: int = Field(default=40, gt=0)

    fast_sma_period: int = Field(default=20, gt=0)
    slow_sma_period: int = Field(default=50, gt=0)
    rsi_period: int = Field(default=14, gt=0)
    macd_fast_period: int = Field(default=12, gt=0)
    macd_slow_period: int = Field(default=26, gt=0)
    macd_signal_period: int = Field(default=9, gt=0)
    atr_period: int = Field(default=14, gt=0)
    atr_stop_multiple: float = Field(default=2.0, gt=0)

    execution: ExecutionConfig


class V1Config(BaseModel):
    """
    Frozen deterministic V1 configuration.

    Do not modify V1 based on the consumed
    final holdout result.
    """

    model_config = ConfigDict(
        frozen=True
    )

    symbol: str = "NIFTY"

    minimum_confidence: float = Field(
        default=0.7,
        ge=0,
        le=1,
    )

    selector: SelectorType = (
        SelectorType.RISK_ADJUSTED
    )

    minimum_train_pnl: float = 0

    minimum_train_trades: int = Field(
        default=5,
        gt=0,
    )

    train_size: int = Field(
        default=120,
        gt=0,
    )

    test_size: int = Field(
        default=40,
        gt=0,
    )

    final_holdout_size: int = Field(
        default=250,
        gt=0,
    )

    candidate_sma_periods: tuple[
        int,
        ...
    ] = (
        3,
        10,
        20,
        30,
        50,
    )

    candidate_strategies: tuple[
        StrategyType,
        ...
    ] = (
        StrategyType.SMA_BASIC,
        StrategyType.SMA_CROSSOVER,
    )

    execution: ExecutionConfig


# =====================================================
# FROZEN V1
# =====================================================

V1_CONFIG = V1Config(
    selector=(
        SelectorType.RISK_ADJUSTED
    ),

    minimum_train_pnl=0,

    minimum_train_trades=5,

    train_size=120,

    test_size=40,

    final_holdout_size=250,

    execution=ExecutionConfig(
        initial_capital=100000,

        position_size=1,

        transaction_cost=20,

        slippage=5,

        force_liquidation=False,
    ),
)


V2_CONFIG = V2Config(
    execution=ExecutionConfig(
        initial_capital=100000,
        position_size=1,
        transaction_cost=20,
        slippage=5,
        force_liquidation=False,
    ),
)
