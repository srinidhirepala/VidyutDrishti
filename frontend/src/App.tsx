/**
 * VidyutDrishti React Dashboard
 * 
 * Feature 18: React + Vite + TypeScript dashboard
 * - Dashboard view with zone risk, loss KPIs
 * - Inspection queue viewer
 * - Meter status lookup with detection overlay
 * - Feedback capture form
 */

import { useState } from 'react'
import './App.css'
import Dashboard from './components/Dashboard'
import QueueViewer from './components/QueueViewer'
import MeterLookup from './components/MeterLookup'
import FeedbackForm from './components/FeedbackForm'
import ZoneRiskMap from './components/ZoneRiskMap'
import EvaluationMetrics from './components/EvaluationMetrics'
import ROICalculator from './components/ROICalculator'

type View = 'dashboard' | 'queue' | 'meter' | 'feedback' | 'map' | 'metrics' | 'roi'

function App() {
  const [currentView, setCurrentView] = useState<View>('dashboard')
  const [mapVisited, setMapVisited] = useState(false)

  const handleViewChange = (view: View) => {
    if (view === 'map') setMapVisited(true)
    setCurrentView(view)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>VidyutDrishti</h1>
        <nav className="app-nav">
          <button 
            className={currentView === 'dashboard' ? 'active' : ''}
            onClick={() => handleViewChange('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={currentView === 'queue' ? 'active' : ''}
            onClick={() => handleViewChange('queue')}
          >
            Inspection Queue
          </button>
          <button 
            className={currentView === 'meter' ? 'active' : ''}
            onClick={() => handleViewChange('meter')}
          >
            Meter Lookup
          </button>
          <button 
            className={currentView === 'feedback' ? 'active' : ''}
            onClick={() => handleViewChange('feedback')}
          >
            Feedback
          </button>
          <button 
            className={currentView === 'map' ? 'active' : ''}
            onClick={() => handleViewChange('map')}
          >
            Zone Map
          </button>
          <button
            className={currentView === 'metrics' ? 'active' : ''}
            onClick={() => handleViewChange('metrics')}
          >
            Metrics
          </button>
          <button
            className={currentView === 'roi' ? 'active' : ''}
            onClick={() => handleViewChange('roi')}
          >
            ROI
          </button>
        </nav>
      </header>

      <main className="app-main">
        <div style={{ display: currentView === 'dashboard' ? 'block' : 'none' }}><Dashboard /></div>
        <div style={{ display: currentView === 'queue' ? 'block' : 'none' }}><QueueViewer /></div>
        <div style={{ display: currentView === 'meter' ? 'block' : 'none' }}><MeterLookup /></div>
        <div style={{ display: currentView === 'feedback' ? 'block' : 'none' }}><FeedbackForm /></div>
        {mapVisited && <div style={{ display: currentView === 'map' ? 'block' : 'none' }}><ZoneRiskMap /></div>}
        <div style={{ display: currentView === 'metrics' ? 'block' : 'none' }}><EvaluationMetrics /></div>
        <div style={{ display: currentView === 'roi' ? 'block' : 'none' }}><ROICalculator /></div>
      </main>
    </div>
  )
}

export default App
