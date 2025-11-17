import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { groupsApi } from '../api';
import { fetchAuthSession } from 'aws-amplify/auth';

function GroupDetail() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const [group, setGroup] = useState(null);
  const [members, setMembers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [userMembership, setUserMembership] = useState(null);

  useEffect(() => {
    loadData();
  }, [groupId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const session = await fetchAuthSession();
      const userId = session.tokens?.idToken?.payload?.sub;
      setCurrentUserId(userId);

      const [groupData, membersData] = await Promise.all([
        groupsApi.get(groupId),
        groupsApi.listMembers(groupId),
      ]);

      setGroup(groupData);
      setMembers(membersData.members || []);

      const membership = membersData.members?.find((m) => m.userId === userId);
      setUserMembership(membership);

      if (membership) {
        const messagesData = await groupsApi.listMessages(groupId);
        setMessages(messagesData.messages || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    try {
      await groupsApi.join(groupId);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleLeave = async () => {
    try {
      await groupsApi.removeMember(groupId, currentUserId);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handlePostMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    try {
      await groupsApi.postMessage(groupId, newMessage);
      setNewMessage('');
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUpdateRole = async (userId, newRole) => {
    try {
      await groupsApi.updateMemberRole(groupId, userId, newRole);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRemoveMember = async (userId) => {
    try {
      await groupsApi.removeMember(groupId, userId);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return <div className="loading">Loading group...</div>;
  }

  if (error) {
    return <div className="message error">Error: {error}</div>;
  }

  if (!group) {
    return <div className="message error">Group not found</div>;
  }

  const isOwner = userMembership?.role === 'owner';
  const isManager = userMembership?.role === 'manager' || isOwner;
  const isMember = !!userMembership;

  return (
    <div>
      <div className="card">
        <h2>{group.name}</h2>
        {group.description && <p>{group.description}</p>}
        {group.website && (
          <p>
            <a href={group.website} target="_blank" rel="noopener noreferrer">
              {group.website}
            </a>
          </p>
        )}

        <div style={{ marginTop: '20px' }}>
          {!isMember ? (
            <button onClick={handleJoin} className="btn btn-primary">
              Join Group
            </button>
          ) : (
            <button onClick={handleLeave} className="btn btn-secondary">
              Leave Group
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Members ({members.length})</h3>
        <div>
          {members.map((member) => (
            <div
              key={member.userId}
              style={{
                padding: '10px',
                borderBottom: '1px solid #eee',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <strong>{member.userId}</strong>
                <span style={{ marginLeft: '10px', color: '#7f8c8d' }}>
                  ({member.role})
                </span>
              </div>
              {isOwner && member.userId !== currentUserId && (
                <div>
                  <select
                    value={member.role}
                    onChange={(e) => handleUpdateRole(member.userId, e.target.value)}
                    style={{ marginRight: '10px' }}
                  >
                    <option value="member">Member</option>
                    <option value="manager">Manager</option>
                    <option value="owner">Owner</option>
                  </select>
                  <button
                    onClick={() => handleRemoveMember(member.userId)}
                    className="btn btn-danger"
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {isMember && (
        <div className="card">
          <h3>Messages</h3>
          <div style={{ marginBottom: '20px' }}>
            {messages.length === 0 ? (
              <p>No messages yet. Start the conversation!</p>
            ) : (
              messages.map((message, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '10px',
                    borderBottom: '1px solid #eee',
                    marginBottom: '10px',
                  }}
                >
                  <div style={{ color: '#7f8c8d', fontSize: '12px' }}>
                    {message.userId} • {new Date(message.timestamp).toLocaleString()}
                  </div>
                  <div style={{ marginTop: '5px' }}>{message.content}</div>
                </div>
              ))
            )}
          </div>

          <form onSubmit={handlePostMessage}>
            <div className="form-group">
              <textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Write a message..."
                required
              />
            </div>
            <button type="submit" className="btn btn-primary">
              Post Message
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

export default GroupDetail;
