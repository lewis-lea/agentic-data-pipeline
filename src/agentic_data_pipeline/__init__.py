"""Tools for ingesting, standardizing, analyzing, and persisting time-series data."""

from importlib.metadata import PackageNotFoundError, version

from agentic_data_pipeline.incremental import (
    update_yfinance_distributions,
    update_yfinance_market_data,
)
from agentic_data_pipeline.metrics import (
    DEFAULT_BENCHMARK,
    add_benchmark_metrics,
    add_stock_metrics,
    benchmark_statistics,
    time_series_diagnostics,
)
from agentic_data_pipeline.returns import build_return_history
from agentic_data_pipeline.storage import DatasetKey, ParquetStorage
from agentic_data_pipeline.types import (
    MARKET_DATA_COLUMNS,
    create_market_data,
    validate_market_data,
)

try:
    __version__ = version("agentic-data-pipeline")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "DEFAULT_BENCHMARK",
    "DatasetKey",
    "MARKET_DATA_COLUMNS",
    "ParquetStorage",
    "add_benchmark_metrics",
    "add_stock_metrics",
    "benchmark_statistics",
    "build_return_history",
    "create_market_data",
    "time_series_diagnostics",
    "update_yfinance_distributions",
    "update_yfinance_market_data",
    "validate_market_data",
]
