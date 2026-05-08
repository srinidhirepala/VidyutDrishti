#!/usr/bin/env python3
"""
Show the structure of synthetic data from the simulator.
"""

import sys
from pathlib import Path
import yaml
import pandas as pd

# Add paths
REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "simulator"))

from simulator.dataset import build_dataset
from simulator.models import SimConfig

print("=" * 70)
print("SYNTHETIC DATA STRUCTURE")
print("=" * 70)

# Load simulator config
with open(REPO / "simulator" / "config.yaml") as f:
    raw_config = yaml.safe_load(f)

# Configure for realistic demo
raw_config["days"] = 30
raw_config["meters_per_dt"] = 5
raw_config["theft_scenarios"] = [
    {"meter_id": "DT1-M03", "kind": "hook_bypass", "start_day": 10, "end_day": 30, "severity": 0.85},
    {"meter_id": "DT2-M02", "kind": "gradual_tampering", "start_day": 15, "end_day": 30, "severity": 0.60},
]

config = SimConfig.from_dict(raw_config)

print(f"\n[1] Generating synthetic data...")
dataset = build_dataset(config)

print(f"\n[2] Dataset keys:")
for key in dataset.keys():
    print(f"    - {key}")

print(f"\n[3] METER READINGS:")
print(f"    Shape: {dataset['meter_readings'].shape}")
print(f"    Columns: {list(dataset['meter_readings'].columns)}")
print(f"\n    Head (5 rows):")
print(dataset['meter_readings'].head().to_string(index=False))

print(f"\n[4] DT READINGS:")
print(f"    Shape: {dataset['dt_readings'].shape}")
print(f"    Columns: {list(dataset['dt_readings'].columns)}")
print(f"\n    Head (5 rows):")
print(dataset['dt_readings'].head().to_string(index=False))

print(f"\n[5] CONSUMERS:")
print(f"    Shape: {dataset['consumers'].shape}")
print(f"    Columns: {list(dataset['consumers'].columns)}")
print(f"\n    Head (5 rows):")
print(dataset['consumers'].head().to_string(index=False))

print(f"\n[6] INJECTED EVENTS:")
print(f"    Shape: {dataset['injected_events'].shape}")
print(f"    Columns: {list(dataset['injected_events'].columns)}")
print(f"\n    Head (all rows):")
print(dataset['injected_events'].to_string(index=False))

print("\n" + "=" * 70)
