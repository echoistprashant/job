import React, { useState, useEffect } from 'react';
import { ArrowLeft, ExternalLink, Sparkles, CheckCircle, AlertTriangle, Building, MapPin, Briefcase } from 'lucide-react';
import { api } from '../services/api';

export default function JobDetailPage({ jobId, onBack }) {
  const [job, setJob] = useState(null);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [matching, setMatching] = useState(false);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        setLoading(true);
        const jobData = await api.getJobDetails(jobId);
        setJob(jobData);

        // Fetch or calculate match
        try {
          const matchData = await api.getJobMatch(jobId);
          setMatch(matchData);
        } catch {
          // If not calculated, auto-trigger calculation
          const computed = await api.matchJob(jobId);
          setMatch(computed);
        }
      } catch (err) {
        console.error('Error fetching job details:', err);
      } finally {
        setLoading(false);
      }
    };

    if (jobId) {
      fetchDetails();
    }
  }, [jobId]);

  const handleRecalculate = async () => {
    try {
      setMatching(true);
      const res = await api.matchJob(jobId);
      setMatch(res);
    } catch (err) {
      alert(`Error recalculating match: ${err.message}`);
    } finally {
      setMatching(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '3rem', textAlign: 'center' }}>Loading job details and calculating match...</div>;
  }

  if (!job) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h3>Job not found.</h3>
        <button className="btn btn-secondary" onClick={onBack} style={{ marginTop: '1rem' }}>
          <ArrowLeft size={16} /> Back to Job List
        </button>
      </div>
    );
  }

  const breakdown = match?.breakdown || {};
  const dimensions = [
    { label: 'Skills Match', weight: '35%', val: breakdown.skills || 0 },
    { label: 'Experience Alignment', weight: '20%', val: breakdown.experience || 0 },
    { label: 'Role Title Fit', weight: '20%', val: breakdown.role || 0 },
    { label: 'Location & Remote', weight: '10%', val: breakdown.location || 0 },
    { label: 'Responsibilities Alignment', weight: '10%', val: breakdown.responsibilities || 0 },
    { label: 'Education Compatibility', weight: '5%', val: breakdown.education || 0 },
  ];

  return (
    <div>
      <button className="btn btn-secondary btn-sm" onClick={onBack} style={{ marginBottom: '1.25rem' }}>
        <ArrowLeft size={14} /> Back to All Jobs
      </button>

      {/* Header Banner */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <span className="pill pill-primary" style={{ textTransform: 'capitalize' }}>
              {job.source}
            </span>
            {job.remote && <span className="pill">Remote Eligible</span>}
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>{job.title}</h1>
          <div style={{ display: 'flex', gap: '1.5rem', color: 'var(--text-muted)', marginTop: '0.5rem', fontSize: '0.95rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Building size={16} /> {job.company}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <MapPin size={16} /> {job.location || 'Remote'}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Briefcase size={16} /> Exp: {job.experience || 'Not specified'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Composite Fit Score</div>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--primary)' }}>
              {match ? `${match.score}%` : 'N/A'}
            </div>
          </div>

          <a href={job.url} target="_blank" rel="noreferrer" className="btn btn-primary">
            Apply on Company Site <ExternalLink size={16} />
          </a>
        </div>
      </div>

      <div className="grid-2">
        {/* Left Column: AI Match Reasoning & Gaps (Phase 21) */}
        <div>
          {/* Qualitative Match Explanation Card */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 className="card-title" style={{ margin: 0 }}>
                <Sparkles size={20} color="var(--primary)" />
                AI Match Evaluation
              </h2>
              <button className="btn btn-secondary btn-sm" onClick={handleRecalculate} disabled={matching}>
                {matching ? 'Analyzing...' : 'Recalculate'}
              </button>
            </div>

            {match ? (
              <div>
                <p style={{ fontSize: '0.95rem', lineHeight: 1.5, marginBottom: '1.25rem', color: 'var(--text-main)' }}>
                  {match.explanation}
                </p>

                {/* Strengths */}
                <div style={{ marginBottom: '1rem' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--success)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <CheckCircle size={16} /> Key Strengths
                  </h4>
                  <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    {match.strengths.map((str, i) => (
                      <li key={i} style={{ marginBottom: '0.25rem' }}>{str}</li>
                    ))}
                  </ul>
                </div>

                {/* Skill Gaps */}
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--danger)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <AlertTriangle size={16} /> Missing Requirements & Gaps
                  </h4>
                  <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    {match.gaps.map((gap, i) => (
                      <li key={i} style={{ marginBottom: '0.25rem' }}>{gap}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)' }}>Match evaluation not yet generated.</p>
            )}
          </div>

          {/* 6-Dimension Score Breakdown */}
          <div className="card">
            <h2 className="card-title">Score Breakdown by Dimension</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {dimensions.map((dim, idx) => (
                <div key={idx}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                    <span>
                      <strong>{dim.label}</strong> <span style={{ color: 'var(--text-muted)' }}>({dim.weight})</span>
                    </span>
                    <span style={{ fontWeight: 600 }}>{dim.val}%</span>
                  </div>
                  <div className="progress-bar-bg">
                    <div className="progress-bar-fill" style={{ width: `${dim.val}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Full Job Description */}
        <div>
          <div className="card">
            <h2 className="card-title">Job Description</h2>
            <div
              style={{
                fontSize: '0.9rem',
                lineHeight: 1.65,
                color: '#334155',
                whiteSpace: 'pre-line',
                maxHeight: '750px',
                overflowY: 'auto',
                paddingRight: '0.5rem',
              }}
            >
              {job.description}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
