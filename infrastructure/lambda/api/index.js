const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand, PutCommand, UpdateCommand, DeleteCommand, QueryCommand } = require('@aws-sdk/lib-dynamodb');

const { CognitoJwtVerifier } = require('aws-jwt-verify');

const { v4: uuidv4 } = require('uuid');

const Handlebars = require('handlebars');
const fs = require('fs');
const path = require('path');

const { extractLocationInfo, normalizeAddress, getRegionName } = require('./location_utils');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);

// Check if event is online-only based on location
const isOnlineOnlyEvent = (location) => {
  if (!location || typeof location !== 'string') {
    return true; // No location = online only
  }

  const locationLower = location.toLowerCase();
  const onlineIndicators = [
    'online',
    'virtual',
    'zoom',
    'webinar',
    'remote',
    'teams',
    'meet.google.com',
    'whereby.com',
    'hopin.com',
    'discord',
    'twitch'
  ];

  return onlineIndicators.some(indicator => locationLower.includes(indicator));
};

// Create JWT verifiers for Cognito tokens
const accessTokenVerifier = CognitoJwtVerifier.create({
  userPoolId: process.env.USER_POOL_ID,
  tokenUse: 'access',
  clientId: process.env.USER_POOL_CLIENT_ID,
});

const idTokenVerifier = CognitoJwtVerifier.create({
  userPoolId: process.env.USER_POOL_ID,
  tokenUse: 'id',
  clientId: process.env.USER_POOL_CLIENT_ID,
});

// ============================================
// Handlebars Template Setup
// ============================================

const TEMPLATES_PATH = '/opt/nodejs/templates';

// Template cache to avoid re-compiling
const templateCache = {};

const loadTemplate = (name) => {
  if (templateCache[name]) {
    return templateCache[name];
  }

  try {
    const templatePath = path.join(TEMPLATES_PATH, `${name}.hbs`);
    const templateString = fs.readFileSync(templatePath, 'utf8');
    templateCache[name] = Handlebars.compile(templateString);
    return templateCache[name];
  } catch (error) {
    console.error(`Failed to load template ${name}:`, error);
    return null;
  }
};

// Register partials
const registerPartials = () => {
  try {
    const partialsPath = path.join(TEMPLATES_PATH, 'partials');
    if (fs.existsSync(partialsPath)) {
      const partialFiles = fs.readdirSync(partialsPath);
      partialFiles.forEach(file => {
        const name = file.replace('.hbs', '');
        const partial = fs.readFileSync(path.join(partialsPath, file), 'utf8');
        Handlebars.registerPartial(name, partial);
      });
    }
  } catch (error) {
    console.error('Failed to register partials:', error);
  }
};

// Register custom Handlebars helpers
Handlebars.registerHelper('upper', (str) => str?.toUpperCase() || '');
Handlebars.registerHelper('formatTime', (time) => {
  if (!time) return '';
  const [h, m] = time.split(':');
  const hour = parseInt(h);
  const meridiem = hour >= 12 ? 'pm' : 'am';
  const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
  return `${displayHour}:${m} ${meridiem}`;
});

Handlebars.registerHelper('formatDate', (date) => {
  if (!date) return '';
  return new Date(date).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  });
});

Handlebars.registerHelper('formatShortDate', (date) => {
  if (!date) return '';
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  });
});

Handlebars.registerHelper('eq', (a, b) => a === b);
Handlebars.registerHelper('contains', (arr, item) => arr?.includes(item) || false);
Handlebars.registerHelper('year', () => new Date().getFullYear());
Handlebars.registerHelper('getState', (location) => {
  if (!location) return '';
  const parts = location.split(',').map(p => p.trim());
  return parts.length >= 2 ? parts[1] : '';
});

// Helper to get state abbreviation from "City, STATE" format
Handlebars.registerHelper('getStateAbbrev', (cityState) => {
  if (!cityState) return '';
  const parts = cityState.split(',').map(p => p.trim());
  return parts.length >= 2 ? parts[1].toLowerCase() : '';
});

// Helper to get city slug from "City, STATE" format
Handlebars.registerHelper('getCitySlug', (cityState) => {
  if (!cityState) return '';
  const parts = cityState.split(',').map(p => p.trim());
  return parts.length >= 1 ? parts[0].toLowerCase().replace(/\s+/g, '-') : '';
});

// Initialize partials on Lambda cold start
registerPartials();

// Template rendering helper
// Note: Templates use {{}} for automatic HTML escaping. The {{{content}}} in base.hbs
// is intentional for rendering pre-rendered page content, not user input directly.
// User inputs must be escaped before passing to templates or use {{}} syntax.
const renderTemplate = (name, data) => {
  const template = loadTemplate(name);
  if (!template) {
    return `<div>Error: Template ${name} not found</div>`;
  }
  return template(data);
};

// Helper to verify and decode JWT token with signature verification
async function verifyJWT(token) {
  // Try access token first
  try {
    const payload = await accessTokenVerifier.verify(token);
    return payload;
  } catch (error) {
    // If access token verification fails, try ID token
    try {
      const payload = await idTokenVerifier.verify(token);
      return payload;
    } catch (idError) {
      console.error('JWT verification failed:', idError.message);
      return null;
    }
  }
}

// Helper to parse API Gateway event
async function parseEvent(event) {
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

  // If not in authorizer context, verify token from Authorization header
  if (!userId) {
    const authHeader = headers['authorization'] || headers['Authorization'] || '';
    if (authHeader.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const claims = await verifyJWT(token);
      if (claims) {
        userId = claims.sub || null;
        userEmail = claims.email || null;
      }
    }
  }

  // If still no userId, check for idToken cookie
  if (!userId) {
    const cookieHeader = headers['cookie'] || headers['Cookie'] || '';
    const cookies = {};
    cookieHeader.split(';').forEach(cookie => {
      const [name, ...rest] = cookie.split('=');
      if (name && rest.length > 0) {
        cookies[name.trim()] = rest.join('=').trim();
      }
    });

    if (cookies.idToken) {
      const claims = await verifyJWT(cookies.idToken);
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

  await docClient.send(new PutCommand({
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
  const { hasPermission } = await checkGroupPermission(groupId, userId, 'owner');

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
  const { hasPermission } = await checkGroupPermission(groupId, currentUserId, 'owner');

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

// ============================================
// Site Detection and Routing
// ============================================

// Determine which site (organize or next) is being accessed
const determineSite = (event) => {
  const headers = event.headers || {};
  const host = headers.host || headers.Host || '';
  const customHeader = headers['x-site'] || headers['X-Site'] || '';

  if (customHeader === 'next' || host.includes('next.dctech.events')) {
    return 'next';
  }
  return 'organize';
};

// ============================================
// Helper Functions for next.dctech.events
// ============================================

// Format events by day (mirrors Flask's prepare_events_by_day)
const prepareEventsByDay = (events, addWeekLinks = false) => {
  const eventsByDay = {};

  // Filter out online-only events and normalize locations
  const filteredEvents = events.filter(event => !isOnlineOnlyEvent(event.location));
  
  filteredEvents.forEach(event => {
    if (event.location) {
      event.location = normalizeAddress(event.location);
      const { city, state } = extractLocationInfo(event.location);
      event.city = city;
      event.state = state;
    }
  });

  // Group duplicates by title + date + time
  const eventGroups = {};
  filteredEvents.forEach(event => {
    const key = `${event.title}|||${event.eventDate}|||${event.time || 'TBD'}`;
    if (!eventGroups[key]) {
      eventGroups[key] = [];
    }
    eventGroups[key].push(event);
  });

  // Merge duplicates
  const mergedEvents = Object.values(eventGroups).map(group => {
    if (group.length === 1) {
      return group[0];
    }

    // Multiple events with same title/date/time - merge them
    const primary = group[0];
    const alsoPublishedBy = [];
    
    for (let i = 1; i < group.length; i++) {
      if (group[i].groupId && group[i].groupId !== primary.groupId) {
        alsoPublishedBy.push({
          group: group[i].group || group[i].groupId,
          url: group[i].group_website || group[i].url
        });
      }
    }

    if (alsoPublishedBy.length > 0) {
      primary.also_published_by = alsoPublishedBy;
    }

    return primary;
  });

  // Add events to their respective days
  mergedEvents.forEach(event => {
    const startDate = new Date(event.eventDate + 'T00:00:00Z');
    let endDate = null;
    if (event.endDate) {
      try {
        endDate = new Date(event.endDate + 'T00:00:00Z');
      } catch (e) {
        // Invalid end date
      }
    }

    // Generate list of dates for this event
    const eventDates = [];
    if (endDate && endDate > startDate) {
      let currentDate = new Date(startDate);
      while (currentDate <= endDate) {
        eventDates.push(new Date(currentDate));
        currentDate.setUTCDate(currentDate.getUTCDate() + 1);
      }
    } else {
      eventDates.push(startDate);
    }

    // Add event to each day
    eventDates.forEach((eventDate, i) => {
      const dayKey = eventDate.toISOString().split('T')[0];
      const shortDate = formatShortDate(dayKey);

      if (!eventsByDay[dayKey]) {
        let weekUrl = null;
        if (addWeekLinks) {
          const weekId = getCurrentWeekId(); // Would need to implement week calculation
          weekUrl = `/week/${weekId}/#${dayKey}`;
        }

        eventsByDay[dayKey] = {
          date: dayKey,
          short_date: shortDate,
          week_url: weekUrl,
          time_slots: {},
          has_events: false
        };
      }

      // Format time
      let timeKey = 'TBD';
      let formattedTime = 'TBD';
      const originalTime = event.time || '';

      if (originalTime && typeof originalTime === 'string' && originalTime.includes(':')) {
        try {
          timeKey = originalTime.trim();
          formattedTime = formatTime(timeKey);
        } catch (e) {
          // Keep TBD
        }
      }

      // Create event copy for this day
      const eventCopy = { ...event };
      eventCopy.time = timeKey !== 'TBD' ? timeKey : '';
      eventCopy.formatted_time = formattedTime;
      
      // Add (continuing) for multi-day events
      if (i > 0) {
        eventCopy.display_title = `${event.title} (continuing)`;
      } else {
        eventCopy.display_title = event.title;
      }

      // Create time slot if it doesn't exist
      if (!eventsByDay[dayKey].time_slots[timeKey]) {
        eventsByDay[dayKey].time_slots[timeKey] = [];
      }

      eventsByDay[dayKey].time_slots[timeKey].push(eventCopy);
      eventsByDay[dayKey].has_events = true;
    });
  });

  // Convert to sorted array
  const sortedDays = Object.keys(eventsByDay).sort();
  const daysData = [];

  sortedDays.forEach(dayKey => {
    const dayData = eventsByDay[dayKey];
    
    // Sort time slots
    const timeSortKey = (timeStr) => {
      if (timeStr === 'TBD') return [24, 0];
      try {
        const [hour, minute] = timeStr.split(':').map(Number);
        return [hour, minute];
      } catch (e) {
        return [0, 0];
      }
    };

    const sortedTimes = Object.keys(dayData.time_slots).sort((a, b) => {
      const [hourA, minA] = timeSortKey(a);
      const [hourB, minB] = timeSortKey(b);
      if (hourA !== hourB) return hourA - hourB;
      return minA - minB;
    });

    const timeSlots = sortedTimes.map(time => ({
      time,
      events: dayData.time_slots[time].sort((a, b) => 
        (a.title || '').localeCompare(b.title || '')
      )
    }));

    daysData.push({
      date: dayData.date,
      short_date: dayData.short_date,
      week_url: dayData.week_url,
      time_slots: timeSlots,
      has_events: dayData.has_events
    });
  });

  return daysData;
};

// JavaScript utility functions (also registered as Handlebars helpers above)
const formatShortDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr + 'T00:00:00Z');
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC'
  });
};

const formatTime = (time) => {
  if (!time) return '';
  const [h, m] = time.split(':');
  const hour = parseInt(h);
  const meridiem = hour >= 12 ? 'pm' : 'am';
  const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
  return `${displayHour}:${m} ${meridiem}`;
};

const formatDate = (date) => {
  return date.toISOString().split('T')[0]; // YYYY-MM-DD
};

const getCurrentWeekId = () => {
  const now = new Date();
  const year = now.getFullYear();
  const week = getWeekNumber(now);
  return `${year}-W${String(week).padStart(2, '0')}`;
};

const getWeekNumber = (date) => {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
};

const getDateFromISOWeek = (year, week, day) => {
  const simple = new Date(year, 0, 1 + (week - 1) * 7);
  const dow = simple.getDay();
  const isoWeekStart = simple;
  if (dow <= 4) {
    isoWeekStart.setDate(simple.getDate() - simple.getDay() + 1);
  } else {
    isoWeekStart.setDate(simple.getDate() + 8 - simple.getDay());
  }
  isoWeekStart.setDate(isoWeekStart.getDate() + (day - 1));
  return isoWeekStart;
};

const extractCityState = (location) => {
  if (!location) return ['', ''];
  const { city, state } = extractLocationInfo(location);
  return [city || '', state || ''];
};

// Get upcoming events (next N days)
const getUpcomingEvents = async (daysAhead = 90) => {
  const endDate = new Date();
  endDate.setDate(endDate.getDate() + daysAhead);

  const result = await docClient.send(new QueryCommand({
    TableName: process.env.EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :type AND eventDate BETWEEN :start AND :end',
    ExpressionAttributeValues: {
      ':type': 'all',
      ':start': formatDate(new Date()),
      ':end': formatDate(endDate),
    },
  }));

  return result.Items || [];
};

// Get events by week
const getEventsByWeek = async (weekId) => {
  const [year, week] = weekId.split('-W');
  const start = getDateFromISOWeek(parseInt(year), parseInt(week), 1);
  const end = getDateFromISOWeek(parseInt(year), parseInt(week), 7);

  const result = await docClient.send(new QueryCommand({
    TableName: process.env.EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :type AND eventDate BETWEEN :start AND :end',
    ExpressionAttributeValues: {
      ':type': 'all',
      ':start': formatDate(start),
      ':end': formatDate(end),
    },
  }));

  return result.Items || [];
};

// Get events by state
const getEventsByState = async (state) => {
  const events = await getUpcomingEvents();
  return events.filter(e => {
    const [, eventState] = extractCityState(e.location);
    return eventState?.toUpperCase() === state.toUpperCase();
  });
};

// Get events by city
const getEventsByCity = async (state, city) => {
  const events = await getEventsByState(state);
  return events.filter(e => {
    const [eventCity] = extractCityState(e.location);
    return eventCity?.toLowerCase() === city.toLowerCase();
  });
};

// Get active groups
const getActiveGroups = async () => {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.GROUPS_TABLE,
    IndexName: 'activeGroupsIndex',
    KeyConditionExpression: 'active = :active',
    ExpressionAttributeValues: {
      ':active': 'true',
    },
  }));

  return result.Items || [];
};

// Get locations with event counts
const getLocationsWithEventCounts = async () => {
  const events = await getUpcomingEvents();
  const locationStats = {};
  const citySet = new Set();

  // Count events by region and collect cities
  events.forEach(event => {
    const { city, state } = extractLocationInfo(event.location || '');
    if (['DC', 'VA', 'MD'].includes(state)) {
      // Add to region count
      const region = getRegionName(state);
      locationStats[region] = (locationStats[region] || 0) + 1;

      // Add to city set (skip Washington, DC since it's same as DC region)
      if (city && !(city === 'Washington' && state === 'DC')) {
        citySet.add(`${city}, ${state}`);
      }
    }
  });

  // Get city counts
  const cityStats = {};
  for (const cityState of citySet) {
    const [city, state] = cityState.split(', ');
    const cityEvents = events.filter(event => {
      const { city: eventCity, state: eventState } = extractLocationInfo(event.location || '');
      return eventCity === city && eventState === state;
    });

    if (cityEvents.length > 0) {
      const displayCity = state === 'DC' ? 'Washington' : city;
      cityStats[`${displayCity}, ${state}`] = cityEvents.length;
    }
  }

  return {
    locationStats,
    cityStats: Object.entries(cityStats)
      .sort((a, b) => b[1] - a[1])
      .reduce((obj, [key, value]) => {
        obj[key] = value;
        return obj;
      }, {})
  };
};

// Generate stats for homepage
const generateStats = (events) => {
  const upcomingCount = events.length;
  const locations = [...new Set(events.map(e => e.location).filter(Boolean))];
  const groups = [...new Set(events.map(e => e.groupId).filter(Boolean))];

  return {
    upcomingCount,
    locationCount: locations.length,
    groupCount: groups.length,
  };
};

// Generate sitemap XML
const generateSitemap = () => {
  const baseUrl = 'https://next.dctech.events';
  const today = formatDate(new Date());

  const urls = [
    { loc: '/', lastmod: today, priority: 1.0 },
    { loc: '/week/LATEST/', lastmod: today, priority: 0.9 },
    { loc: '/locations/', lastmod: today, priority: 0.8 },
    { loc: '/groups/', lastmod: today, priority: 0.8 },
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(url => `  <url>
    <loc>${baseUrl}${url.loc}</loc>
    <lastmod>${url.lastmod}</lastmod>
    <priority>${url.priority}</priority>
  </url>`).join('\n')}
</urlset>`;

  return xml;
};

// Cognito login URL helper
const cognitoLoginUrl = (redirectPath) => {
  const domain = process.env.COGNITO_DOMAIN;
  const region = process.env.USER_POOL_REGION || 'us-east-1';
  const clientId = process.env.USER_POOL_CLIENT_ID;
  
  // Construct full Cognito URL
  const cognitoUrl = `https://${domain}.auth.${region}.amazoncognito.com`;
  const redirectUri = encodeURIComponent(`https://next.dctech.events/callback`);
  
  return `${cognitoUrl}/login?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&state=${encodeURIComponent(redirectPath)}`;
};

// ============================================
// Route Handlers for next.dctech.events
// ============================================

const handleNextRequest = async (path, method, userId, isHtmx, event, parsedBody) => {
  // PUBLIC ROUTES

  // GET / - Homepage with upcoming events
  if (path === '/' && method === 'GET') {
    const events = await getUpcomingEvents();
    const eventsByDay = prepareEventsByDay(events);
    const stats = generateStats(events);

    const html = renderTemplate('homepage', {
      eventsByDay,
      stats,
      isAuthenticated: !!userId,
      isHtmx,
    });

    return createResponse(200, html, true);
  }

  // GET /week/:weekId - Week view
  if (path.match(/^\/week\/[\d]{4}-W\d{2}\/?$/)) {
    const weekId = path.match(/\/week\/([\d]{4}-W\d{2})/)[1];
    
    // Validate week number (should be 1-53)
    const weekMatch = weekId.match(/^(\d{4})-W(\d{2})$/);
    if (weekMatch) {
      const weekNum = parseInt(weekMatch[2], 10);
      if (weekNum < 1 || weekNum > 53) {
        return createResponse(400, 'Invalid week number', false);
      }
    }
    
    const events = await getEventsByWeek(weekId);
    const eventsByDay = prepareEventsByDay(events);
    
    // Calculate prev/next week
    const [year, week] = weekId.split('-W');
    const weekNum = parseInt(week);
    const yearNum = parseInt(year);
    
    // Calculate previous week
    let prevWeekNum, prevYear;
    if (weekNum > 1) {
      prevWeekNum = weekNum - 1;
      prevYear = yearNum;
    } else {
      // Get last week of previous year (could be 52 or 53)
      const lastDayOfPrevYear = new Date(yearNum - 1, 11, 31);
      prevWeekNum = getWeekNumber(lastDayOfPrevYear);
      prevYear = yearNum - 1;
    }
    
    // Calculate next week
    let nextWeekNum, nextYear;
    // Get last week of current year to handle 52/53 week years
    const lastDayOfYear = new Date(yearNum, 11, 31);
    const maxWeeksInYear = getWeekNumber(lastDayOfYear);
    
    if (weekNum < maxWeeksInYear) {
      nextWeekNum = weekNum + 1;
      nextYear = yearNum;
    } else {
      nextWeekNum = 1;
      nextYear = yearNum + 1;
    }
    
    const prevWeek = `${prevYear}-W${String(prevWeekNum).padStart(2, '0')}`;
    const nextWeek = `${nextYear}-W${String(nextWeekNum).padStart(2, '0')}`;

    const html = renderTemplate('week_page', {
      weekId,
      eventsByDay,
      isAuthenticated: !!userId,
      currentWeek: getCurrentWeekId(),
      prevWeek,
      nextWeek,
    });

    return createResponse(200, html, true);
  }

  // GET /locations/ - Location index
  if (path === '/locations/' && method === 'GET') {
    const { locationStats, cityStats } = await getLocationsWithEventCounts();

    const html = renderTemplate('locations_index', {
      locationStats,
      cityStats,
      isAuthenticated: !!userId,
    });

    return createResponse(200, html, true);
  }

  // GET /locations/:state - State-filtered events
  if (path.match(/^\/locations\/[A-Za-z]{2}\/?$/i)) {
    const state = path.match(/\/locations\/([A-Za-z]{2})/i)[1].toUpperCase();
    const events = await getEventsByState(state);
    const eventsByDay = prepareEventsByDay(events);
    const cities = [...new Set(events.map(e => extractCityState(e.location)[0]).filter(Boolean))];

    const html = renderTemplate('location_page', {
      state,
      eventsByDay,
      cities,
      isAuthenticated: !!userId,
    });

    return createResponse(200, html, true);
  }

  // GET /locations/:state/:city - City-filtered events
  if (path.match(/^\/locations\/[A-Za-z]{2}\/[\w-]+\/?$/i)) {
    const match = path.match(/\/locations\/([A-Za-z]{2})\/([^/]+)/i);
    const state = match[1].toUpperCase();
    const citySlug = match[2];
    // Convert slug back to city name (e.g., "mc-lean" -> "McLean")
    const city = citySlug.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
    
    const events = await getEventsByCity(state, city);
    const eventsByDay = prepareEventsByDay(events);

    const html = renderTemplate('location_page', {
      state,
      city,
      eventsByDay,
      isAuthenticated: !!userId,
    });

    return createResponse(200, html, true);
  }

  // GET /groups/ - Groups list
  if (path === '/groups/' && method === 'GET') {
    const groups = await getActiveGroups();
    const sortedGroups = groups.sort((a, b) => a.name.localeCompare(b.name));

    const html = renderTemplate('groups_list', {
      groups: sortedGroups,
      isAuthenticated: !!userId,
    });

    return createResponse(200, html, true);
  }

  // GET /newsletter.html - HTML newsletter
  if (path === '/newsletter.html' && method === 'GET') {
    const events = await getUpcomingEvents(14);
    const eventsByDay = prepareEventsByDay(events);

    const html = renderTemplate('newsletter', {
      format: 'html',
      eventsByDay,
    });

    return createResponse(200, html, true);
  }

  // GET /sitemap.xml - XML sitemap
  if (path === '/sitemap.xml' && method === 'GET') {
    const sitemap = generateSitemap();
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/xml',
      },
      body: sitemap,
    };
  }

  // GET /callback - OAuth callback handler
  if (path === '/callback' && method === 'GET') {
    const code = event.queryStringParameters?.code;
    const state = event.queryStringParameters?.state || '/';
    
    if (!code) {
      return createResponse(400, 'Missing authorization code', false);
    }

    // Exchange code for tokens with Cognito
    try {
      const domain = process.env.COGNITO_DOMAIN;
      const region = process.env.USER_POOL_REGION || 'us-east-1';
      const clientId = process.env.USER_POOL_CLIENT_ID;
      const tokenUrl = `https://${domain}.auth.${region}.amazoncognito.com/oauth2/token`;
      
      const response = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: clientId,
          code: code,
          redirect_uri: 'https://next.dctech.events/callback',
        }).toString(),
      });

      const tokens = await response.json();
      
      if (!response.ok) {
        console.error('Token exchange failed:', tokens);
        return createResponse(400, 'Failed to authenticate', false);
      }

      // Set cookie with ID token and redirect to original destination
      return {
        statusCode: 302,
        headers: {
          'Location': state,
          'Set-Cookie': `idToken=${tokens.id_token}; Path=/; Secure; HttpOnly; Max-Age=3600`,
        },
        body: '',
      };
    } catch (error) {
      console.error('Callback error:', error);
      return createResponse(500, 'Authentication error', false);
    }
  }

  // PROTECTED ROUTES (require authentication)

  // GET /submit/ - Event submission form
  if (path === '/submit/' && method === 'GET') {
    if (!userId) {
      return {
        statusCode: 302,
        headers: {
          'Location': cognitoLoginUrl('/submit/'),
        },
        body: '',
      };
    }

    const html = renderTemplate('submit_event', {
      userId,
      isAuthenticated: true,
    });

    return createResponse(200, html, true);
  }

  // POST /submit/ - Create event
  if (path === '/submit/' && method === 'POST') {
    if (!userId) {
      return createResponse(403, { error: 'Authentication required' });
    }

    // Use parsedBody parameter (already parsed by parseEvent in main handler)
    // parseEvent handles both JSON and form-encoded content types
    const body = parsedBody || {};
    
    // Validate required fields
    if (!body.title || !body.title.trim()) {
      return createResponse(400, html.error('Event title is required'), true);
    }
    if (!body.date || !body.date.trim()) {
      return createResponse(400, html.error('Event date is required'), true);
    }
    
    const eventId = uuidv4();
    const timestamp = new Date().toISOString();

    await docClient.send(new PutCommand({
      TableName: process.env.EVENTS_TABLE,
      Item: {
        eventId,
        title: body.title.trim(),
        eventDate: body.date,
        time: body.time || '',
        location: body.location || '',
        url: body.url || '',
        description: body.description || '',
        eventType: 'all',
        createdBy: userId,
        createdAt: timestamp,
        updatedAt: timestamp,
      },
    }));

    const html = renderTemplate('event_created_confirmation', {
      eventId,
      title: body.title,
    });

    return createResponse(200, html, true);
  }

  // GET /submit-group/ - Group submission form
  if (path === '/submit-group/' && method === 'GET') {
    if (!userId) {
      return {
        statusCode: 302,
        headers: {
          'Location': cognitoLoginUrl('/submit-group/'),
        },
        body: '',
      };
    }

    const html = renderTemplate('submit_group', {
      userId,
      isAuthenticated: true,
    });

    return createResponse(200, html, true);
  }

  // POST /submit-group/ - Create group
  if (path === '/submit-group/' && method === 'POST') {
    if (!userId) {
      return createResponse(403, { error: 'Authentication required' });
    }

    // Use parsedBody parameter (already parsed by parseEvent in main handler)
    // parseEvent handles both JSON and form-encoded content types
    const body = parsedBody || {};
    
    // Validate required fields
    if (!body.name || !body.name.trim()) {
      return createResponse(400, html.error('Group name is required'), true);
    }
    
    const groupId = uuidv4();
    const timestamp = new Date().toISOString();

    await docClient.send(new PutCommand({
      TableName: process.env.GROUPS_TABLE,
      Item: {
        groupId,
        name: body.name.trim(),
        website: body.website || '',
        ical: body.ical || '',
        description: body.description || '',
        active: 'false', // Requires admin approval
        createdBy: userId,
        createdAt: timestamp,
        updatedAt: timestamp,
      },
    }));

    const html = renderTemplate('group_created_confirmation', {
      groupId,
      name: body.name,
    });

    return createResponse(200, html, true);
  }

  // Default 404
  return createResponse(404, '<h1>Page Not Found</h1>', true);
};

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
  let isHtmx = false;
  try {
    const site = determineSite(event);
    const { path, method, body, pathParams, queryParams, userId, userEmail, isHtmx: isHtmxRequest } = await parseEvent(event);
    isHtmx = isHtmxRequest;

    // Handle CORS preflight
    if (method === 'OPTIONS') {
      return createResponse(200, {});
    }

    // Route to appropriate site handler
    if (site === 'next') {
      return await handleNextRequest(path, method, userId, isHtmx, event, body);
    }

    // Original organize.dctech.events routes below
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
