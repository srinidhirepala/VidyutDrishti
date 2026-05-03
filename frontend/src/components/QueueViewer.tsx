/**
 * QueueViewer Component
 * 
 * Displays prioritized inspection queue
 */

import { useState, useEffect } from 'react'
import './QueueViewer.css'

interface QueueItem {
  rank: number
  meter_id: string
  dt_id: string
  feeder_id: string
  zone: string | null
  confidence: number
  estimated_inr_lost: number | null
  anomaly_type: string
  description: string
  status: string
}

function QueueViewer() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Mock data - in production fetch from /api/v1/queue/daily
    const mockItems: QueueItem[] = [
      {
        rank: 1,
        meter_id: 'M001',
        dt_id: 'DT001',
        feeder_id: 'F001',
        zone: 'ZoneA',
        confidence: 0.85,
        estimated_inr_lost: 1250,
        anomaly_type: 'sudden_drop',
        description: '40% consumption drop detected',
        status: 'pending',
      },
      {
        rank: 2,
        meter_id: 'M042',
        dt_id: 'DT007',
        feeder_id: 'F003',
        zone: 'ZoneB',
        confidence: 0.72,
        estimated_inr_lost: 890,
        anomaly_type: 'flatline',
        description: '95% zero readings',
        status: 'pending',
      },
    ]

    setTimeout(() => {
      setItems(mockItems)
      setLoading(false)
    }, 500)
  }, [])

  if (loading) {
    return <div className="queue-viewer loading">Loading queue...</div>
  }

  return (
    <div className="queue-viewer">
      <h2>Inspection Queue</h2>
      <table className="queue-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Meter</th>
            <th>Zone</th>
            <th>Type</th>
            <th>Confidence</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.meter_id}>
              <td>{item.rank}</td>
              <td>{item.meter_id}</td>
              <td>{item.zone || '-'}</td>
              <td>{item.anomaly_type}</td>
              <td>{(item.confidence * 100).toFixed(0)}%</td>
              <td>{item.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default QueueViewer
