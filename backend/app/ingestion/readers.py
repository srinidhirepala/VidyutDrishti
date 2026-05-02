"""Source readers.

For the prototype only a CSV reader is implemented; the interface is
shaped so a future Kafka or MQTT reader can be slotted in without any
change to the loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Protocol

import pandas as pd


class SourceReader(Protocol):
    """Yield DataFrames in whatever natural batch size the source emits."""

    def read_meter_readings(self) -> Iterator[pd.DataFrame]: ...
    def read_dt_readings(self) -> Iterator[pd.DataFrame]: ...
    def read_consumers(self) -> pd.DataFrame: ...


class CSVReader:
    """Read the simulator's on-disk output."""

    def __init__(self, root: Path, batch_rows: int = 50_000) -> None:
        self.root = Path(root)
        self.batch_rows = batch_rows

    # -- time series (streamed) ------------------------------------------

    def _iter_csv(self, filename: str) -> Iterator[pd.DataFrame]:
        path = self.root / filename
        if not path.exists():
            return
        for chunk in pd.read_csv(path, chunksize=self.batch_rows, parse_dates=["ts"]):
            yield chunk

    def read_meter_readings(self) -> Iterator[pd.DataFrame]:
        yield from self._iter_csv("meter_readings.csv")

    def read_dt_readings(self) -> Iterator[pd.DataFrame]:
        yield from self._iter_csv("dt_readings.csv")

    # -- dimensions (small) ----------------------------------------------

    def read_consumers(self) -> pd.DataFrame:
        path = self.root / "consumers.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def read_dts(self) -> pd.DataFrame:
        path = self.root / "dts.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def read_injected_events(self) -> pd.DataFrame:
        path = self.root / "injected_events.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
