import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Zap,
  Sliders,
  BarChart2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Play,
  Settings,
  Target,
  Award,
  Calendar,
  Layers,
  Activity,
  RefreshCw
} from 'lucide-react';
import { api } from '../services/api';

export default function AutoApplyPage() {
  const [activeTab, setActiveTab] = useState('policy'); // 'policy' | 'analytics'
  const [policy, setPolicy] = useState(null);
  const [quota, setQuota] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningCycle, setRunningCycle] = useState(false);
  const [cycleReport, setCycleReport] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form State
  const [enabled, setEnabled] = useState(false);
  const [minScore, setMinScore] = useState(80);
  const [targetRoles, setTargetRoles] = useState('');
  const [allowedLocations, setAllowedLocations] = useState('');
  const [remoteOnly, setRemoteOnly] = useState(true);
  const [maxPerDay, setMaxPerDay] = useState(5);
  const [requireGrounded, setRequireGrounded] = useState(true);
  const [excludedCompanies, setExcludedCompanies] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [pol, q, met] = await Promise.all([
        api.getAutoApplyPolicy(),
        api.getDailyQuota(),
        api.getAnalyticsOverview(),
      ]);
      setPolicy(pol);
      setQuota(q);
      setMetrics(met);

      // Populate form
      setEnabled(pol.enabled);
      setMinScore(pol.minimum_match_score);
      setTargetRoles((pol.target_roles || []).join(', '));
      setAllowedLocations((pol.allowed_locations || []).join(', '));
      setRemoteOnly(pol.remote_only);
      setMaxPerDay(pol.max_applications_per_day);
      setRequireGrounded(pol.require_all_skills_grounded);
      setExcludedCompanies((pol.excluded_companies || []).join(', '));
    } catch (err) {
      console.error('Failed to load auto-apply configuration:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      const updatedPolicy = {
        enabled,
        minimum_match_score: Number(minScore),
        target_roles: targetRoles.split(',').map(s => s.trim()).filter(Boolean),
        allowed_locations: allowedLocations.split(',').map(s => s.trim()).filter(Boolean),
        remote_only: remoteOnly,
        max_applications_per_day: Number(maxPerDay),
        require_all_skills_grounded: requireGrounded,
        excluded_companies: excludedCompanies.split(',').map(s => s.trim()).filter(Boolean),
      };
      const res = await api.updateAutoApplyPolicy(updatedPolicy);
      setPolicy(res);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      const q = await api.getDailyQuota();
      setQuota(q);
    } catch (err) {
      alert(`Failed to save policy: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRunAutoApply = async () => {
    setRunningCycle(true);
    setCycleReport(null);
    try {
      const res = await api.runAutoApplyNow({ force_run: true });
      setCycleReport(res);
      await loadData();
    } catch (err) {
      alert(`Auto-apply cycle failed: ${err.message}`);
    } finally {
      setRunningCycle(false);
    }
  };

  if (loading) {
    return (
      <div className="empty-state" style={{ maxWidth: '800px', margin: '3rem auto', textAlign: 'center' }}>
        <p>Loading Auto-Apply settings & analytics...</p>
      </div>
    );
  }

  return (
    <div className="auto-apply-page" style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}>
            Controlled Auto-Apply & Telemetry
          </h1>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Configure safety thresholds, rules, daily limits, and monitor production conversion rates.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className={`btn btn-sm ${activeTab === 'policy' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setActiveTab('policy')}
          >
            <Sliders size={14} /> Rules & Policy
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'analytics' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setActiveTab('analytics')}
          >
            <BarChart2 size={14} /> Telemetry & Metrics
          </button>
        </div>
      </div>

      {/* Daily Quota Ribbon */}
      <div className="card" style={{ padding: '0.85rem 1.25rem', marginBottom: '1.5rem', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Activity size={18} color="#6366f1" />
            <div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#1e293b' }}>
                Daily Auto-Apply Quota: {quota?.submitted_today || 0} / {quota?.max_per_day || 5} Used
              </span>
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                {quota?.remaining_today || 0} applications remaining today • Master Switch:{' '}
                <strong style={{ color: enabled ? '#10b981' : '#f59e0b' }}>
                  {enabled ? 'ENABLED' : 'DISABLED'}
                </strong>
              </div>
            </div>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleRunAutoApply}
            disabled={runningCycle}
          >
            <Zap size={14} className={runningCycle ? 'spin' : ''} />
            {runningCycle ? 'Processing Auto-Apply...' : 'Run Auto-Apply Now'}
          </button>
        </div>
      </div>

      {/* Cycle Report Notification */}
      {cycleReport && (
        <div className="card" style={{
          padding: '1rem 1.25rem', marginBottom: '1.5rem',
          background: cycleReport.submitted_count > 0 ? '#f0fdf4' : '#eff6ff',
          borderColor: cycleReport.submitted_count > 0 ? '#bbf7d0' : '#bfdbfe'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            <CheckCircle2 size={16} color="#16a34a" />
            Auto-Apply Cycle Completed: {cycleReport.summary_message}
          </div>
          <div style={{ fontSize: '0.85rem', color: '#475569' }}>
            Evaluated: {cycleReport.evaluated_count} • Submitted: {cycleReport.submitted_count} • Escalated to Human Review: {cycleReport.escalated_count} • Skipped: {cycleReport.skipped_count}
          </div>
        </div>
      )}

      {/* TAB 1: RULES & POLICY (Phases 48 & 49) */}
      {activeTab === 'policy' && (
        <div className="card" style={{ padding: '1.5rem' }}>
          <form onSubmit={handleSavePolicy}>
            {/* Master Toggle */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '1rem', background: enabled ? '#f0fdf4' : '#fffbeb',
              borderRadius: '6px', border: `1px solid ${enabled ? '#bbf7d0' : '#fde68a'}`,
              marginBottom: '1.5rem'
            }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: enabled ? '#166534' : '#92400e' }}>
                  Automated Application Submissions: {enabled ? 'Active' : 'Disabled'}
                </div>
                <div style={{ fontSize: '0.8rem', color: enabled ? '#15803d' : '#b45309', marginTop: '0.2rem' }}>
                  {enabled
                    ? 'The agent will prepare, verify, and submit qualifying jobs satisfying all safety rules.'
                    : 'Applications will stop in READY state for your manual review and approval.'}
                </div>
              </div>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                style={{ width: '20px', height: '20px', cursor: 'pointer' }}
              />
            </div>

            {/* Minimum Match Score Slider */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                  Minimum Match Score Threshold
                </label>
                <span className="badge badge-primary" style={{ fontSize: '0.95rem' }}>
                  {minScore}%
                </span>
              </div>
              <input
                type="range"
                min="60"
                max="95"
                step="5"
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8' }}>
                <span>60% (Broad)</span>
                <span>80% (Recommended)</span>
                <span>95% (Strictly High Confidence)</span>
              </div>
            </div>

            {/* Daily Ceiling */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.35rem' }}>
                Daily Application Limit (Safety Ceiling)
              </label>
              <input
                type="number"
                className="input"
                min="1"
                max="50"
                value={maxPerDay}
                onChange={(e) => setMaxPerDay(e.target.value)}
                style={{ maxWidth: '200px' }}
              />
              <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0.25rem 0 0 0' }}>
                Caps the maximum number of automated submissions per calendar day to avoid spamming.
              </p>
            </div>

            {/* Target Roles */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.35rem' }}>
                Target Job Roles (Comma-separated)
              </label>
              <input
                type="text"
                className="input"
                value={targetRoles}
                onChange={(e) => setTargetRoles(e.target.value)}
                placeholder="AI Engineer, Full Stack Engineer, Python Developer"
                style={{ width: '100%' }}
              />
            </div>

            {/* Locations */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.35rem' }}>
                Allowed Locations (Comma-separated)
              </label>
              <input
                type="text"
                className="input"
                value={allowedLocations}
                onChange={(e) => setAllowedLocations(e.target.value)}
                placeholder="Remote, India, United States"
                style={{ width: '100%' }}
              />
            </div>

            {/* Remote Only */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <input
                type="checkbox"
                id="remoteOnlyToggle"
                checked={remoteOnly}
                onChange={(e) => setRemoteOnly(e.target.checked)}
              />
              <label htmlFor="remoteOnlyToggle" style={{ fontSize: '0.9rem', fontWeight: 500, cursor: 'pointer' }}>
                Strictly Remote-Only Positions
              </label>
            </div>

            {/* Require 100% Grounded Answers */}
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
              padding: '0.85rem', background: '#f8fafc', borderRadius: '6px',
              border: '1px solid #e2e8f0', marginBottom: '1.5rem'
            }}>
              <input
                type="checkbox"
                id="groundedToggle"
                checked={requireGrounded}
                onChange={(e) => setRequireGrounded(e.target.checked)}
                style={{ marginTop: '0.2rem' }}
              />
              <div>
                <label htmlFor="groundedToggle" style={{ fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer' }}>
                  Mandatory Human Escalation for Uncertain Questions (Safety Gate)
                </label>
                <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0.2rem 0 0 0' }}>
                  If any screening question cannot be answered with high confidence (&gt;80%) using verified facts from your resume, the application will be flagged and halted for your manual inspection.
                </p>
              </div>
            </div>

            {/* Excluded Companies */}
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.35rem' }}>
                Excluded Companies (Comma-separated blacklist)
              </label>
              <input
                type="text"
                className="input"
                value={excludedCompanies}
                onChange={(e) => setExcludedCompanies(e.target.value)}
                placeholder="e.g. CurrentEmployer, BadCompany Inc"
                style={{ width: '100%' }}
              />
            </div>

            {/* Submit */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={saving}
              >
                {saving ? 'Saving Policy...' : 'Save Policy Settings'}
              </button>
              {saveSuccess && (
                <span style={{ color: '#16a34a', fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <CheckCircle2 size={14} /> Saved successfully!
                </span>
              )}
            </div>
          </form>
        </div>
      )}

      {/* TAB 2: PRODUCTION TELEMETRY & METRICS (Phase 50) */}
      {activeTab === 'analytics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Top KPI Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
            <div className="card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>JOBS INGESTED</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#0f172a', marginTop: '0.25rem' }}>
                {metrics?.total_jobs || 0}
              </div>
            </div>
            <div className="card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>APPLICATIONS CREATED</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#6366f1', marginTop: '0.25rem' }}>
                {metrics?.total_applications || 0}
              </div>
            </div>
            <div className="card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>SUBMITTED</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#059669', marginTop: '0.25rem' }}>
                {metrics?.submitted_count || 0}
              </div>
            </div>
            <div className="card" style={{ padding: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>ACTIVE INTERVIEWS</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#2563eb', marginTop: '0.25rem' }}>
                {metrics?.interview_count || 0}
              </div>
            </div>
            <div className="card" style={{ padding: '1.25rem', background: '#f0fdf4' }}>
              <div style={{ fontSize: '0.8rem', color: '#047857', fontWeight: 600 }}>OFFERS RECEIVED</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#047857', marginTop: '0.25rem' }}>
                {metrics?.offer_count || 0}
              </div>
            </div>
          </div>

          {/* Conversion Ratios & Average Match Score */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div className="card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1.05rem', margin: '0 0 1rem 0' }}>Conversion Analytics</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                    <span>Interview Conversion Rate</span>
                    <strong>{metrics?.interview_conversion_rate || 0}%</strong>
                  </div>
                  <div style={{ height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, metrics?.interview_conversion_rate || 0)}%`, height: '100%', background: '#3b82f6' }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                    <span>Offer Conversion Rate</span>
                    <strong>{metrics?.offer_conversion_rate || 0}%</strong>
                  </div>
                  <div style={{ height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, metrics?.offer_conversion_rate || 0)}%`, height: '100%', background: '#10b981' }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                    <span>Average AI Match Score</span>
                    <strong>{metrics?.average_match_score || 0}%</strong>
                  </div>
                  <div style={{ height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, metrics?.average_match_score || 0)}%`, height: '100%', background: '#8b5cf6' }} />
                  </div>
                </div>
              </div>
            </div>

            {/* ATS Source Distribution */}
            <div className="card" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '1.05rem', margin: '0 0 1rem 0' }}>ATS Sources Distribution</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {metrics?.source_distribution && Object.entries(metrics.source_distribution).map(([src, cnt]) => (
                  <div key={src} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ textTransform: 'capitalize', fontWeight: 500, fontSize: '0.9rem' }}>{src}</span>
                    <span className="badge badge-primary">{cnt} jobs</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
