from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StrategyType(str, Enum):
    SMA_BASIC = "sma_basic"
    SMA_CROSSOVER = "sma_crossover"


class SelectorType(str, Enum):
    PNL = "pnl"
    RISK_ADJUSTED = "risk_adjusted"


class ExecutionConfig(BaseModel):
    initial_capital: float = Field(gt=0)

    position_size: int = Field(gt=0)

    # Simplified round-trip transaction cost.
    transaction_cost: float = Field(ge=0)

    # Adverse execution movement in NIFTY points.
    slippage: float = Field(ge=0)

    # False:
    # Keep final open position and mark it to market.
    #
    # True:
    # Explicitly liquidate final open position.
    force_liquidation: bool = False


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

    sma_period: int = Field(gt=0)

    strategy: StrategyType


class V1Config(BaseModel):
    """
    Frozen deterministic V1 research configuration.

    Once we run the final holdout, this configuration
    should NOT be changed and the holdout rerun.
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

    # -------------------------------------------------
    # Frozen model-selection policy
    # -------------------------------------------------

    selector: SelectorType = (
        SelectorType.RISK_ADJUSTED
    )

    minimum_train_pnl: float = 0

    minimum_train_trades: int = Field(
        default=5,
        gt=0,
    )

    # -------------------------------------------------
    # Walk-forward configuration
    # -------------------------------------------------

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

    # -------------------------------------------------
    # Candidate search space
    # -------------------------------------------------

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

    # -------------------------------------------------
    # Execution assumptions
    # -------------------------------------------------

    execution: ExecutionConfig


# =====================================================
# FROZEN V1 CONFIGURATION
# =====================================================

V1_CONFIG = V1Config(
    selector=SelectorType.RISK_ADJUSTED,

    minimum_train_pnl=0,
    minimum_train_trades=5,

    train_size=120,
    test_size=40,

    final_holdout_size=250,

    execution=ExecutionConfig(
        initial_capital=100000,
        position_size=1,
        transaction_cost=20,

        # Deliberately non-zero execution assumption.
        slippage=5,

        # Preserve our existing accounting behavior.
        force_liquidation=False,
    ),
)