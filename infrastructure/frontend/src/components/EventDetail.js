import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { eventsApi } from '../api';
import { fetchAuthSession } from 'aws-amplify/auth';

function EventDetail() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [rsvps, setRsvps] = useState([]);
  const [userRsvp, setUserRsvp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [showConvertModal, setShowConvertModal] = useState(false);
  const [groupName, setGroupName] = useState('');

  useEffect(() => {
    loadData();
  }, [eventId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const session = await fetchAuthSession();
      const userId = session.tokens?.idToken?.payload?.sub;
      setCurrentUserId(userId);

      const [eventData, rsvpsData] = await Promise.all([
        eventsApi.get(eventId),
        eventsApi.listRSVPs(eventId),
      ]);

      setEvent(eventData);
      setRsvps(rsvpsData.rsvps || []);

      const userRsvpData = rsvpsData.rsvps?.find((r) => r.userId === userId);
      setUserRsvp(userRsvpData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRSVP = async (status) => {
    try {
      await eventsApi.rsvp(eventId, status);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteRSVP = async () => {
    try {
      await eventsApi.deleteRSVP(eventId);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this event?')) {
      return;
    }

    try {
      await eventsApi.delete(eventId);
      navigate('/events');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleConvertToGroup = async () => {
    if (!groupName.trim()) {
      setError('Please enter a group name');
      return;
    }

    try {
      const result = await eventsApi.convertToGroup(eventId, groupName);
      navigate(`/groups/${result.groupId}`);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return <div className="loading">Loading event...</div>;
  }

  if (error) {
    return <div className="message error">Error: {error}</div>;
  }

  if (!event) {
    return <div className="message error">Event not found</div>;
  }

  const isCreator = event.createdBy === currentUserId;
  const goingCount = rsvps.filter((r) => r.status === 'going').length;

  return (
    <div>
      <div className="card">
        <h2>{event.title}</h2>

        <div className="event-date" style={{ fontSize: '18px', marginBottom: '10px' }}>
          {new Date(event.eventDate).toLocaleDateString()}
          {event.time && ` at ${event.time}`}
        </div>

        {event.location && (
          <div style={{ marginBottom: '10px' }}>
            <strong>Location:</strong> {event.location}
          </div>
        )}

        {event.url && (
          <div style={{ marginBottom: '10px' }}>
            <a href={event.url} target="_blank" rel="noopener noreferrer">
              Event Link
            </a>
          </div>
        )}

        {event.description && (
          <div style={{ marginTop: '15px' }}>
            <p>{event.description}</p>
          </div>
        )}

        {event.groupId && (
          <div style={{ marginTop: '15px' }}>
            <Link to={`/groups/${event.groupId}`} className="btn btn-secondary">
              View Group
            </Link>
          </div>
        )}

        <div style={{ marginTop: '20px' }}>
          {!userRsvp ? (
            <div>
              <button onClick={() => handleRSVP('going')} className="btn btn-primary" style={{ marginRight: '10px' }}>
                RSVP: Going
              </button>
              <button onClick={() => handleRSVP('maybe')} className="btn btn-secondary" style={{ marginRight: '10px' }}>
                RSVP: Maybe
              </button>
              <button onClick={() => handleRSVP('not-going')} className="btn btn-secondary">
                RSVP: Not Going
              </button>
            </div>
          ) : (
            <div>
              <p>Your RSVP: <strong>{userRsvp.status}</strong></p>
              <button onClick={handleDeleteRSVP} className="btn btn-secondary">
                Cancel RSVP
              </button>
            </div>
          )}
        </div>

        {isCreator && (
          <div style={{ marginTop: '20px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
            <h3>Event Management</h3>
            <button onClick={() => setShowConvertModal(true)} className="btn btn-primary" style={{ marginRight: '10px' }}>
              Convert RSVPs to Group
            </button>
            <button onClick={handleDelete} className="btn btn-danger">
              Delete Event
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h3>RSVPs ({goingCount} going)</h3>
        {rsvps.length === 0 ? (
          <p>No RSVPs yet. Be the first!</p>
        ) : (
          <div>
            {['going', 'maybe', 'not-going'].map((status) => {
              const statusRsvps = rsvps.filter((r) => r.status === status);
              if (statusRsvps.length === 0) return null;

              return (
                <div key={status} style={{ marginBottom: '15px' }}>
                  <h4 style={{ textTransform: 'capitalize', color: '#7f8c8d' }}>
                    {status} ({statusRsvps.length})
                  </h4>
                  {statusRsvps.map((rsvp) => (
                    <div key={rsvp.userId} style={{ padding: '5px 0' }}>
                      {rsvp.userId}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showConvertModal && (
        <div className="modal-overlay" onClick={() => setShowConvertModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Convert RSVPs to Group</h2>
            <p>
              This will create a new group and add all attendees as members.
              You will be the owner of the group.
            </p>

            <div className="form-group">
              <label htmlFor="groupName">Group Name *</label>
              <input
                type="text"
                id="groupName"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="Enter group name"
              />
            </div>

            <div className="modal-actions">
              <button onClick={() => setShowConvertModal(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button onClick={handleConvertToGroup} className="btn btn-primary">
                Create Group
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EventDetail;
