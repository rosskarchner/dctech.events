import React from 'react';
import { Link } from 'react-router-dom';

function Home({ user }) {
  return (
    <div>
      <div className="card">
        <h2>Welcome to Organize DC Tech Events</h2>
        <p>
          Create and manage tech events and groups in the DC area. Connect with other
          organizers, build communities, and grow the tech scene.
        </p>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Create a Group</h3>
          <p>Start a new community around a tech topic, meetup, or organization.</p>
          <Link to="/create-group" className="btn btn-primary">
            Create Group
          </Link>
        </div>

        <div className="card">
          <h3>Create an Event</h3>
          <p>Organize a one-time event or add an event to one of your groups.</p>
          <Link to="/create-event" className="btn btn-primary">
            Create Event
          </Link>
        </div>

        <div className="card">
          <h3>Browse Groups</h3>
          <p>Discover and join existing tech groups in the DC area.</p>
          <Link to="/groups" className="btn btn-primary">
            Browse Groups
          </Link>
        </div>

        <div className="card">
          <h3>Browse Events</h3>
          <p>Find upcoming tech events happening around DC.</p>
          <Link to="/events" className="btn btn-primary">
            Browse Events
          </Link>
        </div>
      </div>

      <div className="card">
        <h3>About</h3>
        <p>
          Events and groups created here will automatically appear on the main{' '}
          <a href="https://dctech.events" target="_blank" rel="noopener noreferrer">
            dctech.events
          </a>{' '}
          calendar. This platform allows community members to organize and manage
          their own events and groups independently.
        </p>
      </div>
    </div>
  );
}

export default Home;
