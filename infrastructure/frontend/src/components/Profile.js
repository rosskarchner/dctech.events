import React, { useState, useEffect } from 'react';
import { userApi } from '../api';

function Profile({ user }) {
  const [profile, setProfile] = useState({
    fullname: '',
    bio: '',
    website: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await userApi.getProfile();
      setProfile({
        fullname: data.fullname || '',
        bio: data.bio || '',
        website: data.website || '',
      });
    } catch (err) {
      // User might not have a profile yet, that's okay
      console.log('No profile found, using defaults');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setProfile({
      ...profile,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      await userApi.updateProfile(profile);
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  return (
    <div>
      <div className="card">
        <h2>My Profile</h2>
        <p>Manage your profile information</p>

        <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '4px' }}>
          <strong>Email:</strong> {user?.signInDetails?.loginId || 'N/A'}
        </div>

        {error && <div className="message error">{error}</div>}
        {success && <div className="message success">Profile updated successfully!</div>}

        <form onSubmit={handleSubmit} style={{ marginTop: '20px' }}>
          <div className="form-group">
            <label htmlFor="fullname">Full Name</label>
            <input
              type="text"
              id="fullname"
              name="fullname"
              value={profile.fullname}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="bio">Bio</label>
            <textarea
              id="bio"
              name="bio"
              value={profile.bio}
              onChange={handleChange}
              placeholder="Tell people a bit about yourself..."
              maxLength={500}
            />
            <small style={{ color: '#7f8c8d' }}>
              {profile.bio.length}/500 characters
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="website">Website</label>
            <input
              type="url"
              id="website"
              name="website"
              value={profile.website}
              onChange={handleChange}
              placeholder="https://example.com"
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Profile;
