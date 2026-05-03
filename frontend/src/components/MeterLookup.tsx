/**
 * MeterLookup Component
 * 
 * Search for meter and display status with detection overlay
 */

import { useState } from 'react'
import './MeterLookup.css'

interface MeterStatus {
  meter_id: string
  date: string
  confidence: number
  is_anomaly: boolean
  anomaly_type: string | null
  layer_signals: {
    l0_is_anomaly: boolean
    l1_is_anomaly: boolean
    l1_z_score: number | null
    l2_is_anomaly: boolean
    l3_is_anomaly: boolean
  }
}

function MeterLookup() {
  const [meterId, setMeterId] = useState('')
  const [status, setStatus] = useState<MeterStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!meterId) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`/api/v1/meters/${meterId.toUpperCase()}/status`)
      if (!res.ok) {
        if (res.status === 404) {
          setError('Meter not found')
        } else {
          setError(`Error: ${res.status}`)
        }
        setStatus(null)
      } else {
        const data = await res.json()
        setStatus(data)
      }
    } catch (err) {
      setError('Network error')
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="meter-lookup">
      <h2>Meter Lookup</h2>
      
      <div className="search-box">
        <input
          type="text"
          value={meterId}
          onChange={(e) => setMeterId(e.target.value)}
          placeholder="Enter meter ID (e.g., M001)"
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {status && (
        <div className={`status-card ${status.is_anomaly ? 'anomaly' : 'normal'}`}>
          <h3>Meter: {status.meter_id}</h3>
          <div className="status-badge">
            {status.is_anomaly ? '⚠️ ANOMALY DETECTED' : '✅ Normal'}
          </div>
          
          {status.is_anomaly && (
            <>
              <div className="anomaly-details">
                <p><strong>Type:</strong> {status.anomaly_type}</p>
                <p><strong>Confidence:</strong> {(status.confidence * 100).toFixed(0)}%</p>
                <p><strong>Date:</strong> {status.date}</p>
              </div>
              
              <div className="layer-signals">
                <h4>Layer Signals</h4>
                <div className="signal-grid">
                  <div className={`signal ${status.layer_signals.l0_is_anomaly ? 'alert' : 'ok'}`}>
                    <span className="layer-name">L0 (DT Balance)</span>
                    <span className="layer-status">{status.layer_signals.l0_is_anomaly ? '⚠️' : '✅'}</span>
                  </div>
                  <div className={`signal ${status.layer_signals.l1_is_anomaly ? 'alert' : 'ok'}`}>
                    <span className="layer-name">L1 (Z-Score)</span>
                    <span className="layer-status">
                      {status.layer_signals.l1_is_anomaly ? `⚠️ z=${status.layer_signals.l1_z_score}` : '✅'}
                    </span>
                  </div>
                  <div className={`signal ${status.layer_signals.l2_is_anomaly ? 'alert' : 'ok'}`}>
                    <span className="layer-name">L2 (Peer)</span>
                    <span className="layer-status">{status.layer_signals.l2_is_anomaly ? '⚠️' : '✅'}</span>
                  </div>
                  <div className={`signal ${status.layer_signals.l3_is_anomaly ? 'alert' : 'ok'}`}>
                    <span className="layer-name">L3 (IsoForest)</span>
                    <span className="layer-status">{status.layer_signals.l3_is_anomaly ? '⚠️' : '✅'}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default MeterLookup
