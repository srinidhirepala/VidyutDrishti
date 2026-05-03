/**
 * Dashboard Component
 * 
 * Shows KPIs: zones at risk, total estimated loss, pending inspections
 */

import { useState, useEffect } from 'react'
import './Dashboard.css'

interface KPIData {
  zonesAtRisk: number
  totalZones: number
  estimatedLossINR: number
  pendingInspections: number
  highConfidenceAnomalies: number
}

function Dashboard() {
  const [kpi, setKpi] = useState<KPIData>({
    zonesAtRisk: 0,
    totalZones: 0,
    estimatedLossINR: 0,
    pendingInspections: 0,
    highConfidenceAnomalies: 0,
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Mock data - in production this would fetch from /api/v1/dashboard/summary
    const mockData: KPIData = {
      zonesAtRisk: 3,
      totalZones: 12,
      estimatedLossINR: 125000,
      pendingInspections: 47,
      highConfidenceAnomalies: 12,
    }
    
    setTimeout(() => {
      setKpi(mockData)
      setLoading(false)
    }, 500)
  }, [])

  if (loading) {
    return <div className="dashboard loading">Loading dashboard...</div>
  }

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>
      
      <div className="kpi-grid">
        <div className="kpi-card risk">
          <h3>Zones at Risk</h3>
          <div className="kpi-value">
            {kpi.zonesAtRisk} <span className="kpi-total">/ {kpi.totalZones}</span>
          </div>
          <div className="kpi-label">
            {((kpi.zonesAtRisk / kpi.totalZones) * 100).toFixed(0)}% of network
          </div>
        </div>

        <div className="kpi-card loss">
          <h3>Estimated Daily Loss</h3>
          <div className="kpi-value">
            ₹{(kpi.estimatedLossINR / 1000).toFixed(1)}K
          </div>
          <div className="kpi-label">Across all detected anomalies</div>
        </div>

        <div className="kpi-card inspections">
          <h3>Pending Inspections</h3>
          <div className="kpi-value">{kpi.pendingInspections}</div>
          <div className="kpi-label">In queue for today</div>
        </div>

        <div className="kpi-card anomalies">
          <h3>High Confidence Anomalies</h3>
          <div className="kpi-value">{kpi.highConfidenceAnomalies}</div>
          <div className="kpi-label">Confidence &gt; 0.8</div>
        </div>
      </div>

      <div className="dashboard-section">
        <h3>Risk Distribution</h3>
        <div className="risk-bars">
          <div className="risk-bar high">
            <span className="risk-label">High Risk</span>
            <div className="risk-fill" style={{width: '25%'}}></div>
            <span className="risk-count">3 zones</span>
          </div>
          <div className="risk-bar medium">
            <span className="risk-label">Medium Risk</span>
            <div className="risk-fill" style={{width: '50%'}}></div>
            <span className="risk-count">6 zones</span>
          </div>
          <div className="risk-bar low">
            <span className="risk-label">Low Risk</span>
            <div className="risk-fill" style={{width: '25%'}}></div>
            <span className="risk-count">3 zones</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
