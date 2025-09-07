import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // If unauthorized and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(
            `${api.defaults.baseURL}/auth/refresh`,
            { refresh_token: refreshToken }
          );

          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (code) => api.post('/auth/login', { code }),
  refresh: (refreshToken) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  logout: () => api.post('/auth/logout'),
  getUser: () => api.get('/auth/user'),
};

// Embed API
export const embedAPI = {
  // Template management
  getTemplates: (params) => api.get('/embeds/templates', { params }),
  getTemplate: (id) => api.get(`/embeds/templates/${id}`),
  createTemplate: (data) => api.post('/embeds/templates', data),
  updateTemplate: (id, data) => api.put(`/embeds/templates/${id}`, data),
  deleteTemplate: (id) => api.delete(`/embeds/templates/${id}`),
  validateTemplate: (name, data) => api.post(`/embeds/templates/${name}/validate`, { embed_json: data }),

  // Posted messages
  getPostedMessages: (params) => api.get('/embeds/posted-messages', { params }),

  // Preview
  previewEmbed: (data) => api.post('/embeds/preview', { embed_json: data }),
};

// Stats API
export const statsAPI = {
  getServerStats: (guildId, timePeriod) => api.get('/stats/server', {
    params: { guild_id: guildId, time_period: timePeriod }
  }),
  getUserStats: (userId, timePeriod) => api.get('/stats/user', {
    params: { user_id: userId, time_period: timePeriod }
  }),
  getMessageStats: (params) => api.get('/stats/messages', { params }),
  getVoiceStats: (params) => api.get('/stats/voice', { params }),
  getInviteStats: (params) => api.get('/stats/invites', { params }),
};

// Giveaway API
export const giveawayAPI = {
  getGiveaways: (params) => api.get('/giveaways', { params }),
  getGiveaway: (id) => api.get(`/giveaways/${id}`),
  createGiveaway: (data) => api.post('/giveaways', data),
  updateGiveaway: (id, data) => api.put(`/giveaways/${id}`, data),
  deleteGiveaway: (id) => api.delete(`/giveaways/${id}`),
  getEntries: (id) => api.get(`/giveaways/${id}/entries`),
  endGiveaway: (id) => api.post(`/giveaways/${id}/end`),
};

// Media API
export const mediaAPI = {
  searchMovies: (query, limit) => api.get('/media/search/movies', {
    params: { q: query, limit }
  }),
  searchTV: (query, limit) => api.get('/media/search/tv', {
    params: { q: query, limit }
  }),
  searchAnime: (query, limit) => api.get('/media/search/anime', {
    params: { q: query, limit }
  }),
  getWatchParties: (params) => api.get('/media/watchparties', { params }),
  createWatchParty: (data) => api.post('/media/watchparties', data),
  getTrackedShows: () => api.get('/media/tracked'),
  trackShow: (data) => api.post('/media/track', data),
  untrackShow: (id) => api.delete(`/media/track/${id}`),
};

// LLM API
export const llmAPI = {
  chat: (data) => api.post('/llm/chat', data),
  getHistory: (userId, params) => api.get(`/llm/history/${userId}`, { params }),
  clearHistory: (userId) => api.delete(`/llm/history/${userId}`),
};

// User API
export const userAPI = {
  getProfile: () => api.get('/users/profile'),
  updateProfile: (data) => api.put('/users/profile', data),
  getPermissions: () => api.get('/users/permissions'),
};

// Utility functions
export const handleAPIError = (error) => {
  if (error.response) {
    // Server responded with error status
    const { status, data } = error.response;

    switch (status) {
      case 400:
        return data.message || 'Bad request';
      case 401:
        return 'Unauthorized - please login again';
      case 403:
        return 'Forbidden - insufficient permissions';
      case 404:
        return 'Resource not found';
      case 409:
        return 'Conflict - resource already exists';
      case 422:
        return 'Validation error';
      case 429:
        return 'Too many requests - please try again later';
      case 500:
        return 'Internal server error';
      default:
        return data.message || `Server error: ${status}`;
    }
  } else if (error.request) {
    // Network error
    return 'Network error - please check your connection';
  } else {
    // Other error
    return error.message || 'An unexpected error occurred';
  }
};

export default api;