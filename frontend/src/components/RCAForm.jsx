import { useEffect, useState } from 'react'
import { incidentApi } from '../services/api'
import { toast } from '../lib/toast'

const ROOT_CAUSE_CATEGORIES = [
  'HUMAN_ERROR',
  'SOFTWARE_BUG',
  'INFRASTRUCTURE_FAILURE',
  'CAPACITY_EXHAUSTION',
  'EXTERNAL_DEPENDENCY',
  'SECURITY_INCIDENT',
  'CONFIGURATION_ERROR',
]

const inputCls = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition'
const labelCls = 'block text-sm font-semibold text-gray-700 mb-1.5'

const DRAFT_KEY = (id) => `ims_rca_draft_${id}`

function loadDraft(incidentId, existing) {
  if (existing?.root_cause_category) return null       // submitted RCA takes priority
  try { return JSON.parse(localStorage.getItem(DRAFT_KEY(incidentId))) } catch { return null }
}

export default function RCAForm({ incident, onSubmitted, onClose, closing }) {
  const existing = incident.rca
  const draft    = loadDraft(incident.id, existing)

  const [form, setForm] = useState({
    incident_start:      existing?.incident_start?.slice(0, 16) ?? draft?.incident_start ?? toLocalDT(incident.start_time),
    incident_end:        existing?.incident_end?.slice(0, 16)   ?? draft?.incident_end   ?? '',
    root_cause_category: existing?.root_cause_category          ?? draft?.root_cause_category ?? '',
    fix_applied:         existing?.fix_applied                  ?? draft?.fix_applied         ?? '',
    prevention_steps:    existing?.prevention_steps             ?? draft?.prevention_steps     ?? '',
    submitted_by:        existing?.submitted_by                 ?? draft?.submitted_by         ?? '',
  })

  const [submitting, setSubmitting] = useState(false)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  // Save draft locally — no API call, no validation required
  const saveDraft = () => {
    try {
      localStorage.setItem(DRAFT_KEY(incident.id), JSON.stringify(form))
      toast.success('Draft saved locally.')
    } catch {
      toast.error('Could not save draft — check browser storage permissions.')
    }
  }

  // Submit RCA — validate client-side first, then call API
  const submit = async (e) => {
    e?.preventDefault()

    const missing = []
    if (!form.incident_end)        missing.push('Incident End')
    if (!form.root_cause_category) missing.push('Root Cause Category')
    if ((form.fix_applied ?? '').trim().length < 10)       missing.push('Fix Applied (min 10 chars)')
    if ((form.prevention_steps ?? '').trim().length < 10)  missing.push('Prevention Steps (min 10 chars)')

    if (missing.length) {
      toast.warn(`Please complete: ${missing.join(', ')}.`)
      return
    }

    if (form.incident_end && new Date(form.incident_end) <= new Date(form.incident_start)) {
      toast.warn('Incident End must be after Incident Start.')
      return
    }

    setSubmitting(true)
    try {
      await incidentApi.submitRca(incident.id, {
        ...form,
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end:   new Date(form.incident_end).toISOString(),
      })
      localStorage.removeItem(DRAFT_KEY(incident.id))
      toast.success('RCA submitted. You can now close the incident.')
      onSubmitted?.()
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(' · ')
        : (typeof detail === 'string' ? detail : 'Submission failed')
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // Close incident — only gate on RCA completeness.
  // IncidentDetail.closeWithAutoChain handles the state machine walk automatically.
  const handleClose = () => {
    const rcaReady =
      (existing?.root_cause_category || form.root_cause_category) &&
      (existing?.fix_applied?.trim().length >= 10 || form.fix_applied?.trim().length >= 10) &&
      (existing?.prevention_steps?.trim().length >= 10 || form.prevention_steps?.trim().length >= 10) &&
      (existing?.incident_end || form.incident_end)

    if (!rcaReady) {
      toast.warn('Complete and submit the RCA form before closing the incident.')
      return
    }
    onClose?.()
  }

  if (incident.status === 'CLOSED') {
    return (
      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-500 text-center">
        This incident is closed. RCA is locked.
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {/* Date row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Incident Start</label>
          <input
            type="datetime-local"
            value={form.incident_start}
            onChange={set('incident_start')}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Incident End</label>
          <input
            type="datetime-local"
            value={form.incident_end}
            onChange={set('incident_end')}
            className={inputCls}
          />
        </div>
      </div>

      {/* Category */}
      <div>
        <label className={labelCls}>Root Cause Category</label>
        <select value={form.root_cause_category} onChange={set('root_cause_category')} className={inputCls}>
          <option value="">Select root cause category</option>
          {ROOT_CAUSE_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {/* Fix Applied */}
      <div>
        <label className={labelCls}>Fix Applied</label>
        <textarea
          rows={3}
          value={form.fix_applied}
          onChange={set('fix_applied')}
          placeholder="Explain what fix was applied..."
          className={`${inputCls} resize-none`}
        />
      </div>

      {/* Prevention Steps */}
      <div>
        <label className={labelCls}>Prevention Steps</label>
        <textarea
          rows={3}
          value={form.prevention_steps}
          onChange={set('prevention_steps')}
          placeholder="Explain how this issue will be prevented in future..."
          className={`${inputCls} resize-none`}
        />
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-end gap-3 pt-1">
        <button
          type="button"
          onClick={saveDraft}
          disabled={submitting}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 disabled:opacity-50 transition-colors"
        >
          Save Draft
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="px-5 py-2 text-sm font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
        >
          {submitting ? 'Submitting…' : existing ? 'Update RCA' : 'Submit RCA'}
        </button>
        <button
          type="button"
          onClick={handleClose}
          disabled={closing || submitting}
          className="px-4 py-2 text-sm font-semibold rounded-lg bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors"
        >
          {closing ? 'Closing…' : 'Close Incident'}
        </button>
      </div>
    </form>
  )
}

function toLocalDT(iso) {
  if (!iso) return ''
  const d   = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
