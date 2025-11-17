import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import config from './config';

// Import components
import Home from './components/Home';
import Groups from './components/Groups';
import GroupDetail from './components/GroupDetail';
import Events from './components/Events';
import EventDetail from './components/EventDetail';
import CreateGroup from './components/CreateGroup';
import CreateEvent from './components/CreateEvent';
import Profile from './components/Profile';

// Configure Amplify
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: config.userPoolId,
      userPoolClientId: config.userPoolClientId,
      loginWith: {
        oauth: {
          domain: `${config.userPoolDomain}.auth.${config.region}.amazoncognito.com`,
          scopes: ['email', 'openid', 'profile'],
          redirectSignIn: [window.location.origin + '/callback'],
          redirectSignOut: [window.location.origin],
          responseType: 'code',
        },
        email: true,
        username: true,
      },
    },
  },
  API: {
    REST: {
      organizeApi: {
        endpoint: config.apiUrl,
        region: config.region,
      },
    },
  },
});

function AppContent({ signOut, user }) {
  return (
    <Router>
      <div className="app">
        <header>
          <div className="container">
            <h1>Organize DC Tech Events</h1>
            <nav>
              <Link to="/">Home</Link>
              <Link to="/groups">Groups</Link>
              <Link to="/events">Events</Link>
              <Link to="/create-group">Create Group</Link>
              <Link to="/create-event">Create Event</Link>
              <Link to="/profile">Profile</Link>
              <button onClick={signOut} className="btn btn-secondary">
                Sign Out
              </button>
            </nav>
          </div>
        </header>

        <main className="container">
          <Routes>
            <Route path="/" element={<Home user={user} />} />
            <Route path="/groups" element={<Groups user={user} />} />
            <Route path="/groups/:groupId" element={<GroupDetail user={user} />} />
            <Route path="/events" element={<Events user={user} />} />
            <Route path="/events/:eventId" element={<EventDetail user={user} />} />
            <Route path="/create-group" element={<CreateGroup user={user} />} />
            <Route path="/create-event" element={<CreateEvent user={user} />} />
            <Route path="/profile" element={<Profile user={user} />} />
            <Route path="/callback" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

function App() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <AppContent signOut={signOut} user={user} />
      )}
    </Authenticator>
  );
}

export default App;
