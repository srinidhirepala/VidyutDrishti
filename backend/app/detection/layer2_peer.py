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

    # Anomaly if more than threshold_std standard deviations from mean,
    # OR if percentage deviation exceeds 60% (handles heterogeneous peer groups
    # where inflated std suppresses the z-score despite extreme absolute deviation)
    pct_anomaly = deviation_pct is not None and abs(deviation_pct) > 60.0
    if std > 0:
        z = abs(deviation) / std
        is_anomaly = z > threshold_std or pct_anomaly
    else:
        is_anomaly = abs(deviation) > 0.01 or pct_anomaly

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

    def _compute_streak_counts(
        self,
        meter_daily: pd.DataFrame,
        topology: pd.DataFrame,
        target_date: date,
        streak_days: int,
    ) -> dict[str, int]:
        """Count how many days in the streak window each meter was anomalously below peers.

        Only counts days where the meter's deviation from peer mean exceeds threshold_std
        (matching the same criterion used in per-day anomaly flagging).
        """
        import datetime as _dt

        cutoff = target_date - _dt.timedelta(days=streak_days - 1)

        # Filter first (P4.1: avoid full copy of multi-month dataset)
        if pd.api.types.is_datetime64_any_dtype(meter_daily["date"]):
            mask = (meter_daily["date"].dt.date >= cutoff) & (meter_daily["date"].dt.date <= target_date)
        else:
            mask = (meter_daily["date"] >= cutoff) & (meter_daily["date"] <= target_date)

        window = meter_daily.loc[mask].copy()
        if window.empty:
            return {}

        if pd.api.types.is_datetime64_any_dtype(window["date"]):
            window["_date"] = window["date"].dt.date
        else:
            window["_date"] = window["date"]

        streak_merged = window.merge(topology, on="meter_id", how="left")
        if streak_merged.empty or "dt_id" not in streak_merged.columns:
            return {}

        # Compute per-(dt, category, date) peer mean and std — same grouping as analyze()
        peer_stats = (
            streak_merged.groupby(["dt_id", "consumer_category", "_date"])["kwh"]
            .agg(["mean", "std"])
            .reset_index()
            .rename(columns={"mean": "_peer_mean", "std": "_peer_std"})
        )
        streak_merged = streak_merged.merge(
            peer_stats, on=["dt_id", "consumer_category", "_date"], how="left"
        )
        streak_merged["_peer_std"] = streak_merged["_peer_std"].fillna(0)

        # Vectorised flag: below peer by > threshold_std * std (or > 0.01 when std=0)
        dev = streak_merged["kwh"] - streak_merged["_peer_mean"]
        has_std = streak_merged["_peer_std"] > 0
        streak_merged["_flagged"] = (
            (dev < 0)
            & (
                (has_std & (dev.abs() / streak_merged["_peer_std"].clip(lower=1e-9) > self.threshold_std))
                | (~has_std & (dev.abs() > 0.01))
            )
        )

        # Vectorised consecutive-streak count ending on target_date.
        # For each meter, sort by date, assign a "break group" id (cumsum on ~_flagged),
        # then the streak = size of the last group only if its last day == target_date.
        sm = streak_merged[["meter_id", "_date", "_flagged"]].sort_values(
            ["meter_id", "_date"]
        )
        sm["_break"] = (~sm["_flagged"]).astype(int)
        sm["_group"] = sm.groupby("meter_id")["_break"].cumsum()

        # For each (meter, group) count the days and find the max date in that group
        grp_stats = (
            sm.groupby(["meter_id", "_group"])
            .agg(streak_len=("_flagged", "sum"), last_date=("_date", "max"))
            .reset_index()
        )
        # Only keep the last group per meter (highest _group id = most recent run)
        last_grp = grp_stats.sort_values("_group").groupby("meter_id").last().reset_index()
        # Streak only counts if the run ends exactly on target_date (unbroken up to today)
        last_grp["_streak"] = last_grp.apply(
            lambda r: int(r["streak_len"]) if r["last_date"] == target_date else 0,
            axis=1,
        )
        return last_grp.set_index("meter_id")["_streak"].astype(int).to_dict()

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

        # 5-consecutive-day streak check per spec
        STREAK_DAYS = 5
        streak_counts = self._compute_streak_counts(
            meter_daily, topology, target_date, STREAK_DAYS
        )

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
                    # Apply 5-consecutive-day streak requirement:
                    # only flag as anomaly if meter has been below peer for STREAK_DAYS days
                    if result.is_anomaly and (result.deviation_kwh or 0) < 0:
                        streak = streak_counts.get(meter_id, 0)
                        if streak < STREAK_DAYS:
                            result.is_anomaly = False
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
