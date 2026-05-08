"""Layer 3: Isolation Forest Multivariate Anomaly Detection.

Uses scikit-learn's Isolation Forest to detect anomalies based on
multivariate feature vectors (rolling means, diurnal patterns, etc.).
This catches complex patterns that univariate methods (z-score, peer)
might miss.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Try to import sklearn - may not be available in all environments
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    IsolationForest = Any  # type: ignore


@dataclass
class IsoForestResult:
    """Result of Isolation Forest analysis for a single meter."""

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Anomaly score
    anomaly_score: float  # Negative = more anomalous (Isolation Forest convention)
    is_anomaly: bool  # True if anomaly_score < threshold

    # Feature contributions (approximate)
    feature_names: list[str]
    feature_values: list[float]

    # Context
    model_version: str  # Hash of training data for reproducibility

    # Metadata
    computed_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for layer3_isoforest table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "anomaly_score": self.anomaly_score,
            "is_anomaly": self.is_anomaly,
            "feature_names": self.feature_names,
            "feature_values": self.feature_values,
            "model_version": self.model_version,
            "computed_at": self.computed_at,
        }


class IsoForestAnalyzer:
    """Isolation Forest anomaly detection (Layer 3).

    Trains an Isolation Forest model on normal historical data and
    scores new observations based on multivariate feature vectors.
    """

    def __init__(
        self,
        contamination: float = 0.03,  # Expected proportion of anomalies (PPT spec: 0.03)
        n_estimators: int = 100,
        random_state: int = 42,
        feature_columns: list[str] | None = None,
    ) -> None:
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.feature_columns = feature_columns or [
            "total_kwh",
            "rolling7_kwh",
            "peak_hour_kwh",
            "diurnal_mean",
            "meter_health_score",
            "zero_reading_rate",
            "power_factor",
            "trend_slope",
        ]
        self.model: IsolationForest | None = None
        self.model_version: str = ""

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract feature matrix from DataFrame."""
        # Select only available feature columns
        available = [c for c in self.feature_columns if c in df.columns]
        if not available:
            raise ValueError(f"None of the feature columns {self.feature_columns} found in data")

        features = df[available].fillna(df[available].median())
        return features.values

    def train(self, historical_features: pd.DataFrame) -> bool:
        """Train Isolation Forest on historical normal data.

        Args:
            historical_features: DataFrame with feature columns from normal period

        Returns:
            True if training successful, False if sklearn unavailable
        """
        if not SKLEARN_AVAILABLE:
            return False

        if historical_features.empty:
            return False

        X = self._prepare_features(historical_features)
        if len(X) < 10:
            return False  # Need sufficient data

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        self.model.fit(X)

        # Generate model version from data hash
        self.model_version = self._compute_version(historical_features)
        return True

    def _compute_version(self, df: pd.DataFrame) -> str:
        """Compute deterministic version string from training data."""
        import hashlib
        sample = df.head(100).to_csv(index=False)
        return hashlib.sha256(sample.encode()).hexdigest()[:16]

    def analyze(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        features: pd.Series,  # Single row with feature values
    ) -> IsoForestResult | None:
        """Score a single meter using trained Isolation Forest.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date of analysis
            features: Series with feature values

        Returns:
            IsoForestResult or None if model not trained
        """
        if self.model is None or not SKLEARN_AVAILABLE:
            return None

        # Prepare feature vector
        available = [c for c in self.feature_columns if c in features.index]
        if not available:
            return None

        X = features[available].fillna(0).values.reshape(1, -1)

        # Get anomaly score (negative = more anomalous)
        score = self.model.score_samples(X)[0]

        # Isolation Forest: lower (more negative) = more anomalous
        # Use contamination-based threshold or fixed threshold
        threshold = -0.5  # Empirical threshold; could be tuned
        is_anomaly = score < threshold

        return IsoForestResult(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            anomaly_score=float(score),
            is_anomaly=is_anomaly,
            feature_names=available,
            feature_values=[float(features.get(c, 0)) for c in available],
            model_version=self.model_version,
            computed_at=datetime.utcnow(),
        )

    def analyze_batch(
        self,
        features_df: pd.DataFrame,  # meter_id, dt_id, feeder_id, date, feature columns...
    ) -> list[IsoForestResult]:
        """Analyze all meters in batch.

        Args:
            features_df: DataFrame with meter features

        Returns:
            List of IsoForestResult for each row
        """
        results: list[IsoForestResult] = []

        if self.model is None or features_df.empty:
            return results

        # Get features matrix
        available = [c for c in self.feature_columns if c in features_df.columns]
        if not available:
            return results

        X = features_df[available].fillna(features_df[available].median()).values

        # Batch scoring
        scores = self.model.score_samples(X)

        threshold = -0.5

        for i, (_, row) in enumerate(features_df.iterrows()):
            result = IsoForestResult(
                meter_id=str(row.get("meter_id", "")),
                dt_id=str(row.get("dt_id", "")),
                feeder_id=str(row.get("feeder_id", "")),
                date=row.get("date", date.today()),
                anomaly_score=float(scores[i]),
                is_anomaly=scores[i] < threshold,
                feature_names=available,
                feature_values=[float(row.get(c, 0)) for c in available],
                model_version=self.model_version,
                computed_at=datetime.utcnow(),
            )
            results.append(result)

        return results


def train_and_analyze_csv(
    train_csv: Path,
    analyze_csv: Path,
    output_csv: Path,
    contamination: float = 0.1,
) -> int:
    """CLI helper: train on one CSV, analyze another, write output.

    Returns count of anomalies detected.
    """
    train_df = pd.read_csv(train_csv, parse_dates=["date"])
    analyze_df = pd.read_csv(analyze_csv, parse_dates=["date"])

    analyzer = IsoForestAnalyzer(contamination=contamination)
    if not analyzer.train(train_df):
        return 0

    results = analyzer.analyze_batch(analyze_df)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len([r for r in results if r.is_anomaly])
