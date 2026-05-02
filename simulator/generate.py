"""CLI entrypoint: ``python -m simulator.generate --config ... --out ...``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

from .dataset import build_dataset
from .models import SimConfig

log = logging.getLogger("simulator")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VidyutDrishti synthetic data simulator")
    p.add_argument("--config", type=Path, default=Path("simulator/config.yaml"))
    p.add_argument("--out", type=Path, default=Path("data"))
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    raw = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    cfg = SimConfig.from_dict(raw)

    args.out.mkdir(parents=True, exist_ok=True)
    log.info("Generating dataset: %d DTs x %d meters x %d days",
             cfg.dt_count, cfg.meters_per_dt, cfg.days)

    result = build_dataset(cfg)
    for name, df in result.items():
        path = args.out / f"{name}.csv"
        df.to_csv(path, index=False)
        log.info("Wrote %s (%d rows)", path, len(df))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
