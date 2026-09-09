import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Send,
  Sparkles,
  Edit3,
  Save,
  ShieldCheck,
  FileText,
  User,
  Briefcase,
  HelpCircle,
  AlertCircle,
  ExternalLink,
  Lock
} from 'lucide-react';
import { api } from '../services/api';

export default function ApplicationReviewPage({ applicationId, onBack }) {
  const [application, setApplication] = useState(null);
  const [job, setJob] = useState(null);
  const [match, setMatch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generatingAi, setGeneratingAi] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Editable state
  const [editedFields, setEditedFields] = useState({});
  const [editedAnswers, setEditedAnswers] = useState({});
  const [editedCoverLetter, setEditedCoverLetter] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const appData = await api.getApplication(applicationId);
      setApplication(appData);
      setEditedFields(appData.filled_fields || {});
      setEditedAnswers(appData.answers || {});
      setEditedCoverLetter(appData.cover_letter || '');

      if (appData.job_id) {
        try {
          const jobData = await api.getJobDetails(appData.job_id);
          setJob(jobData);
        } catch (e) {
          console.error("Could not fetch job:", e);
        }

        try {
          const matchData = await api.getJobMatch(appData.job_id);
          setMatch(matchData);
        } catch (e) {
          console.debug("No pre-existing match:", e);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load application review data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [applicationId]);

  const handleFieldChange = (key, val) => {
    setEditedFields(prev => ({ ...prev, [key]: val }));
  };

  const handleAnswerChange = (qId, val) => {
    setEditedAnswers(prev => ({
      ...prev,
      [qId]: {
        ...(typeof prev[qId] === 'object' ? prev[qId] : {}),
        answer: val,
        needs_review: false
      }
    }));
  };

  const handleSaveEdits = async () => {
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await api.updateApplicationContent(applicationId, {
        filled_fields: editedFields,
        answers: editedAnswers,
        cover_letter: editedCoverLetter
      });
      setApplication(updated);
      setSuccessMsg('Changes saved successfully.');
    } catch (err) {
      setError(err.message || 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      // Save any pending edits first
      await api.updateApplicationContent(applicationId, {
        filled_fields: editedFields,
        answers: editedAnswers,
        cover_letter: editedCoverLetter
      });
      const approved = await api.approveApplication(applicationId);
      setApplication(approved);
      setSuccessMsg('Application explicitly APPROVED. Ready for final submission.');
    } catch (err) {
      setError(err.message || 'Failed to approve application.');
    } finally {
      setApproving(false);
    }
  };

  const handleSubmit = async () => {
    if (application.status !== 'APPROVED') {
      setError('You must explicitly approve this application before submitting.');
      return;
    }

    if (!window.confirm('Are you sure you want to proceed with live submission through browser automation?')) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await api.submitApplication(applicationId);
      if (result.success) {
        setSuccessMsg(result.confirmation_message || 'Application submitted successfully!');
      } else {
        setError(result.failure_reason || 'Submission failed. Halting without retrying.');
      }
      // Refresh application record
      const refreshed = await api.getApplication(applicationId);
      setApplication(refreshed);
    } catch (err) {
      setError(err.message || 'Submission error.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerateCoverLetter = async () => {
    setGeneratingAi(true);
    setError(null);
    try {
      const cl = await api.generateCoverLetter(applicationId, 'professional');
      setEditedCoverLetter(cl.full_text);
      setApplication(prev => ({ ...prev, cover_letter: cl.full_text }));
      setSuccessMsg('Tailored cover letter generated.');
    } catch (err) {
      setError(err.message || 'Failed to generate cover letter.');
    } finally {
      setGeneratingAi(false);
    }
  };

  const handleTailorResume = async () => {
    setGeneratingAi(true);
    setError(null);
    try {
      const tailored = await api.tailorResume(applicationId);
      setApplication(prev => ({ ...prev, tailored_resume: tailored, resume_version: tailored.version_id }));
      setSuccessMsg('Resume tailored for this role with verified factual integrity.');
    } catch (err) {
      setError(err.message || 'Failed to tailor resume.');
    } finally {
      setGeneratingAi(false);
    }
  };

  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading application review...</p>
      </div>
    );
  }

  if (error && !application) {
    return (
      <div className="card">
        <div className="badge badge-danger">Error</div>
        <p style={{ marginTop: '1rem' }}>{error}</p>
        <button className="btn btn-outline" onClick={onBack} style={{ marginTop: '1rem' }}>
          <ArrowLeft size={16} /> Back
        </button>
      </div>
    );
  }

  const isApproved = application?.status === 'APPROVED';
  const isSubmitted = application?.status === 'SUBMITTED';
  const isFailed = application?.status === 'FAILED';

  return (
    <div className="application-review-page" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Top Navigation & Status Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <button className="btn btn-outline" onClick={onBack}>
          <ArrowLeft size={16} /> Back to Dashboard
        </button>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <span className={`badge ${
            isSubmitted ? 'badge-success' : isApproved ? 'badge-primary' : isFailed ? 'badge-danger' : 'badge-warning'
          }`} style={{ fontSize: '0.9rem', padding: '0.35rem 0.75rem' }}>
            Status: {application.status}
          </span>
        </div>
      </div>

      {/* Main Header Card */}
      <div className="card" style={{ marginBottom: '1.5rem', background: 'linear-gradient(to right, #ffffff, #f8fafc)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.85rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Application Review & Approval Checkpoint
            </span>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0.25rem 0', color: '#0f172a' }}>
              {job?.title || 'Target Job Position'}
            </h1>
            <p style={{ color: '#475569', margin: 0, display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <span><strong>{job?.company || 'Company'}</strong></span>
              <span>•</span>
              <span>{job?.location || 'Location'}</span>
              {job?.remote && <span className="badge badge-success">Remote</span>}
              {job?.url && (
                <a href={job.url} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#2563eb' }}>
                  Job Listing <ExternalLink size={14} />
                </a>
              )}
            </p>
          </div>

          {match && (
            <div style={{ textAlign: 'right', background: '#f1f5f9', padding: '0.75rem 1.25rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Match Score</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: match.overall_score >= 75 ? '#16a34a' : '#d97706' }}>
                {Math.round(match.overall_score)}%
              </div>
            </div>
          )}
        </div>

        {/* Human-in-the-loop checkpoint notice */}
        <div style={{
          marginTop: '1.25rem',
          padding: '0.85rem 1rem',
          borderRadius: '6px',
          background: '#eff6ff',
          borderLeft: '4px solid #3b82f6',
          display: 'flex',
          gap: '0.75rem',
          alignItems: 'center',
          fontSize: '0.9rem',
          color: '#1e40af'
        }}>
          <ShieldCheck size={20} />
          <div>
            <strong>Human-in-the-Loop Safeguard:</strong> Inspect every proposed value and AI answer below. You can make inline corrections, save edits, and then explicitly click <strong>Approve Application</strong> to unlock submission.
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            className="btn btn-outline"
            onClick={handleSaveEdits}
            disabled={saving || isSubmitted}
          >
            <Save size={16} /> {saving ? 'Saving...' : 'Save Edits'}
          </button>

          {!isApproved && !isSubmitted && (
            <button
              className="btn btn-primary"
              onClick={handleApprove}
              disabled={approving}
              style={{ background: '#16a34a', borderColor: '#16a34a' }}
            >
              <CheckCircle2 size={16} /> {approving ? 'Approving...' : 'Approve Application'}
            </button>
          )}

          {isApproved && !isSubmitted && (
            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting}
              style={{ background: '#2563eb', borderColor: '#2563eb' }}
            >
              <Send size={16} /> {submitting ? 'Submitting via Playwright...' : 'Submit Application'}
            </button>
          )}
        </div>
      </div>

      {/* Feedback Messages */}
      {successMsg && (
        <div className="card" style={{ background: '#f0fdf4', borderColor: '#bbf7d0', color: '#166534', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CheckCircle2 size={18} /> {successMsg}
        </div>
      )}

      {error && (
        <div className="card" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertTriangle size={18} /> {error}
        </div>
      )}

      {/* Confirmation Details Card if Submitted */}
      {isSubmitted && application.confirmation_details && (
        <div className="card" style={{ background: '#f0fdf4', borderColor: '#86efac', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#15803d', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle2 size={20} /> Submission Confirmation Audit
          </h3>
          <p style={{ margin: '0.25rem 0', fontSize: '0.95rem' }}>
            <strong>Outcome:</strong> {application.confirmation_details.message || 'Submitted successfully'}
          </p>
          {application.confirmation_details.url && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.9rem', color: '#475569' }}>
              <strong>Landing URL:</strong> {application.confirmation_details.url}
            </p>
          )}
          {application.applied_at && (
            <p style={{ margin: '0.25rem 0', fontSize: '0.9rem', color: '#475569' }}>
              <strong>Timestamp:</strong> {new Date(application.applied_at).toLocaleString()}
            </p>
          )}
        </div>
      )}

      {/* Failure Recovery Card if Failed */}
      {isFailed && application.failure_reason && (
        <div className="card" style={{ background: '#fff1f2', borderColor: '#fecdd3', marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#be123c', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={20} /> Submission Halted Safely (Loop Prevention)
          </h3>
          <p style={{ margin: '0.25rem 0', color: '#9f1239', fontSize: '0.95rem' }}>
            <strong>Reason:</strong> {application.failure_reason}
          </p>
          <p style={{ margin: '0.25rem 0', fontSize: '0.85rem', color: '#64748b' }}>
            Execution stopped immediately to prevent duplicate submissions or form lockouts. Correct any issues above and re-approve when ready.
          </p>
        </div>
      )}

      {/* Section 1: Candidate Contact & Proposed Field Values */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.25rem', margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <User size={20} color="#2563eb" /> 1. Proposed Contact & Profile Fields
        </h2>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>
          Values autofilled from your candidate profile for standard form inputs.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {Object.entries(editedFields).map(([key, val]) => (
            <div key={key}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#334155', marginBottom: '0.25rem', textTransform: 'capitalize' }}>
                {key.replace(/_/g, ' ')}
              </label>
              <input
                type="text"
                className="input"
                value={val || ''}
                disabled={isSubmitted}
                onChange={(e) => handleFieldChange(key, e.target.value)}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Section 2: Screening Questions & AI Answers */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1.25rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <HelpCircle size={20} color="#8b5cf6" /> 2. Screening Questions & Grounded AI Answers
          </h2>
        </div>

        {Object.keys(editedAnswers).length === 0 ? (
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>No custom screening questions detected on this application form.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {Object.entries(editedAnswers).map(([qId, ansObj]) => {
              const ansText = typeof ansObj === 'object' ? ansObj.answer : ansObj;
              const prompt = typeof ansObj === 'object' ? ansObj.prompt : qId;
              const needsReview = typeof ansObj === 'object' ? ansObj.needs_review : false;
              const confidence = typeof ansObj === 'object' ? ansObj.confidence : 1.0;
              const facts = typeof ansObj === 'object' ? ansObj.grounded_facts : [];

              return (
                <div key={qId} style={{
                  padding: '1rem',
                  borderRadius: '8px',
                  background: needsReview ? '#fffbeb' : '#f8fafc',
                  border: needsReview ? '1px solid #fef3c7' : '1px solid #e2e8f0'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <div style={{ fontWeight: 600, color: '#1e293b' }}>
                      {prompt || qId}
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {needsReview && (
                        <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <AlertTriangle size={12} /> Needs Review
                        </span>
                      )}
                      <span className="badge badge-primary">
                        Confidence: {Math.round((confidence || 1.0) * 100)}%
                      </span>
                    </div>
                  </div>

                  <textarea
                    rows={3}
                    className="input"
                    value={ansText || ''}
                    disabled={isSubmitted}
                    onChange={(e) => handleAnswerChange(qId, e.target.value)}
                    style={{ width: '100%', marginBottom: '0.5rem' }}
                  />

                  {facts && facts.length > 0 && (
                    <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      <strong>Grounded Sources:</strong> {facts.join(', ')}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Section 3: Tailored Cover Letter */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontSize: '1.25rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={20} color="#059669" /> 3. Tailored Cover Letter
          </h2>
          {!isSubmitted && (
            <button className="btn btn-outline" onClick={handleGenerateCoverLetter} disabled={generatingAi}>
              <Sparkles size={14} /> Regenerate with AI
            </button>
          )}
        </div>

        <textarea
          rows={10}
          className="input"
          value={editedCoverLetter}
          disabled={isSubmitted}
          onChange={(e) => setEditedCoverLetter(e.target.value)}
          placeholder="No cover letter drafted yet. Click 'Regenerate with AI' to compose one."
          style={{ width: '100%', fontFamily: 'inherit', lineHeight: '1.6' }}
        />
      </div>

      {/* Section 4: Tailored Resume Version */}
      {application.tailored_resume && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1.25rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Briefcase size={20} color="#d97706" /> 4. Tailored Resume Breakdown
            </h2>
            <span className="badge badge-success">
              <CheckCircle2 size={12} /> Factual Integrity Verified
            </span>
          </div>

          <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem' }}>
            <strong>Target Headline:</strong> {application.tailored_resume.headline}
          </p>
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: '#475569' }}>
            <strong>Summary:</strong> {application.tailored_resume.tailored_summary}
          </p>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155', marginBottom: '0.5rem' }}>
              Highlighted Matching Skills:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {application.tailored_resume.highlighted_skills?.map(skill => (
                <span key={skill} className="badge badge-primary">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
