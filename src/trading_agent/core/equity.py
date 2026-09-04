"""Cash-equity instrument and shared-portfolio research configuration."""

from pydantic import BaseModel, ConfigDict, Field


class EquityInstrument(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    tick_size: float = Field(default=0.05, gt=0)
    quantity_step: int = Field(default=1, gt=0)
    minimum_median_volume: int = Field(default=100_000, ge=0)


class EquityPortfolioConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    initial_capital: float = Field(default=1_000_000, gt=0)
    max_positions: int = Field(default=5, gt=0)
    allocation_fraction: float = Field(default=0.20, gt=0, le=1)
    transaction_cost: float = Field(default=20.0, ge=0)
    slippage: float = Field(default=0.05, ge=0)
    reserved_holdout_sessions: int = Field(default=250, gt=0)


V3_STEP4_PORTFOLIO_CONFIG = EquityPortfolioConfig()

