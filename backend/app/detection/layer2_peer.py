"""Layer 2: Peer Comparison Anomaly Detection.

Compares each meter against similar meters (same DT, same consumer category)
to identify outliers within peer groups. This catches anomalies that Layer 1
might miss (e.g., if all meters in an area have shifted, individual z-scores
may look normal, but peer comparison reveals the outlier).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class PeerResult:
    """Result of peer comparison analysis for a single meter."""

    meter_id: str
    dt_id: str
    feeder_id: str
    consumer_category: str | None
    date: date

    # Consumption
    actual_kwh: float

    # Peer statistics
    peer_mean: float | None
    peer_std: float | None
    n_peers: int  # Number of meters in peer group

    # Deviation
    deviation_kwh: float | None  # actual - peer_mean
    deviation_pct: float | None  # (actual - peer_mean) / peer_mean * 100

    # Thresholding
    threshold_std: float  # Typically 2.0 (2 sigmas from peer mean)
    is_anomaly: bool  # True if |actual - mean| > threshold_std * std

    # Metadata
    computed_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for layer2_peer table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "consumer_category": self.consumer_category,
            "date": self.date,
            "actual_kwh": self.actual_kwh,
            "peer_mean": self.peer_mean,
            "peer_std": self.peer_std,
            "n_peers": self.n_peers,
            "deviation_kwh": self.deviation_kwh,
            "deviation_pct": self.deviation_pct,
            "threshold_std": self.threshold_std,
            "is_anomaly": self.is_anomaly,
            "computed_at": self.computed_at,
        }


def _compute_peer_stats(
    target_value: float,
    peer_values: pd.Series,
    threshold_std: float,
    min_peers: int = 3,
) -> tuple[float | None, float | None, int, float | None, float | None, bool]:
    """Compute peer statistics and anomaly flag.

    Returns: (mean, std, n_peers, deviation_kwh, deviation_pct, is_anomaly)
    """
    clean = peer_values.dropna()
    if len(clean) < min_peers:
        return None, None, len(clean), None, None, False

    mean = float(clean.mean())
    std = float(clean.std())
    n_peers = len(clean)

    deviation = target_value - mean
    deviation_pct = (deviation / mean * 100.0) if mean != 0 else None

    # Anomaly if more than threshold_std standard deviations from mean
    if std > 0:
        z = abs(deviation) / std
        is_anomaly = z > threshold_std
    else:
        is_anomaly = abs(deviation) > 0.01  # Small tolerance if no variation

    return mean, std, n_peers, deviation, deviation_pct, is_anomaly


class PeerAnalyzer:
    """Peer comparison anomaly detection (Layer 2).

    Compares meters against their peers (same DT, same consumer category)
    to identify relative outliers.
    """

    def __init__(
        self,
        threshold_std: float = 2.0,
        min_peers: int = 3,
    ) -> None:
        self.threshold_std = threshold_std
        self.min_peers = min_peers

    def analyze(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        consumer_category: str | None,
        target_date: date,
        actual_kwh: float,
        peer_kwh: pd.Series,  # Index = meter_id, values = kwh for peers
    ) -> PeerResult | None:
        """Analyze peer comparison for a single meter.

        Args:
            meter_id: Target meter ID
            dt_id: Distribution transformer ID (peer group anchor)
            feeder_id: Feeder/substation ID
            consumer_category: e.g., 'domestic', 'commercial'
            target_date: Date of analysis
            actual_kwh: This meter's consumption
            peer_kwh: Series of peer consumption (excluding this meter)

        Returns:
            PeerResult or None if insufficient peers
        """
        # Exclude self from peers if present
        peer_kwh = peer_kwh[peer_kwh.index != meter_id]

        if len(peer_kwh) < self.min_peers:
            return None

        mean, std, n_peers, dev_kwh, dev_pct, is_anomaly = _compute_peer_stats(
            actual_kwh, peer_kwh, self.threshold_std, self.min_peers
        )

        if mean is None:
            return None

        return PeerResult(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            consumer_category=consumer_category,
            date=target_date,
            actual_kwh=actual_kwh,
            peer_mean=mean,
            peer_std=std,
            n_peers=n_peers,
            deviation_kwh=dev_kwh,
            deviation_pct=dev_pct,
            threshold_std=self.threshold_std,
            is_anomaly=is_anomaly,
            computed_at=datetime.utcnow(),
        )

    def analyze_batch(
        self,
        meter_daily: pd.DataFrame,  # meter_id, date, kwh, consumer_category
        topology: pd.DataFrame,  # meter_id, dt_id, feeder_id
        target_date: date,
    ) -> list[PeerResult]:
        """Analyze peer comparison for all meters in batch.

        Args:
            meter_daily: DataFrame with daily meter readings
            topology: DataFrame with meter-to-DT mapping
            target_date: Date to analyze

        Returns:
            List of PeerResult for meters with sufficient peers
        """
        results: list[PeerResult] = []

        if meter_daily.empty or "date" not in meter_daily.columns:
            return results

        # Filter to target date
        if pd.api.types.is_datetime64_any_dtype(meter_daily["date"]):
            day_data = meter_daily[meter_daily["date"].dt.date == target_date]
        else:
            day_data = meter_daily[meter_daily["date"] == target_date]

        if day_data.empty:
            return results

        # Merge with topology
        merged = day_data.merge(topology, on="meter_id", how="left")

        # Group by DT and category for peer groups
        for (dt_id, category), group in merged.groupby(["dt_id", "consumer_category"]):
            if len(group) < 2:  # Need at least 2 meters for comparison
                continue

            # Build series of all kwh in this group
            peer_series = pd.Series(
                group["kwh"].values,
                index=group["meter_id"].values
            )

            # Analyze each meter against peers
            for _, row in group.iterrows():
                meter_id = str(row["meter_id"])
                feeder_id = str(row.get("feeder_id", ""))
                actual = float(row["kwh"])

                result = self.analyze(
                    meter_id=meter_id,
                    dt_id=str(dt_id),
                    feeder_id=feeder_id,
                    consumer_category=category if pd.notna(category) else None,
                    target_date=target_date,
                    actual_kwh=actual,
                    peer_kwh=peer_series,
                )
                if result is not None:
                    results.append(result)

        return results


def analyze_peer_csv(
    meter_daily_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
    threshold_std: float = 2.0,
) -> int:
    """CLI helper: analyze from CSV files and write output.

    Returns count of meters analyzed.
    """
    meter_daily = pd.read_csv(meter_daily_csv, parse_dates=["date"])
    topology = pd.read_csv(topology_csv)

    analyzer = PeerAnalyzer(threshold_std=threshold_std)
    results = analyzer.analyze_batch(meter_daily, topology, target_date)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)
