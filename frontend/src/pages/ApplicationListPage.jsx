import React, { useState, useEffect } from 'react';
import { Briefcase, CheckCircle2, Clock, AlertTriangle, AlertCircle, Eye, ExternalLink } from 'lucide-react';
import { api } from '../services/api';

export default function ApplicationListPage({ onSelectApplication }) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState(null);

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

  const getStatusBadge = (status) => {
    switch (status) {
      case 'SUBMITTED':
        return <span className="badge badge-success"><CheckCircle2 size={12} /> Submitted</span>;
      case 'APPROVED':
        return <span className="badge badge-primary"><CheckCircle2 size={12} /> Approved</span>;
      case 'READY':
        return <span className="badge badge-warning"><Clock size={12} /> Draft Ready</span>;
      case 'FAILED':
        return <span className="badge badge-danger"><AlertCircle size={12} /> Failed</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <div className="application-list-page" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}>Job Applications</h1>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Inspect drafts, provide human-in-the-loop approvals, and monitor controlled submissions.
          </p>
        </div>

        {/* Status Filter */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            className={`btn btn-sm ${statusFilter === '' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setStatusFilter('')}
          >
            All
          </button>
          <button
            className={`btn btn-sm ${statusFilter === 'READY' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setStatusFilter('READY')}
          >
            Drafts
          </button>
          <button
            className={`btn btn-sm ${statusFilter === 'APPROVED' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setStatusFilter('APPROVED')}
          >
            Approved
          </button>
          <button
            className={`btn btn-sm ${statusFilter === 'SUBMITTED' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setStatusFilter('SUBMITTED')}
          >
            Submitted
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="empty-state"><p>Loading applications...</p></div>
      ) : applications.length === 0 ? (
        <div className="card empty-state">
          <Briefcase size={36} color="#94a3b8" />
          <p style={{ marginTop: '0.75rem', fontWeight: 500 }}>No applications found.</p>
          <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Go to the Job Board, select a matching position, and prepare an application draft.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {applications.map(app => (
            <div key={app.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.35rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '1.05rem', color: '#0f172a' }}>
                    Application #{app.id}
                  </span>
                  {getStatusBadge(app.status)}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                  Source: <strong>{app.source}</strong> • Updated: {new Date(app.updated_at).toLocaleString()}
                </div>
                {app.applied_at && (
                  <div style={{ fontSize: '0.8rem', color: '#16a34a', marginTop: '0.2rem' }}>
                    Submitted on: {new Date(app.applied_at).toLocaleString()}
                  </div>
                )}
                {app.failure_reason && (
                  <div style={{ fontSize: '0.8rem', color: '#dc2626', marginTop: '0.2rem' }}>
                    Alert: {app.failure_reason}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => onSelectApplication(app.id)}
                >
                  <Eye size={14} /> Review & Approve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
