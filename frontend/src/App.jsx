import React, { useState } from 'react';
import Navbar from './components/Navbar';
import ProfilePage from './pages/ProfilePage';
import JobListPage from './pages/JobListPage';
import JobDetailPage from './pages/JobDetailPage';

export default function App() {
  const [activeTab, setActiveTab] = useState('jobs'); // 'profile', 'jobs', 'detail'
  const [selectedJobId, setSelectedJobId] = useState(null);

  const handleSelectJob = (jobId) => {
    setSelectedJobId(jobId);
    setActiveTab('detail');
  };

  const handleBackToList = () => {
    setActiveTab('jobs');
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
          <JobDetailPage jobId={selectedJobId} onBack={handleBackToList} />
        )}
      </main>
    </div>
  );
}
