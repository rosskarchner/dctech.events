import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { groupsApi } from '../api';

function Groups() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      setLoading(true);
      const data = await groupsApi.list();
      setGroups(data.groups || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading groups...</div>;
  }

  if (error) {
    return <div className="message error">Error: {error}</div>;
  }

  return (
    <div>
      <div className="card">
        <h2>DC Tech Groups</h2>
        <p>Browse and join tech groups in the DC area.</p>
      </div>

      {groups.length === 0 ? (
        <div className="card">
          <p>No groups found. <Link to="/create-group">Create the first one!</Link></p>
        </div>
      ) : (
        <div className="grid">
          {groups.map((group) => (
            <div key={group.groupId} className="group-card">
              <h3>{group.name}</h3>
              {group.description && <p>{group.description}</p>}
              {group.website && (
                <div className="group-website">
                  <a href={group.website} target="_blank" rel="noopener noreferrer">
                    Website
                  </a>
                </div>
              )}
              <div style={{ marginTop: '15px' }}>
                <Link to={`/groups/${group.groupId}`} className="btn btn-primary">
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

export default Groups;
