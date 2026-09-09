import React, { useState, useEffect } from 'react';
import { UploadCloud, Save, UserCheck, Award, BookOpen, Briefcase, Check, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });

  // Form states for editing
  const [targetRolesInput, setTargetRolesInput] = useState('');
  const [locationsInput, setLocationsInput] = useState('');
  const [minMatchScore, setMinMatchScore] = useState(75);
  const [remotePreference, setRemotePreference] = useState(true);
  const [experienceLevel, setExperienceLevel] = useState('Entry Level');

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await api.getProfile();
      setProfile(data);
      if (data) {
        setTargetRolesInput((data.target_roles || []).join(', '));
        setLocationsInput((data.locations || []).join(', '));
        setMinMatchScore(data.minimum_match_score ?? 75);
        setRemotePreference(data.remote_preference ?? true);
        setExperienceLevel(data.experience_level || 'Entry Level');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Failed to load profile: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setFeedback({ type: '', message: '' });
      const resp = await api.uploadResume(file);
      setProfile(resp.profile);
      setTargetRolesInput((resp.profile.target_roles || []).join(', '));
      setLocationsInput((resp.profile.locations || []).join(', '));
      setMinMatchScore(resp.profile.minimum_match_score ?? 75);
      setFeedback({ type: 'success', message: `Resume '${resp.filename}' successfully parsed and profile updated!` });
    } catch (err) {
      setFeedback({ type: 'error', message: `Upload failed: ${err.message}` });
    } finally {
      setUploading(false);
    }
  };

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setFeedback({ type: '', message: '' });

      const roles = targetRolesInput
        .split(',')
        .map((r) => r.trim())
        .filter(Boolean);

      const locs = locationsInput
        .split(',')
        .map((l) => l.trim())
        .filter(Boolean);

      const updated = await api.updateProfile({
        target_roles: roles,
        locations: locs,
        minimum_match_score: parseInt(minMatchScore, 10),
        remote_preference: remotePreference,
        experience_level: experienceLevel,
      });

      setProfile(updated);
      setFeedback({ type: 'success', message: 'Preferences updated successfully!' });
    } catch (err) {
      setFeedback({ type: 'error', message: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading candidate profile...</div>;
  }

  const candidate = profile?.candidate || {};

  return (
    <div>
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Candidate Profile & Resume</h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Upload your resume and customize target preferences for AI matching.
          </p>
        </div>
      </div>

      {feedback.message && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: feedback.type === 'success' ? '#dcfce7' : '#fee2e2',
            color: feedback.type === 'success' ? '#166534' : '#991b1b',
          }}
        >
          {feedback.type === 'success' ? <Check size={18} /> : <AlertCircle size={18} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Resume Upload Card */}
      <div className="card" style={{ borderStyle: 'dashed', borderWidth: '2px', textAlign: 'center', padding: '2rem' }}>
        <UploadCloud size={40} color="var(--primary)" style={{ margin: '0 auto 1rem' }} />
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem' }}>Upload New Resume</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Supports PDF (.pdf) and Word DOCX (.docx) documents.
        </p>
        <label className="btn btn-primary" style={{ cursor: uploading ? 'not-allowed' : 'pointer' }}>
          {uploading ? 'Parsing Resume...' : 'Choose File to Upload'}
          <input
            type="file"
            accept=".pdf,.docx"
            style={{ display: 'none' }}
            onChange={handleFileUpload}
            disabled={uploading}
          />
        </label>
      </div>

      <div className="grid-2">
        {/* Left Column: Parsed Resume Information */}
        <div>
          <div className="card">
            <h2 className="card-title">
              <UserCheck size={20} color="var(--primary)" />
              Candidate Identity
            </h2>
            <div style={{ marginBottom: '1rem' }}>
              <strong style={{ fontSize: '1.25rem', display: 'block' }}>{candidate.name || 'Candidate'}</strong>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                {candidate.email && <div>Email: {candidate.email}</div>}
                {candidate.phone && <div>Phone: {candidate.phone}</div>}
                {candidate.linkedin && (
                  <div>
                    LinkedIn: <a href={candidate.linkedin} target="_blank" rel="noreferrer">{candidate.linkedin}</a>
                  </div>
                )}
                {candidate.github && (
                  <div>
                    GitHub: <a href={candidate.github} target="_blank" rel="noreferrer">{candidate.github}</a>
                  </div>
                )}
              </div>
            </div>

            {candidate.summary && (
              <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', fontSize: '0.875rem' }}>
                <strong>Summary:</strong> {candidate.summary}
              </div>
            )}
          </div>

          <div className="card">
            <h2 className="card-title">
              <Award size={20} color="var(--primary)" />
              Extracted Technical Skills
            </h2>
            <div>
              {(profile?.skills || []).length > 0 ? (
                profile.skills.map((skill, idx) => (
                  <span key={idx} className="pill pill-primary">
                    {skill}
                  </span>
                ))
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  No skills parsed yet. Upload a resume to automatically extract skills.
                </p>
              )}
            </div>
          </div>

          {candidate.experience?.length > 0 && (
            <div className="card">
              <h2 className="card-title">
                <Briefcase size={20} color="var(--primary)" />
                Experience History
              </h2>
              {candidate.experience.map((exp, idx) => (
                <div key={idx} style={{ marginBottom: '0.75rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border)' }}>
                  <strong>{exp.role}</strong> — <span style={{ color: 'var(--text-muted)' }}>{exp.company}</span>
                  <div style={{ fontSize: '0.85rem', marginTop: '0.2rem' }}>{exp.description}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Editable Preferences (Phase 19) */}
        <div>
          <div className="card">
            <h2 className="card-title">
              <BookOpen size={20} color="var(--primary)" />
              Match & Search Preferences
            </h2>
            <form onSubmit={handleSavePreferences}>
              <div className="form-group">
                <label className="form-label">Target Roles (comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  value={targetRolesInput}
                  onChange={(e) => setTargetRolesInput(e.target.value)}
                  placeholder="e.g. AI Engineer, Backend Engineer, ML Engineer"
                />
                <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  The AI Matcher uses these roles to compute role-alignment scores.
                </small>
              </div>

              <div className="form-group">
                <label className="form-label">Preferred Locations (comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  value={locationsInput}
                  onChange={(e) => setLocationsInput(e.target.value)}
                  placeholder="e.g. Remote, Bangalore, India"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Experience Level</label>
                <select
                  className="form-select"
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value)}
                >
                  <option value="Entry Level">Entry Level (0-2 years)</option>
                  <option value="Mid Level">Mid Level (2-5 years)</option>
                  <option value="Senior Level">Senior Level (5+ years)</option>
                </select>
              </div>

              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <label className="form-label" style={{ margin: 0 }}>
                    Minimum Match Score Threshold
                  </label>
                  <span style={{ fontWeight: 700, color: 'var(--primary)' }}>{minMatchScore}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={minMatchScore}
                  onChange={(e) => setMinMatchScore(e.target.value)}
                  style={{ width: '100%' }}
                />
                <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  Jobs scoring below this threshold will be filtered out of recommended lists.
                </small>
              </div>

              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  id="remotePref"
                  checked={remotePreference}
                  onChange={(e) => setRemotePreference(e.target.checked)}
                />
                <label htmlFor="remotePref" style={{ fontSize: '0.875rem', cursor: 'pointer' }}>
                  Prefer remote opportunities
                </label>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={saving}>
                <Save size={16} />
                {saving ? 'Saving...' : 'Save Preferences'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
