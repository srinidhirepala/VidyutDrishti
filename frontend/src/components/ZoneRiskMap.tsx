/**
 * ZoneRiskMap Component
 * 
 * Bengaluru locality-level risk heatmap using Leaflet.
 * Zones colored by risk: HIGH (red), MEDIUM (orange), LOW (green).
 * Click for feeder-level forecast and anomaly summary.
 */

import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './ZoneRiskMap.css'

interface ZoneData {
  id: string
  name: string
  lat: number
  lng: number
  risk: 'HIGH' | 'MEDIUM' | 'LOW'
  riskScore: number
  feederId: string
  peakForecastKw: number
  utilizationPct: number
  pendingInspections: number
  estLossINR: number
}

const ZONES: ZoneData[] = [
  { id: 'Z1', name: 'Malleshwaram', lat: 12.9978, lng: 77.5708, risk: 'HIGH', riskScore: 0.92, feederId: 'F-MAL-01', peakForecastKw: 4600, utilizationPct: 92, pendingInspections: 12, estLossINR: 45000 },
  { id: 'Z2', name: 'Koramangala', lat: 12.9279, lng: 77.6271, risk: 'MEDIUM', riskScore: 0.78, feederId: 'F-KOR-01', peakForecastKw: 3900, utilizationPct: 78, pendingInspections: 8, estLossINR: 32000 },
  { id: 'Z3', name: 'Indiranagar', lat: 12.9719, lng: 77.6412, risk: 'MEDIUM', riskScore: 0.81, feederId: 'F-IND-01', peakForecastKw: 4050, utilizationPct: 81, pendingInspections: 6, estLossINR: 28000 },
  { id: 'Z4', name: 'Jayanagar', lat: 12.9299, lng: 77.5823, risk: 'LOW', riskScore: 0.45, feederId: 'F-JAY-01', peakForecastKw: 2250, utilizationPct: 45, pendingInspections: 4, estLossINR: 15000 },
  { id: 'Z5', name: 'Whitefield', lat: 12.9698, lng: 77.7499, risk: 'LOW', riskScore: 0.32, feederId: 'F-WHI-01', peakForecastKw: 1600, utilizationPct: 32, pendingInspections: 2, estLossINR: 5000 },
  { id: 'Z6', name: 'Rajajinagar', lat: 12.9983, lng: 77.5525, risk: 'HIGH', riskScore: 0.89, feederId: 'F-RAJ-01', peakForecastKw: 4450, utilizationPct: 89, pendingInspections: 10, estLossINR: 38000 },
  { id: 'Z7', name: 'BTM Layout', lat: 12.9165, lng: 77.6101, risk: 'MEDIUM', riskScore: 0.72, feederId: 'F-BTM-01', peakForecastKw: 3600, utilizationPct: 72, pendingInspections: 5, estLossINR: 21000 },
]

const RISK_COLORS = {
  HIGH: '#ef4444',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
}

function ZoneRiskMap() {
  const [selectedZone, setSelectedZone] = useState<ZoneData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setTimeout(() => setLoading(false), 400)
  }, [])

  if (loading) {
    return <div className="zone-map loading">Loading zone risk map...</div>
  }

  return (
    <div className="zone-map">
      <h2>Zone Risk Map — Bengaluru Distribution Network</h2>
      
      <div className="map-legend">
        <div className="legend-item">
          <span className="legend-dot high" />
          <span>HIGH Risk (&gt;88% utilization)</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot medium" />
          <span>MEDIUM Risk (75-88%)</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot low" />
          <span>LOW Risk (&lt;75%)</span>
        </div>
      </div>

      <div className="map-container">
        <MapContainer
          center={[12.95, 77.60]}
          zoom={12}
          scrollWheelZoom={true}
          style={{ height: '500px', width: '100%', borderRadius: '8px' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {ZONES.map((zone) => (
            <CircleMarker
              key={zone.id}
              center={[zone.lat, zone.lng]}
              radius={18 + zone.riskScore * 20}
              fillColor={RISK_COLORS[zone.risk]}
              color={RISK_COLORS[zone.risk]}
              fillOpacity={0.7}
              weight={2}
              eventHandlers={{
                click: () => setSelectedZone(zone),
              }}
            >
              <Popup>
                <div className="zone-popup">
                  <h4>{zone.name}</h4>
                  <div className="popup-row">
                    <span className="popup-label">Risk Level:</span>
                    <span className={`popup-value ${zone.risk.toLowerCase()}`}>{zone.risk}</span>
                  </div>
                  <div className="popup-row">
                    <span className="popup-label">Feeder:</span>
                    <span className="popup-value">{zone.feederId}</span>
                  </div>
                  <div className="popup-row">
                    <span className="popup-label">Peak Forecast:</span>
                    <span className="popup-value">{zone.peakForecastKw.toLocaleString()} kW</span>
                  </div>
                  <div className="popup-row">
                    <span className="popup-label">Utilization:</span>
                    <span className="popup-value">{zone.utilizationPct}%</span>
                  </div>
                  <div className="popup-row">
                    <span className="popup-label">Pending Inspections:</span>
                    <span className="popup-value highlight">{zone.pendingInspections}</span>
                  </div>
                  <div className="popup-row">
                    <span className="popup-label">Est. Loss:</span>
                    <span className="popup-value loss">₹{zone.estLossINR.toLocaleString()}</span>
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {selectedZone && (
        <div className="zone-detail">
          <h3>Zone Detail: {selectedZone.name}</h3>
          <div className="detail-grid">
            <div className="detail-card">
              <h4>Risk Score</h4>
              <div className={`detail-value ${selectedZone.risk.toLowerCase()}`}>
                {(selectedZone.riskScore * 100).toFixed(0)}%
              </div>
            </div>
            <div className="detail-card">
              <h4>Peak Forecast</h4>
              <div className="detail-value">{selectedZone.peakForecastKw.toLocaleString()} kW</div>
            </div>
            <div className="detail-card">
              <h4>Pending Inspections</h4>
              <div className="detail-value">{selectedZone.pendingInspections}</div>
            </div>
            <div className="detail-card">
              <h4>Est. Revenue Loss</h4>
              <div className="detail-value loss">₹{selectedZone.estLossINR.toLocaleString()}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ZoneRiskMap
