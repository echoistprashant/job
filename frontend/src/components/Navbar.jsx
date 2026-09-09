import React, { useEffect, useState } from 'react';
import { Briefcase, User, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

export default function Navbar({ activeTab, setActiveTab, selectedJobId }) {
  const [isBackendOnline, setIsBackendOnline] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        await api.checkHealth();
        setIsBackendOnline(true);
      } catch {
        setIsBackendOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <a href="#home" className="brand" onClick={(e) => { e.preventDefault(); setActiveTab('jobs'); }}>
          <Briefcase size={24} />
          <span>AI Job Agent</span>
        </a>

        <nav className="nav-links">
          <button
            className={`nav-button ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            <User size={18} />
            Profile & Resume
          </button>

          <button
            className={`nav-button ${activeTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setActiveTab('jobs')}
          >
            <Briefcase size={18} />
            Job Board
          </button>

          <button
            className={`nav-button ${activeTab === 'applications' || activeTab === 'review' ? 'active' : ''}`}
            onClick={() => setActiveTab('applications')}
          >
            <CheckCircle2 size={18} />
            Applications
          </button>

          {selectedJobId && (
            <button
              className={`nav-button ${activeTab === 'detail' ? 'active' : ''}`}
              onClick={() => setActiveTab('detail')}
            >
              <FileText size={18} />
              Job Details
            </button>
          )}
        </nav>

        <div className="status-container">
          {isBackendOnline ? (
            <span className="status-badge status-online">
              <CheckCircle2 size={14} /> Backend Online
            </span>
          ) : (
            <span className="status-badge status-offline">
              <AlertCircle size={14} /> Backend Offline
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
