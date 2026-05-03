/**
 * FeedbackForm Component
 * 
 * Capture inspection feedback for recalibration
 */

import { useState } from 'react'
import './FeedbackForm.css'

interface FeedbackData {
  meter_id: string
  inspection_date: string
  was_anomaly: boolean
  actual_kwh_observed: string
  notes: string
}

function FeedbackForm() {
  const [form, setForm] = useState<FeedbackData>({
    meter_id: '',
    inspection_date: new Date().toISOString().split('T')[0],
    was_anomaly: true,
    actual_kwh_observed: '',
    notes: '',
  })
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    // Mock API call - in production: POST /api/v1/feedback
    setTimeout(() => {
      setLoading(false)
      setSubmitted(true)
    }, 500)
  }

  if (submitted) {
    return (
      <div className="feedback-form success">
        <h2>Feedback Submitted</h2>
        <p>Thank you! Your inspection feedback has been recorded.</p>
        <button onClick={() => {
          setSubmitted(false)
          setForm({
            meter_id: '',
            inspection_date: new Date().toISOString().split('T')[0],
            was_anomaly: true,
            actual_kwh_observed: '',
            notes: '',
          })
        }}>
          Submit Another
        </button>
      </div>
    )
  }

  return (
    <div className="feedback-form">
      <h2>Inspection Feedback</h2>
      <p className="form-description">
        Record the outcome of your field inspection to help improve detection accuracy.
      </p>
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="meter_id">Meter ID</label>
          <input
            type="text"
            id="meter_id"
            value={form.meter_id}
            onChange={(e) => setForm({...form, meter_id: e.target.value})}
            placeholder="e.g., M001"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="inspection_date">Inspection Date</label>
          <input
            type="date"
            id="inspection_date"
            value={form.inspection_date}
            onChange={(e) => setForm({...form, inspection_date: e.target.value})}
            required
          />
        </div>

        <div className="form-group">
          <label>Was an anomaly confirmed?</label>
          <div className="radio-group">
            <label className="radio-label">
              <input
                type="radio"
                checked={form.was_anomaly}
                onChange={() => setForm({...form, was_anomaly: true})}
              />
              Yes - Theft/Meter Fault Found
            </label>
            <label className="radio-label">
              <input
                type="radio"
                checked={!form.was_anomaly}
                onChange={() => setForm({...form, was_anomaly: false})}
              />
              No - Normal Reading
            </label>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="actual_kwh">Actual kWh Observed (optional)</label>
          <input
            type="number"
            id="actual_kwh"
            value={form.actual_kwh_observed}
            onChange={(e) => setForm({...form, actual_kwh_observed: e.target.value})}
            placeholder="e.g., 150"
            step="0.1"
          />
        </div>

        <div className="form-group">
          <label htmlFor="notes">Notes</label>
          <textarea
            id="notes"
            value={form.notes}
            onChange={(e) => setForm({...form, notes: e.target.value})}
            placeholder="Describe what you found..."
            rows={4}
          />
        </div>

        <button type="submit" disabled={loading || !form.meter_id}>
          {loading ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </form>
    </div>
  )
}

export default FeedbackForm
