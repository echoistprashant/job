import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  CheckCircle2,
  Clock,
  AlertCircle,
  Eye,
  Calendar,
  Award,
  XCircle,
  History,
  Edit3,
  Filter,
  Check,
  ChevronRight,
  TrendingUp
} from 'lucide-react';
import { api } from '../services/api';

export default function ApplicationListPage({ onSelectApplication }) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState(null);

  // Status Update Modal State
  const [updatingApp, setUpdatingApp] = useState(null);
  const [newStatus, setNewStatus] = useState('INTERVIEW');
  const [statusNote, setStatusNote] = useState('');
  const [interviewRound, setInterviewRound] = useState('Recruiter Screen');
  const [interviewDate, setInterviewDate] = useState('');
  const [interviewerName, setInterviewerName] = useState('');
  const [statusSubmitting, setStatusSubmitting] = useState(false);

  // Audit History Modal State
  const [historyApp, setHistoryApp] = useState(null);

  const fetchApps = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listApplications(statusFilter || undefined);
      setApplications(res.items || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch applications.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApps();
  }, [statusFilter]);

  const handleOpenStatusModal = (app) => {
    setUpdatingApp(app);
    setNewStatus(app.status === 'SUBMITTED' ? 'INTERVIEW' : app.status);
    setStatusNote('');
    setInterviewRound('Recruiter Screen');
    setInterviewDate('');
    setInterviewerName('');
  };

  const handleSaveStatus = async (e) => {
    e.preventDefault();
    if (!updatingApp) return;
    setStatusSubmitting(true);
    try {
      const payload = {
        status: newStatus,
        note: statusNote || undefined,
        actor: 'user',
      };
      if (newStatus === 'INTERVIEW') {
        payload.interview_details = {
          round: interviewRound,
          date: interviewDate || undefined,
          interviewer: interviewerName || undefined,
        };
      }
      await api.updateApplicationStatus(updatingApp.id, payload);
      setUpdatingApp(null);
      await fetchApps();
    } catch (err) {
      alert(`Error updating status: ${err.message}`);
    } finally {
      setStatusSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'OFFER':
        return (
          <span className="badge" style={{ backgroundColor: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0' }}>
            <Award size={12} /> Offer
          </span>
        );
      case 'INTERVIEW':
        return (
          <span className="badge" style={{ backgroundColor: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>
            <Calendar size={12} /> Interviewing
          </span>
        );
      case 'SUBMITTED':
        return (
          <span className="badge badge-success">
            <CheckCircle2 size={12} /> Submitted
          </span>
        );
      case 'APPROVED':
        return (
          <span className="badge badge-primary">
            <CheckCircle2 size={12} /> Approved
          </span>
        );
      case 'READY':
        return (
          <span className="badge badge-warning">
            <Clock size={12} /> Draft Ready
          </span>
        );
      case 'REJECTED':
        return (
          <span className="badge" style={{ backgroundColor: '#fff1f2', color: '#be123c', border: '1px solid #fecdd3' }}>
            <XCircle size={12} /> Rejected
          </span>
        );
      case 'WITHDRAWN':
        return (
          <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>
            Withdrawn
          </span>
        );
      case 'FAILED':
        return (
          <span className="badge badge-danger">
            <AlertCircle size={12} /> Failed
          </span>
        );
      default:
        return <span className="badge">{status}</span>;
    }
  };

  // Funnel counts calculation across fetched items
  const counts = {
    total: applications.length,
    drafts: applications.filter(a => a.status === 'READY' || a.status === 'SAVED').length,
    approved: applications.filter(a => a.status === 'APPROVED').length,
    submitted: applications.filter(a => a.status === 'SUBMITTED').length,
    interviews: applications.filter(a => a.status === 'INTERVIEW').length,
    offers: applications.filter(a => a.status === 'OFFER').length,
  };

  return (
    <div className="application-tracker-page" style={{ maxWidth: '1100px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}>
            Application Tracker & Funnel
          </h1>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Track your recruitment lifecycle from draft preparation through interview rounds and offers.
          </p>
        </div>
      </div>

      {/* KPI Funnel Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #6366f1' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>TOTAL APPS</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', marginTop: '0.25rem' }}>
            {counts.total}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #f59e0b' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>DRAFTS READY</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#d97706', marginTop: '0.25rem' }}>
            {counts.drafts}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #3b82f6' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>APPROVED</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#2563eb', marginTop: '0.25rem' }}>
            {counts.approved}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #10b981' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>SUBMITTED</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#059669', marginTop: '0.25rem' }}>
            {counts.submitted}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #8b5cf6' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>INTERVIEWS</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#7c3aed', marginTop: '0.25rem' }}>
            {counts.interviews}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #059669', background: '#f0fdf4' }}>
          <div style={{ fontSize: '0.8rem', color: '#047857', fontWeight: 600 }}>OFFERS</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#047857', marginTop: '0.25rem' }}>
            {counts.offers}
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', marginBottom: '1.25rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
        {[
          { label: 'All', value: '' },
          { label: 'Drafts', value: 'READY' },
          { label: 'Approved', value: 'APPROVED' },
          { label: 'Submitted', value: 'SUBMITTED' },
          { label: 'Interviewing', value: 'INTERVIEW' },
          { label: 'Offers', value: 'OFFER' },
          { label: 'Rejected', value: 'REJECTED' },
          { label: 'Withdrawn', value: 'WITHDRAWN' },
          { label: 'Failed', value: 'FAILED' },
        ].map(tab => (
          <button
            key={tab.value}
            className={`btn btn-sm ${statusFilter === tab.value ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setStatusFilter(tab.value)}
            style={{ whiteSpace: 'nowrap' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="card" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Applications Table / Cards */}
      {loading ? (
        <div className="empty-state"><p>Loading application tracker...</p></div>
      ) : applications.length === 0 ? (
        <div className="card empty-state">
          <Briefcase size={36} color="#94a3b8" />
          <p style={{ marginTop: '0.75rem', fontWeight: 500 }}>No applications found in this view.</p>
          <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Discover jobs on the Job Board and prepare an application draft to start tracking.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {applications.map(app => (
            <div key={app.id} className="card" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.35rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '1.1rem', color: '#0f172a' }}>
                      Application #{app.id}
                    </span>
                    {getStatusBadge(app.status)}
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      • Job ID: {app.job_id}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                    Source: <strong style={{ color: '#334155' }}>{app.source}</strong> • Created: {new Date(app.created_at).toLocaleDateString()}
                    {app.applied_at && (
                      <span style={{ marginLeft: '0.5rem', color: '#16a34a' }}>
                        • Submitted: {new Date(app.applied_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  {/* Interview info if present */}
                  {app.interview_details && (
                    <div style={{ marginTop: '0.5rem', padding: '0.4rem 0.75rem', background: '#f8fafc', borderRadius: '4px', borderLeft: '3px solid #3b82f6', fontSize: '0.85rem' }}>
                      <strong>Interview Stage:</strong> {app.interview_details.round || 'Active'}
                      {app.interview_details.date && ` • Scheduled: ${app.interview_details.date}`}
                      {app.interview_details.interviewer && ` • With: ${app.interview_details.interviewer}`}
                    </div>
                  )}

                  {/* Notes / Failure Alert */}
                  {app.notes && (
                    <div style={{ marginTop: '0.4rem', fontSize: '0.85rem', color: '#475569', fontStyle: 'italic' }}>
                      "{app.notes}"
                    </div>
                  )}
                  {app.failure_reason && (
                    <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#dc2626' }}>
                      Alert: {app.failure_reason}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => setHistoryApp(app)}
                    title="View lifecycle history"
                  >
                    <History size={14} /> History ({app.status_history?.length || 1})
                  </button>

                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => handleOpenStatusModal(app)}
                    title="Update status"
                  >
                    <Edit3 size={14} /> Update Status
                  </button>

                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => onSelectApplication(app.id)}
                  >
                    <Eye size={14} /> Review Draft
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* STATUS UPDATE MODAL */}
      {updatingApp && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(15, 23, 42, 0.6)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem'
        }}>
          <div className="card" style={{ maxWidth: '500px', width: '100%', background: '#fff', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.25rem' }}>
              Update Status: Application #{updatingApp.id}
            </h3>

            <form onSubmit={handleSaveStatus}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Target Lifecycle Status
                </label>
                <select
                  className="input"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  style={{ width: '100%' }}
                >
                  <option value="READY">READY (Draft Prepared)</option>
                  <option value="APPROVED">APPROVED (Approved for Submission)</option>
                  <option value="SUBMITTED">SUBMITTED (Application Sent)</option>
                  <option value="INTERVIEW">INTERVIEW (Interviewing)</option>
                  <option value="OFFER">OFFER (Offer Extended)</option>
                  <option value="REJECTED">REJECTED (Candidate Not Selected)</option>
                  <option value="WITHDRAWN">WITHDRAWN (Withdrawn by Candidate)</option>
                  <option value="FAILED">FAILED (Submission Error)</option>
                </select>
              </div>

              {/* Conditional Interview Fields */}
              {newStatus === 'INTERVIEW' && (
                <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '6px', marginBottom: '1rem', border: '1px solid #e2e8f0' }}>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                      Interview Round / Stage
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={interviewRound}
                      onChange={(e) => setInterviewRound(e.target.value)}
                      placeholder="e.g. Recruiter Screen, Technical Interview, System Design"
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                        Date / Time
                      </label>
                      <input
                        type="date"
                        className="input"
                        value={interviewDate}
                        onChange={(e) => setInterviewDate(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                        Interviewer(s)
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={interviewerName}
                        onChange={(e) => setInterviewerName(e.target.value)}
                        placeholder="e.g. Jane Doe (Tech Lead)"
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Status Notes / Feedback
                </label>
                <textarea
                  className="input"
                  rows={3}
                  value={statusNote}
                  onChange={(e) => setStatusNote(e.target.value)}
                  placeholder="e.g. Recruiter contacted via email, positive technical feedback, etc."
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setUpdatingApp(null)}
                  disabled={statusSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={statusSubmitting}
                >
                  {statusSubmitting ? 'Saving...' : 'Update Status'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AUDIT HISTORY MODAL */}
      {historyApp && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(15, 23, 42, 0.6)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem'
        }}>
          <div className="card" style={{ maxWidth: '600px', width: '100%', maxHeight: '80vh', overflowY: 'auto', background: '#fff', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem' }}>
                Lifecycle History: Application #{historyApp.id}
              </h3>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setHistoryApp(null)}
              >
                Close
              </button>
            </div>

            {(!historyApp.status_history || historyApp.status_history.length === 0) ? (
              <p style={{ color: '#64748b' }}>No status transitions recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {historyApp.status_history.map((entry, idx) => (
                  <div key={idx} style={{ borderLeft: '3px solid #6366f1', paddingLeft: '1rem', position: 'relative' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                      {entry.from_status && (
                        <>
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{entry.from_status}</span>
                          <ChevronRight size={12} color="#94a3b8" />
                        </>
                      )}
                      <strong style={{ color: '#0f172a' }}>{entry.to_status}</strong>
                      <span className="badge" style={{ fontSize: '0.7rem', padding: '2px 6px' }}>
                        by {entry.actor || 'system'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                      {new Date(entry.timestamp).toLocaleString()}
                    </div>
                    {entry.note && (
                      <div style={{ fontSize: '0.85rem', color: '#334155', marginTop: '0.25rem' }}>
                        {entry.note}
                      </div>
                    )}
                    {entry.interview_details && (
                      <div style={{ fontSize: '0.8rem', color: '#2563eb', marginTop: '0.25rem', background: '#eff6ff', padding: '0.3rem 0.6rem', borderRadius: '4px' }}>
                        Round: {entry.interview_details.round}
                        {entry.interview_details.date && ` • Date: ${entry.interview_details.date}`}
                        {entry.interview_details.interviewer && ` • With: ${entry.interview_details.interviewer}`}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
