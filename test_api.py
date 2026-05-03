#!/usr/bin/env python3
"""Test the VidyutDrishti API with real algorithm computation."""

import requests
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Health: {resp.status_code} - {resp.json()}")
    return resp.status_code == 200

def ingest_data():
    """Ingest 30 days of synthetic data with theft pattern."""
    readings = []

    # Generate 30 days of readings for two meters
    for day in range(1, 31):
        date_str = f'2024-01-{day:02d}'
        for hour in range(24):
            # DT01-M01: Normal for first 20 days, then sudden drop (theft)
            if day <= 20:
                kwh_m1 = 2.5
            else:
                kwh_m1 = 0.5  # 80% drop - theft

            # DT01-M02: Always normal (for peer comparison)
            kwh_m2 = 2.5

            readings.append({
                'meter_id': 'DT01-M01',
                'timestamp': f'{date_str}T{hour:02d}:00:00',
                'kwh': kwh_m1,
                'voltage': 230.0,
                'pf': 0.95
            })
            readings.append({
                'meter_id': 'DT01-M02',
                'timestamp': f'{date_str}T{hour:02d}:00:00',
                'kwh': kwh_m2,
                'voltage': 230.0,
                'pf': 0.95
            })

    print(f"Generated {len(readings)} readings")

    resp = requests.post(f"{BASE_URL}/api/v1/ingest/batch", json=readings)
    print(f"Ingest status: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"  Received: {result['records_received']}")
        print(f"  Valid: {result['records_valid']}")
        print(f"  Written: {result['records_written']}")
        return True
    else:
        print(f"  Error: {resp.text}")
        return False

def test_meter_status():
    """Test meter status endpoint with real algorithm computation."""
    # Query for day 25 (after theft started)
    resp = requests.get(f"{BASE_URL}/api/v1/meters/DT01-M01/status", params={'date': '2024-01-25'})
    print(f"Meter status (DT01-M01, theft meter): {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Meter: {data.get('meter_id')}")
        print(f"  Confidence: {data.get('confidence')}")
        print(f"  Is Anomaly: {data.get('is_anomaly')}")
        print(f"  Anomaly Type: {data.get('anomaly_type')}")
        print(f"  Layer Signals: {data.get('layer_signals')}")
        return True
    else:
        print(f"  Error: {resp.text}")
        return False

def test_normal_meter():
    """Test normal meter for comparison."""
    resp = requests.get(f"{BASE_URL}/api/v1/meters/DT01-M02/status", params={'date': '2024-01-25'})
    print(f"Meter status (DT01-M02, normal meter): {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Meter: {data.get('meter_id')}")
        print(f"  Confidence: {data.get('confidence')}")
        print(f"  Is Anomaly: {data.get('is_anomaly')}")
        return True
    else:
        print(f"  Error: {resp.text}")
        return False

def test_queue():
    """Test inspection queue endpoint."""
    resp = requests.get(f"{BASE_URL}/api/v1/queue/daily")
    print(f"Queue status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total items: {data.get('total_items')}")
        print(f"  Pending items: {data.get('pending_items')}")
        items = data.get('items', [])
        if items:
            print(f"  Top item: {items[0]['meter_id']} (confidence: {items[0]['confidence']})")
        return True
    else:
        print(f"  Error: {resp.text}")
        return False

def test_forecast():
    """Test forecast endpoint."""
    resp = requests.get(f"{BASE_URL}/api/v1/forecast/F001")
    print(f"Forecast status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Feeder: {data.get('feeder_id')}")
        print(f"  Zone Risk: {data.get('zone_risk')}")
        print(f"  Risk Score: {data.get('risk_score')}")
        print(f"  Peak Forecast: {data.get('peak_forecast_kw')} kW")
        print(f"  Points count: {len(data.get('points', []))}")
        return True
    else:
        print(f"  Error: {resp.text}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("VIDYUTDRISHTI API TEST")
    print("=" * 60)

    results = []

    print("\n[1] Testing health endpoint...")
    results.append(("Health", test_health()))

    print("\n[2] Ingesting test data...")
    results.append(("Ingest", ingest_data()))

    print("\n[3] Testing meter status (theft pattern)...")
    results.append(("Meter Status (Theft)", test_meter_status()))

    print("\n[4] Testing meter status (normal)...")
    results.append(("Meter Status (Normal)", test_normal_meter()))

    print("\n[5] Testing inspection queue...")
    results.append(("Queue", test_queue()))

    print("\n[6] Testing forecast...")
    results.append(("Forecast", test_forecast()))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("All tests passed!" if all_passed else "Some tests failed."))
