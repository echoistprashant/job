import React, { useState } from 'react';
import Navbar from './components/Navbar';
import ProfilePage from './pages/ProfilePage';
import JobListPage from './pages/JobListPage';
import JobDetailPage from './pages/JobDetailPage';
import ApplicationListPage from './pages/ApplicationListPage';
import ApplicationReviewPage from './pages/ApplicationReviewPage';
import AutoApplyPage from './pages/AutoApplyPage';

export default function App() {
  const [activeTab, setActiveTab] = useState('jobs'); // 'profile', 'jobs', 'detail', 'applications', 'review', 'auto-apply'
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedAppId, setSelectedAppId] = useState(null);

  const handleSelectJob = (jobId) => {
    setSelectedJobId(jobId);
    setActiveTab('detail');
  };

  const handleBackToList = () => {
    setActiveTab('jobs');
  };

  const handleSelectApplication = (appId) => {
    setSelectedAppId(appId);
    setActiveTab('review');
  };

  const handleBackToApplications = () => {
    setActiveTab('applications');
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedJobId={selectedJobId}
      />

      <main className="main-content">
        {activeTab === 'profile' && <ProfilePage />}
        {activeTab === 'jobs' && <JobListPage onSelectJob={handleSelectJob} />}
        {activeTab === 'detail' && selectedJobId && (
          <JobDetailPage
            jobId={selectedJobId}
            onBack={handleBackToList}
            onReviewApplication={handleSelectApplication}
          />
        )}
        {activeTab === 'applications' && (
          <ApplicationListPage onSelectApplication={handleSelectApplication} />
        )}
        {activeTab === 'review' && selectedAppId && (
          <ApplicationReviewPage
            applicationId={selectedAppId}
            onBack={handleBackToApplications}
          />
        )}
        {activeTab === 'auto-apply' && <AutoApplyPage />}
      </main>
    </div>
  );
}
