const BASE_URL = 'http://127.0.0.1:8000';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = options.headers || {};
  
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = 'API request failed';
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = await res.text();
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  // System Health
  checkHealth: () => request('/health'),

  // Candidate Profile & Resume
  getProfile: () => request('/resume/profile'),
  updateProfile: (data) => request('/resume/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  uploadResume: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/resume/upload', {
      method: 'POST',
      body: formData,
    });
  },

  // Job Ingestion & Retrieval
  getJobs: (params = {}) => {
    const query = new URLSearchParams();
    if (params.keyword) query.append('keyword', params.keyword);
    if (params.location) query.append('location', params.location);
    if (params.remote_only !== undefined) query.append('remote_only', params.remote_only);
    if (params.source) query.append('source', params.source);
    if (params.limit) query.append('limit', params.limit);
    if (params.offset) query.append('offset', params.offset);

    const qs = query.toString();
    return request(`/jobs${qs ? '?' + qs : ''}`);
  },

  searchJobs: (keywords, locations) => request('/jobs/search', {
    method: 'POST',
    body: JSON.stringify({ keywords, locations, limit_per_source: 20 }),
  }),

  getJobDetails: (jobId) => request(`/jobs/${jobId}`),

  // Match Scoring
  matchJob: (jobId) => request(`/jobs/${jobId}/match`, {
    method: 'POST',
  }),
  getJobMatch: (jobId) => request(`/jobs/${jobId}/match`),

  // Application Workflow & Human-in-the-Loop
  listApplications: (status) => {
    const qs = status ? `?status=${status}` : '';
    return request(`/applications${qs}`);
  },
  getApplication: (id) => request(`/applications/${id}`),
  prepareApplication: (jobId) => request(`/applications/${jobId}/prepare`, {
    method: 'POST',
  }),
  extractQuestions: (id) => request(`/applications/${id}/extract-questions`, {
    method: 'POST',
  }),
  answerQuestions: (id) => request(`/applications/${id}/answer-questions`, {
    method: 'POST',
  }),
  tailorResume: (id) => request(`/applications/${id}/tailor-resume`, {
    method: 'POST',
  }),
  generateCoverLetter: (id, tone = 'professional') => request(`/applications/${id}/cover-letter`, {
    method: 'POST',
    body: JSON.stringify({ tone }),
  }),
  updateApplicationContent: (id, data) => request(`/applications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  approveApplication: (id) => request(`/applications/${id}/approve`, {
    method: 'POST',
  }),
  submitApplication: (id) => request(`/applications/${id}/submit`, {
    method: 'POST',
  }),
};
