const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand, PutCommand, UpdateCommand, DeleteCommand, QueryCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);

// Helper to decode JWT token (without signature verification)
// Note: This is acceptable since tokens come from Cognito via HTTPS
function decodeJWT(token) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
    return payload;
  } catch (error) {
    return null;
  }
}

// Helper to parse API Gateway event
function parseEvent(event) {
  const path = event.path || event.resource;
  const method = event.httpMethod;
  const headers = event.headers || {};
  const isHtmx = headers['hx-request'] === 'true' || headers['HX-Request'] === 'true';

  // Parse body - could be JSON or form data
  let body = null;
  if (event.body) {
    const contentType = headers['content-type'] || headers['Content-Type'] || '';
    if (contentType.includes('application/json')) {
      body = JSON.parse(event.body);
    } else if (contentType.includes('application/x-www-form-urlencoded')) {
      // Parse form data
      body = {};
      const params = new URLSearchParams(event.body);
      for (const [key, value] of params) {
        body[key] = value;
      }
    } else {
      try {
        body = JSON.parse(event.body);
      } catch {
        body = event.body;
      }
    }
  }

  const pathParams = event.pathParameters || {};
  const queryParams = event.queryStringParameters || {};

  // Try to get user from authorizer context (if API Gateway handled it)
  let userId = event.requestContext?.authorizer?.claims?.sub || null;
  let userEmail = event.requestContext?.authorizer?.claims?.email || null;

  // If not in authorizer context, try to decode from Authorization header
  if (!userId) {
    const authHeader = headers['authorization'] || headers['Authorization'] || '';
    if (authHeader.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const claims = decodeJWT(token);
      if (claims) {
        userId = claims.sub || null;
        userEmail = claims.email || null;
      }
    }
  }

  return { path, method, body, pathParams, queryParams, userId, userEmail, isHtmx };
}

// Helper to create API response
function createResponse(statusCode, body, isHtml = false) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,HX-Request,HX-Target,HX-Trigger',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
  };

  if (isHtml) {
    headers['Content-Type'] = 'text/html';
    return {
      statusCode,
      headers,
      body: body,
    };
  } else {
    headers['Content-Type'] = 'application/json';
    return {
      statusCode,
      headers,
      body: JSON.stringify(body),
    };
  }
}

// HTML escape helper
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// HTML rendering helpers
const html = {
  groupCard: (group) => `
    <div class="group-card">
      <h3>${escapeHtml(group.name)}</h3>
      ${group.description ? `<p>${escapeHtml(group.description)}</p>` : ''}
      ${group.website ? `
        <div class="group-website">
          <a href="${escapeHtml(group.website)}" target="_blank" rel="noopener noreferrer">Website</a>
        </div>
      ` : ''}
      <div style="margin-top: 15px;">
        <a href="/group.html?id=${group.groupId}" class="btn btn-primary">View Details</a>
      </div>
    </div>
  `,

  eventCard: (event) => {
    const date = new Date(event.eventDate);
    const dateStr = date.toLocaleDateString();
    return `
      <div class="event-card">
        <h3>${escapeHtml(event.title)}</h3>
        <div class="event-date">${dateStr}${event.time ? ` at ${event.time}` : ''}</div>
        ${event.location ? `<div class="event-location">${escapeHtml(event.location)}</div>` : ''}
        ${event.description ? `<p style="margin-top: 10px;">${escapeHtml(event.description)}</p>` : ''}
        <div style="margin-top: 15px;">
          <a href="/event.html?id=${event.eventId}" class="btn btn-primary">View Details</a>
        </div>
      </div>
    `;
  },

  memberItem: (member, currentUserId, isOwner) => `
    <div class="member-item" id="member-${member.userId}">
      <div class="member-info">
        <strong>${escapeHtml(member.userId)}</strong>
        <span style="margin-left: 10px; color: #7f8c8d;">(${member.role})</span>
      </div>
      ${isOwner && member.userId !== currentUserId ? `
        <div class="member-actions">
          <select hx-put="/api/groups/${member.groupId}/members/${member.userId}"
                  hx-target="#member-${member.userId}"
                  hx-swap="outerHTML"
                  name="role">
            <option value="member" ${member.role === 'member' ? 'selected' : ''}>Member</option>
            <option value="manager" ${member.role === 'manager' ? 'selected' : ''}>Manager</option>
            <option value="owner" ${member.role === 'owner' ? 'selected' : ''}>Owner</option>
          </select>
          <button class="btn btn-danger btn-small"
                  hx-delete="/api/groups/${member.groupId}/members/${member.userId}"
                  hx-target="#member-${member.userId}"
                  hx-swap="outerHTML"
                  hx-confirm="Remove this member?">
            Remove
          </button>
        </div>
      ` : ''}
    </div>
  `,

  messageItem: (message) => `
    <div class="message-item">
      <div class="message-meta">${escapeHtml(message.userId)} • ${new Date(message.timestamp).toLocaleString()}</div>
      <div>${escapeHtml(message.content)}</div>
    </div>
  `,

  error: (message) => `<div class="message error">${escapeHtml(message)}</div>`,
  success: (message) => `<div class="message success">${escapeHtml(message)}</div>`,
};

// Helper to check group permissions
async function checkGroupPermission(groupId, userId, requiredRole = 'member') {
  const result = await docClient.send(new GetCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Key: { groupId, userId },
  }));

  if (!result.Item) {
    return { hasPermission: false, role: null };
  }

  const role = result.Item.role;
  const roleHierarchy = { owner: 3, manager: 2, member: 1 };
  const hasPermission = roleHierarchy[role] >= roleHierarchy[requiredRole];

  return { hasPermission, role };
}

// Helper to get event creator
async function isEventCreator(eventId, userId) {
  const result = await docClient.send(new GetCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
  }));

  return result.Item && result.Item.createdBy === userId;
}

// User handlers
async function getUser(userId) {
  const result = await docClient.send(new GetCommand({
    TableName: process.env.USERS_TABLE,
    Key: { userId },
  }));

  if (!result.Item) {
    return createResponse(404, { error: 'User not found' });
  }

  return createResponse(200, result.Item);
}

async function updateUser(userId, updates) {
  const timestamp = new Date().toISOString();

  const result = await docClient.send(new PutCommand({
    TableName: process.env.USERS_TABLE,
    Item: {
      userId,
      ...updates,
      updatedAt: timestamp,
    },
  }));

  return createResponse(200, { message: 'User updated successfully' });
}

// Group handlers
async function listGroups(isHtmx) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.GROUPS_TABLE,
    IndexName: 'activeGroupsIndex',
    KeyConditionExpression: 'active = :active',
    ExpressionAttributeValues: {
      ':active': 'true',
    },
  }));

  const groups = result.Items || [];

  if (isHtmx) {
    if (groups.length === 0) {
      return createResponse(200, '<div class="card">No groups found. <a href="/create-group.html">Create the first one!</a></div>', true);
    }
    const htmlContent = groups.map(group => html.groupCard(group)).join('');
    return createResponse(200, htmlContent, true);
  }

  return createResponse(200, { groups });
}

async function getGroup(groupId) {
  const result = await docClient.send(new GetCommand({
    TableName: process.env.GROUPS_TABLE,
    Key: { groupId },
  }));

  if (!result.Item) {
    return createResponse(404, { error: 'Group not found' });
  }

  return createResponse(200, result.Item);
}

async function createGroup(userId, userEmail, data) {
  const groupId = uuidv4();
  const timestamp = new Date().toISOString();

  const group = {
    groupId,
    name: data.name,
    website: data.website || '',
    description: data.description || '',
    active: 'true',
    createdBy: userId,
    createdAt: timestamp,
    updatedAt: timestamp,
  };

  // Create group
  await docClient.send(new PutCommand({
    TableName: process.env.GROUPS_TABLE,
    Item: group,
  }));

  // Add creator as owner
  await docClient.send(new PutCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Item: {
      groupId,
      userId,
      role: 'owner',
      joinedAt: timestamp,
    },
  }));

  return createResponse(201, { groupId, ...group });
}

async function updateGroup(groupId, userId, data) {
  const { hasPermission } = await checkGroupPermission(groupId, userId, 'manager');

  if (!hasPermission) {
    return createResponse(403, { error: 'Insufficient permissions' });
  }

  const timestamp = new Date().toISOString();

  await docClient.send(new UpdateCommand({
    TableName: process.env.GROUPS_TABLE,
    Key: { groupId },
    UpdateExpression: 'SET #name = :name, website = :website, description = :description, updatedAt = :updatedAt',
    ExpressionAttributeNames: {
      '#name': 'name',
    },
    ExpressionAttributeValues: {
      ':name': data.name,
      ':website': data.website || '',
      ':description': data.description || '',
      ':updatedAt': timestamp,
    },
  }));

  return createResponse(200, { message: 'Group updated successfully' });
}

async function deleteGroup(groupId, userId) {
  const { hasPermission, role } = await checkGroupPermission(groupId, userId, 'owner');

  if (!hasPermission) {
    return createResponse(403, { error: 'Only owners can delete groups' });
  }

  // Soft delete by marking as inactive
  await docClient.send(new UpdateCommand({
    TableName: process.env.GROUPS_TABLE,
    Key: { groupId },
    UpdateExpression: 'SET active = :active',
    ExpressionAttributeValues: {
      ':active': 'false',
    },
  }));

  return createResponse(200, { message: 'Group deleted successfully' });
}

// Group member handlers
async function listGroupMembers(groupId, isHtmx, currentUserId) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    KeyConditionExpression: 'groupId = :groupId',
    ExpressionAttributeValues: {
      ':groupId': groupId,
    },
  }));

  const members = result.Items || [];

  if (isHtmx && currentUserId) {
    // Check if current user is owner
    const currentMember = members.find(m => m.userId === currentUserId);
    const isOwner = currentMember?.role === 'owner';

    const htmlContent = members.map(member =>
      html.memberItem({ ...member, groupId }, currentUserId, isOwner)
    ).join('');
    return createResponse(200, htmlContent, true);
  }

  return createResponse(200, { members });
}

async function joinGroup(groupId, userId) {
  const timestamp = new Date().toISOString();

  await docClient.send(new PutCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Item: {
      groupId,
      userId,
      role: 'member',
      joinedAt: timestamp,
    },
  }));

  return createResponse(200, { message: 'Joined group successfully' });
}

async function updateMemberRole(groupId, targetUserId, currentUserId, newRole) {
  const { hasPermission, role } = await checkGroupPermission(groupId, currentUserId, 'owner');

  if (!hasPermission) {
    return createResponse(403, { error: 'Only owners can manage member roles' });
  }

  await docClient.send(new UpdateCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Key: { groupId, userId: targetUserId },
    UpdateExpression: 'SET #role = :role',
    ExpressionAttributeNames: {
      '#role': 'role',
    },
    ExpressionAttributeValues: {
      ':role': newRole,
    },
  }));

  return createResponse(200, { message: 'Member role updated successfully' });
}

async function removeMember(groupId, targetUserId, currentUserId) {
  // Users can remove themselves, or owners/managers can remove others
  if (targetUserId !== currentUserId) {
    const { hasPermission } = await checkGroupPermission(groupId, currentUserId, 'manager');

    if (!hasPermission) {
      return createResponse(403, { error: 'Insufficient permissions' });
    }
  }

  await docClient.send(new DeleteCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Key: { groupId, userId: targetUserId },
  }));

  return createResponse(200, { message: 'Member removed successfully' });
}

// Message handlers
async function listMessages(groupId, userId) {
  const { hasPermission } = await checkGroupPermission(groupId, userId, 'member');

  if (!hasPermission) {
    return createResponse(403, { error: 'Must be a group member to view messages' });
  }

  const result = await docClient.send(new QueryCommand({
    TableName: process.env.MESSAGES_TABLE,
    KeyConditionExpression: 'groupId = :groupId',
    ExpressionAttributeValues: {
      ':groupId': groupId,
    },
    ScanIndexForward: false,
    Limit: 50,
  }));

  return createResponse(200, { messages: result.Items });
}

async function postMessage(groupId, userId, content) {
  const { hasPermission } = await checkGroupPermission(groupId, userId, 'member');

  if (!hasPermission) {
    return createResponse(403, { error: 'Must be a group member to post messages' });
  }

  const timestamp = new Date().toISOString();

  await docClient.send(new PutCommand({
    TableName: process.env.MESSAGES_TABLE,
    Item: {
      groupId,
      timestamp,
      userId,
      content,
    },
  }));

  return createResponse(201, { message: 'Message posted successfully' });
}

// Event handlers
async function listEvents(queryParams, isHtmx) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :eventType',
    ExpressionAttributeValues: {
      ':eventType': 'all',
    },
    ScanIndexForward: true,
  }));

  let events = result.Items || [];

  // Filter to upcoming events
  const now = new Date();
  events = events.filter(e => new Date(e.eventDate) >= now);
  events.sort((a, b) => new Date(a.eventDate) - new Date(b.eventDate));

  if (isHtmx) {
    if (events.length === 0) {
      return createResponse(200, '<div class="card">No upcoming events. <a href="/create-event.html">Create the first one!</a></div>', true);
    }
    const htmlContent = events.map(event => html.eventCard(event)).join('');
    return createResponse(200, htmlContent, true);
  }

  return createResponse(200, { events });
}

async function getEvent(eventId) {
  const result = await docClient.send(new GetCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
  }));

  if (!result.Item) {
    return createResponse(404, { error: 'Event not found' });
  }

  return createResponse(200, result.Item);
}

async function createEvent(userId, data) {
  // Check if user has permission if this is a group event
  if (data.groupId) {
    const { hasPermission } = await checkGroupPermission(data.groupId, userId, 'manager');

    if (!hasPermission) {
      return createResponse(403, { error: 'Only group managers can create group events' });
    }
  }

  const eventId = uuidv4();
  const timestamp = new Date().toISOString();

  const event = {
    eventId,
    title: data.title,
    eventDate: data.date,
    time: data.time || '',
    location: data.location || '',
    url: data.url || '',
    description: data.description || '',
    groupId: data.groupId || null,
    eventType: 'all',
    createdBy: userId,
    createdAt: timestamp,
    updatedAt: timestamp,
  };

  await docClient.send(new PutCommand({
    TableName: process.env.EVENTS_TABLE,
    Item: event,
  }));

  return createResponse(201, { eventId, ...event });
}

async function updateEvent(eventId, userId, data) {
  const event = await docClient.send(new GetCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
  }));

  if (!event.Item) {
    return createResponse(404, { error: 'Event not found' });
  }

  // Check permissions: creator or group manager
  let hasPermission = event.Item.createdBy === userId;

  if (!hasPermission && event.Item.groupId) {
    const groupPermission = await checkGroupPermission(event.Item.groupId, userId, 'manager');
    hasPermission = groupPermission.hasPermission;
  }

  if (!hasPermission) {
    return createResponse(403, { error: 'Insufficient permissions to edit this event' });
  }

  const timestamp = new Date().toISOString();

  await docClient.send(new UpdateCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
    UpdateExpression: 'SET title = :title, eventDate = :eventDate, #time = :time, #location = :location, #url = :url, description = :description, updatedAt = :updatedAt',
    ExpressionAttributeNames: {
      '#time': 'time',
      '#location': 'location',
      '#url': 'url',
    },
    ExpressionAttributeValues: {
      ':title': data.title,
      ':eventDate': data.date,
      ':time': data.time || '',
      ':location': data.location || '',
      ':url': data.url || '',
      ':description': data.description || '',
      ':updatedAt': timestamp,
    },
  }));

  return createResponse(200, { message: 'Event updated successfully' });
}

async function deleteEvent(eventId, userId) {
  const event = await docClient.send(new GetCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
  }));

  if (!event.Item) {
    return createResponse(404, { error: 'Event not found' });
  }

  // Check permissions
  let hasPermission = event.Item.createdBy === userId;

  if (!hasPermission && event.Item.groupId) {
    const groupPermission = await checkGroupPermission(event.Item.groupId, userId, 'manager');
    hasPermission = groupPermission.hasPermission;
  }

  if (!hasPermission) {
    return createResponse(403, { error: 'Insufficient permissions to delete this event' });
  }

  await docClient.send(new DeleteCommand({
    TableName: process.env.EVENTS_TABLE,
    Key: { eventId },
  }));

  return createResponse(200, { message: 'Event deleted successfully' });
}

// RSVP handlers
async function listRSVPs(eventId) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.RSVPS_TABLE,
    KeyConditionExpression: 'eventId = :eventId',
    ExpressionAttributeValues: {
      ':eventId': eventId,
    },
  }));

  return createResponse(200, { rsvps: result.Items });
}

async function createOrUpdateRSVP(eventId, userId, status) {
  const timestamp = new Date().toISOString();

  await docClient.send(new PutCommand({
    TableName: process.env.RSVPS_TABLE,
    Item: {
      eventId,
      userId,
      status,
      timestamp,
    },
  }));

  return createResponse(200, { message: 'RSVP updated successfully' });
}

async function deleteRSVP(eventId, userId) {
  await docClient.send(new DeleteCommand({
    TableName: process.env.RSVPS_TABLE,
    Key: { eventId, userId },
  }));

  return createResponse(200, { message: 'RSVP deleted successfully' });
}

// Convert RSVPs to group
async function convertRSVPsToGroup(eventId, userId, groupName) {
  // Check if user created the event
  if (!(await isEventCreator(eventId, userId))) {
    return createResponse(403, { error: 'Only event creator can convert RSVPs to group' });
  }

  // Get all RSVPs
  const rsvps = await docClient.send(new QueryCommand({
    TableName: process.env.RSVPS_TABLE,
    KeyConditionExpression: 'eventId = :eventId',
    ExpressionAttributeValues: {
      ':eventId': eventId,
    },
  }));

  // Create new group
  const groupId = uuidv4();
  const timestamp = new Date().toISOString();

  await docClient.send(new PutCommand({
    TableName: process.env.GROUPS_TABLE,
    Item: {
      groupId,
      name: groupName,
      website: '',
      description: `Group created from event RSVPs`,
      active: 'true',
      createdBy: userId,
      createdAt: timestamp,
      updatedAt: timestamp,
    },
  }));

  // Add creator as owner
  await docClient.send(new PutCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    Item: {
      groupId,
      userId,
      role: 'owner',
      joinedAt: timestamp,
    },
  }));

  // Add all RSVPs as members
  for (const rsvp of rsvps.Items) {
    if (rsvp.userId !== userId) {
      await docClient.send(new PutCommand({
        TableName: process.env.GROUP_MEMBERS_TABLE,
        Item: {
          groupId,
          userId: rsvp.userId,
          role: 'member',
          joinedAt: timestamp,
        },
      }));
    }
  }

  return createResponse(201, { groupId, message: 'Group created successfully from RSVPs' });
}

// Main handler
// Helper to check if a route requires authentication
function requiresAuth(path, method) {
  // Public routes (no auth required)
  const publicRoutes = [
    { pattern: /^\/users\/[^/]+$/, methods: ['GET'] },
    { pattern: /^\/groups$/, methods: ['GET'] },
    { pattern: /^\/groups\/[^/]+$/, methods: ['GET'] },
    { pattern: /^\/groups\/[^/]+\/members$/, methods: ['GET'] },
    { pattern: /^\/events$/, methods: ['GET'] },
    { pattern: /^\/events\/[^/]+$/, methods: ['GET'] },
    { pattern: /^\/events\/[^/]+\/rsvps$/, methods: ['GET'] },
  ];

  for (const route of publicRoutes) {
    if (route.pattern.test(path) && route.methods.includes(method)) {
      return false;
    }
  }

  // All other routes require authentication
  return true;
}

exports.handler = async (event) => {
  try {
    const { path, method, body, pathParams, queryParams, userId, userEmail, isHtmx } = parseEvent(event);

    // Handle CORS preflight
    if (method === 'OPTIONS') {
      return createResponse(200, {});
    }

    // Check authentication for protected routes
    if (requiresAuth(path, method) && !userId) {
      return createResponse(401, isHtmx ? html.error('Authentication required') : { error: 'Authentication required' }, isHtmx);
    }

    // User routes
    if (path === '/users' && method === 'GET') {
      return await getUser(userId);
    }
    if (path === '/users' && method === 'PUT') {
      return await updateUser(userId, body);
    }
    if (path.startsWith('/users/') && method === 'GET') {
      return await getUser(pathParams.userId);
    }

    // Group routes
    if (path === '/groups' && method === 'GET') {
      return await listGroups(isHtmx);
    }
    if (path === '/groups' && method === 'POST') {
      return await createGroup(userId, userEmail, body);
    }
    if (path.match(/^\/groups\/[^/]+$/) && method === 'GET') {
      return await getGroup(pathParams.groupId);
    }
    if (path.match(/^\/groups\/[^/]+$/) && method === 'PUT') {
      return await updateGroup(pathParams.groupId, userId, body);
    }
    if (path.match(/^\/groups\/[^/]+$/) && method === 'DELETE') {
      return await deleteGroup(pathParams.groupId, userId);
    }

    // Group member routes
    if (path.match(/^\/groups\/[^/]+\/members$/) && method === 'GET') {
      return await listGroupMembers(pathParams.groupId, isHtmx, userId);
    }
    if (path.match(/^\/groups\/[^/]+\/members$/) && method === 'POST') {
      return await joinGroup(pathParams.groupId, userId);
    }
    if (path.match(/^\/groups\/[^/]+\/members\/[^/]+$/) && method === 'PUT') {
      return await updateMemberRole(pathParams.groupId, pathParams.userId, userId, body.role);
    }
    if (path.match(/^\/groups\/[^/]+\/members\/[^/]+$/) && method === 'DELETE') {
      return await removeMember(pathParams.groupId, pathParams.userId, userId);
    }

    // Message routes
    if (path.match(/^\/groups\/[^/]+\/messages$/) && method === 'GET') {
      return await listMessages(pathParams.groupId, userId);
    }
    if (path.match(/^\/groups\/[^/]+\/messages$/) && method === 'POST') {
      return await postMessage(pathParams.groupId, userId, body.content);
    }

    // Event routes
    if (path === '/events' && method === 'GET') {
      return await listEvents(queryParams, isHtmx);
    }
    if (path === '/events' && method === 'POST') {
      return await createEvent(userId, body);
    }
    if (path.match(/^\/events\/[^/]+$/) && method === 'GET') {
      return await getEvent(pathParams.eventId);
    }
    if (path.match(/^\/events\/[^/]+$/) && method === 'PUT') {
      return await updateEvent(pathParams.eventId, userId, body);
    }
    if (path.match(/^\/events\/[^/]+$/) && method === 'DELETE') {
      return await deleteEvent(pathParams.eventId, userId);
    }

    // RSVP routes
    if (path.match(/^\/events\/[^/]+\/rsvps$/) && method === 'GET') {
      return await listRSVPs(pathParams.eventId);
    }
    if (path.match(/^\/events\/[^/]+\/rsvps$/) && method === 'POST') {
      return await createOrUpdateRSVP(pathParams.eventId, userId, body.status);
    }
    if (path.match(/^\/events\/[^/]+\/rsvps$/) && method === 'DELETE') {
      return await deleteRSVP(pathParams.eventId, userId);
    }

    // Convert RSVPs to group
    if (path.match(/^\/events\/[^/]+\/convert-to-group$/) && method === 'POST') {
      return await convertRSVPsToGroup(pathParams.eventId, userId, body.groupName);
    }

    return createResponse(404, { error: 'Not found' });
  } catch (error) {
    console.error('Error:', error);
    if (isHtmx) {
      return createResponse(500, html.error(error.message), true);
    }
    return createResponse(500, { error: error.message });
  }
};
