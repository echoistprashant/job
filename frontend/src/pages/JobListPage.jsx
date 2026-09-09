import React, { useState, useEffect } from 'react';
import { Search, RefreshCw, Filter, ArrowUpDown, ExternalLink, Sparkles, MapPin, Building } from 'lucide-react';
import { api } from '../services/api';

export default function JobListPage({ onSelectJob }) {
  const [jobs, setJobs] = useState([]);
  const [matches, setMatches] = useState({});
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [matchingAll, setMatchingAll] = useState(false);

  // Filters & Sorting
  const [keyword, setKeyword] = useState('');
  const [location, setLocation] = useState('');
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('match_desc'); // match_desc, date_desc, date_asc

  const loadJobs = async () => {
    try {
      setLoading(true);
      const params = {
        keyword: keyword || undefined,
        location: location || undefined,
        remote_only: remoteOnly ? true : undefined,
        source: source || undefined,
        limit: 100,
      };
      const data = await api.getJobs(params);
      setJobs(data.items || []);

      // Pre-fetch existing matches for displayed jobs
      const matchMap = {};
      await Promise.all(
        (data.items || []).slice(0, 15).map(async (j) => {
          try {
            const m = await api.getJobMatch(j.id);
            if (m) matchMap[j.id] = m.score;
          } catch {
            // Not computed yet
          }
        })
      );
      setMatches((prev) => ({ ...prev, ...matchMap }));
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, [remoteOnly, source]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadJobs();
  };

  const handleCollectNewJobs = async () => {
    try {
      setCollecting(true);
      await api.searchJobs(['AI Engineer', 'Backend', 'Machine Learning'], ['Remote', 'India']);
      await loadJobs();
    } catch (err) {
      alert(`Error collecting jobs: ${err.message}`);
    } finally {
      setCollecting(false);
    }
  };

  const handleMatchAll = async () => {
    try {
      setMatchingAll(true);
      const updated = { ...matches };
      for (const j of jobs) {
        try {
          const res = await api.matchJob(j.id);
          updated[j.id] = res.score;
        } catch (e) {
          console.error(e);
        }
      }
      setMatches(updated);
    } finally {
      setMatchingAll(false);
    }
  };

  // Sorting
  const sortedJobs = [...jobs].sort((a, b) => {
    const scoreA = matches[a.id] ?? -1;
    const scoreB = matches[b.id] ?? -1;

    if (sortBy === 'match_desc') return scoreB - scoreA;
    if (sortBy === 'match_asc') return scoreA - scoreB;
    if (sortBy === 'date_desc') return new Date(b.created_at) - new Date(a.created_at);
    return new Date(a.created_at) - new Date(b.created_at);
  });

  const getScoreBadgeClass = (score) => {
    if (score >= 75) return 'badge-score-high';
    if (score >= 50) return 'badge-score-med';
    return 'badge-score-low';
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Job Discovery & Ranking</h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Aggregated job listings scored and ranked using our 6-dimension AI matching model.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={handleCollectNewJobs} disabled={collecting}>
            <RefreshCw size={16} className={collecting ? 'spin' : ''} />
            {collecting ? 'Collecting from Sources...' : 'Discover New Jobs'}
          </button>

          <button className="btn btn-primary" onClick={handleMatchAll} disabled={matchingAll}>
            <Sparkles size={16} />
            {matchingAll ? 'Scoring...' : 'Score All Jobs'}
          </button>
        </div>
      </div>

      {/* Filter & Search Bar (Phase 20) */}
      <div className="card" style={{ padding: '1rem 1.25rem' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: '1 1 200px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search keyword or title..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>

          <div style={{ flex: '1 1 150px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Filter location..."
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>

          <div style={{ width: '130px' }}>
            <select className="form-select" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All Sources</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="manual">Manual</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <input
              type="checkbox"
              id="remoteFilter"
              checked={remoteOnly}
              onChange={(e) => setRemoteOnly(e.target.checked)}
            />
            <label htmlFor="remoteFilter" style={{ fontSize: '0.85rem', cursor: 'pointer' }}>
              Remote Only
            </label>
          </div>

          <button type="submit" className="btn btn-secondary btn-sm">
            <Search size={14} /> Filter
          </button>

          {/* Sort By Dropdown */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <ArrowUpDown size={14} color="var(--text-muted)" />
            <select
              className="form-select"
              style={{ width: 'auto', padding: '0.35rem 0.65rem' }}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="match_desc">Sort: Highest Match Score</option>
              <option value="match_asc">Sort: Lowest Match Score</option>
              <option value="date_desc">Sort: Newest First</option>
            </select>
          </div>
        </form>
      </div>

      {/* Jobs List / Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Loading jobs...
        </div>
      ) : sortedJobs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <h3>No jobs found matching your criteria.</h3>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem', marginBottom: '1.5rem' }}>
            Click "Discover New Jobs" to run the source connectors or adjust your filters.
          </p>
          <button className="btn btn-primary" onClick={handleCollectNewJobs} disabled={collecting}>
            Discover New Jobs
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {sortedJobs.map((job) => {
            const score = matches[job.id];
            return (
              <div
                key={job.id}
                className="card"
                style={{
                  margin: 0,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  transition: 'transform 0.15s, box-shadow 0.15s',
                }}
                onClick={() => onSelectJob(job.id)}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.35rem' }}>
                    <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text-main)' }}>
                      {job.title}
                    </h3>
                    <span className="pill" style={{ textTransform: 'capitalize' }}>
                      {job.source}
                    </span>
                    {job.remote && (
                      <span className="pill pill-primary">Remote</span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Building size={14} /> {job.company}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <MapPin size={14} /> {job.location || 'Remote'}
                    </span>
                    <span>Exp: {job.experience || 'Not specified'}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                      AI Match Score
                    </div>
                    {score !== undefined ? (
                      <span className={`badge ${getScoreBadgeClass(score)}`} style={{ fontSize: '0.95rem', padding: '0.3rem 0.65rem' }}>
                        {score}%
                      </span>
                    ) : (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          api.matchJob(job.id).then((res) => {
                            setMatches((prev) => ({ ...prev, [job.id]: res.score }));
                          });
                        }}
                      >
                        Calculate Score
                      </button>
                    )}
                  </div>

                  <button className="btn btn-secondary btn-sm">
                    View & Apply
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
