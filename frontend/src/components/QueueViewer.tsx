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
    const fetchQueue = async () => {
      try {
        const res = await fetch('/api/v1/queue/daily')
        if (!res.ok) throw new Error('Failed to fetch queue')
        const data = await res.json()
        setItems(data.items || [])
      } catch (err) {
        console.error('Queue fetch error:', err)
        setItems([])
      } finally {
        setLoading(false)
      }
    }
    fetchQueue()
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
