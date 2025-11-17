import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { eventsApi, groupsApi } from '../api';
import { fetchAuthSession } from 'aws-amplify/auth';

function CreateEvent() {
  const navigate = useNavigate();
  const [myGroups, setMyGroups] = useState([]);
  const [formData, setFormData] = useState({
    title: '',
    date: '',
    time: '',
    location: '',
    url: '',
    description: '',
    groupId: '',
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadMyGroups();
  }, []);

  const loadMyGroups = async () => {
    try {
      const session = await fetchAuthSession();
      const userId = session.tokens?.idToken?.payload?.sub;

      const allGroups = await groupsApi.list();
      const groups = allGroups.groups || [];

      // Filter groups where user is a manager or owner
      const myGroupsList = [];
      for (const group of groups) {
        const members = await groupsApi.listMembers(group.groupId);
        const membership = members.members?.find((m) => m.userId === userId);

        if (membership && (membership.role === 'manager' || membership.role === 'owner')) {
          myGroupsList.push(group);
        }
      }

      setMyGroups(myGroupsList);
    } catch (err) {
      console.error('Error loading groups:', err);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await eventsApi.create(formData);
      navigate(`/events/${result.eventId}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h2>Create a New Event</h2>
        {error && <div className="message error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="title">Event Title *</label>
            <input
              type="text"
              id="title"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="date">Date *</label>
            <input
              type="date"
              id="date"
              name="date"
              value={formData.date}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="time">Time</label>
            <input
              type="time"
              id="time"
              name="time"
              value={formData.time}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="location">Location</label>
            <input
              type="text"
              id="location"
              name="location"
              value={formData.location}
              onChange={handleChange}
              placeholder="Address or venue name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="url">Event URL</label>
            <input
              type="url"
              id="url"
              name="url"
              value={formData.url}
              onChange={handleChange}
              placeholder="https://example.com"
            />
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Tell people about your event..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="groupId">Group (optional)</label>
            <select
              id="groupId"
              name="groupId"
              value={formData.groupId}
              onChange={handleChange}
            >
              <option value="">None (standalone event)</option>
              {myGroups.map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.name}
                </option>
              ))}
            </select>
            <small style={{ color: '#7f8c8d' }}>
              You can only add events to groups where you are a manager or owner
            </small>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create Event'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default CreateEvent;
