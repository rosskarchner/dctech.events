import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { eventsApi } from '../api';

function Events() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await eventsApi.list();
      setEvents(data.events || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading events...</div>;
  }

  if (error) {
    return <div className="message error">Error: {error}</div>;
  }

  const now = new Date();
  const upcomingEvents = events.filter((e) => new Date(e.eventDate) >= now);
  const sortedEvents = upcomingEvents.sort(
    (a, b) => new Date(a.eventDate) - new Date(b.eventDate)
  );

  return (
    <div>
      <div className="card">
        <h2>Upcoming Events</h2>
        <p>Browse upcoming tech events in the DC area.</p>
      </div>

      {sortedEvents.length === 0 ? (
        <div className="card">
          <p>No upcoming events. <Link to="/create-event">Create the first one!</Link></p>
        </div>
      ) : (
        <div className="grid">
          {sortedEvents.map((event) => (
            <div key={event.eventId} className="event-card">
              <h3>{event.title}</h3>
              <div className="event-date">
                {new Date(event.eventDate).toLocaleDateString()}
                {event.time && ` at ${event.time}`}
              </div>
              {event.location && (
                <div className="event-location">{event.location}</div>
              )}
              {event.description && (
                <p style={{ marginTop: '10px' }}>{event.description}</p>
              )}
              <div style={{ marginTop: '15px' }}>
                <Link to={`/events/${event.eventId}`} className="btn btn-primary">
                  View Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Events;
