import { fetchAuthSession } from 'aws-amplify/auth';
import config from './config';

async function getAuthToken() {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString();
  } catch (error) {
    console.error('Error getting auth token:', error);
    return null;
  }
}

async function apiRequest(endpoint, options = {}) {
  const token = await getAuthToken();

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${config.apiUrl}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Request failed');
  }

  return response.json();
}

// User API
export const userApi = {
  getProfile: () => apiRequest('/users'),
  updateProfile: (data) => apiRequest('/users', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  getUser: (userId) => apiRequest(`/users/${userId}`),
};

// Groups API
export const groupsApi = {
  list: () => apiRequest('/groups'),
  get: (groupId) => apiRequest(`/groups/${groupId}`),
  create: (data) => apiRequest('/groups', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  update: (groupId, data) => apiRequest(`/groups/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  delete: (groupId) => apiRequest(`/groups/${groupId}`, {
    method: 'DELETE',
  }),

  // Members
  listMembers: (groupId) => apiRequest(`/groups/${groupId}/members`),
  join: (groupId) => apiRequest(`/groups/${groupId}/members`, {
    method: 'POST',
  }),
  updateMemberRole: (groupId, userId, role) => apiRequest(`/groups/${groupId}/members/${userId}`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  }),
  removeMember: (groupId, userId) => apiRequest(`/groups/${groupId}/members/${userId}`, {
    method: 'DELETE',
  }),

  // Messages
  listMessages: (groupId) => apiRequest(`/groups/${groupId}/messages`),
  postMessage: (groupId, content) => apiRequest(`/groups/${groupId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  }),
};

// Events API
export const eventsApi = {
  list: () => apiRequest('/events'),
  get: (eventId) => apiRequest(`/events/${eventId}`),
  create: (data) => apiRequest('/events', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  update: (eventId, data) => apiRequest(`/events/${eventId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  delete: (eventId) => apiRequest(`/events/${eventId}`, {
    method: 'DELETE',
  }),

  // RSVPs
  listRSVPs: (eventId) => apiRequest(`/events/${eventId}/rsvps`),
  rsvp: (eventId, status) => apiRequest(`/events/${eventId}/rsvps`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  }),
  deleteRSVP: (eventId) => apiRequest(`/events/${eventId}/rsvps`, {
    method: 'DELETE',
  }),

  // Convert to group
  convertToGroup: (eventId, groupName) => apiRequest(`/events/${eventId}/convert-to-group`, {
    method: 'POST',
    body: JSON.stringify({ groupName }),
  }),
};
