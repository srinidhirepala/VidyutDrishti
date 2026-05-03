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

type View = 'dashboard' | 'queue' | 'meter' | 'feedback'

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
        </nav>
      </header>

      <main className="app-main">
        {currentView === 'dashboard' && <Dashboard />}
        {currentView === 'queue' && <QueueViewer />}
        {currentView === 'meter' && <MeterLookup />}
        {currentView === 'feedback' && <FeedbackForm />}
      </main>

      <footer className="app-footer">
        <p>VidyutDrishti Prototype • Feature 18 • React + Vite + TypeScript</p>
      </footer>
    </div>
  )
}

export default App
