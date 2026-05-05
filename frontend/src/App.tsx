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

  return (
    <div className="app">
      <header className="app-header">
        <h1>VidyutDrishti</h1>
        <nav className="app-nav">
          <button 
            className={currentView === 'dashboard' ? 'active' : ''}
            onClick={() => setCurrentView('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={currentView === 'queue' ? 'active' : ''}
            onClick={() => setCurrentView('queue')}
          >
            Inspection Queue
          </button>
          <button 
            className={currentView === 'meter' ? 'active' : ''}
            onClick={() => setCurrentView('meter')}
          >
            Meter Lookup
          </button>
          <button 
            className={currentView === 'feedback' ? 'active' : ''}
            onClick={() => setCurrentView('feedback')}
          >
            Feedback
          </button>
          <button 
            className={currentView === 'map' ? 'active' : ''}
            onClick={() => setCurrentView('map')}
          >
            Zone Map
          </button>
          <button
            className={currentView === 'metrics' ? 'active' : ''}
            onClick={() => setCurrentView('metrics')}
          >
            Metrics
          </button>
          <button
            className={currentView === 'roi' ? 'active' : ''}
            onClick={() => setCurrentView('roi')}
          >
            ROI
          </button>
        </nav>
      </header>

      <main className="app-main">
        {currentView === 'dashboard' && <Dashboard />}
        {currentView === 'queue' && <QueueViewer />}
        {currentView === 'meter' && <MeterLookup />}
        {currentView === 'feedback' && <FeedbackForm />}
        {currentView === 'map' && <ZoneRiskMap />}
        {currentView === 'metrics' && <EvaluationMetrics />}
        {currentView === 'roi' && <ROICalculator />}
      </main>

      <footer className="app-footer">
        <p>VidyutDrishti Prototype • Feature 18 • React + Vite + TypeScript</p>
      </footer>
    </div>
  )
}

export default App
