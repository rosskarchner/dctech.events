const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand, PutCommand, UpdateCommand, DeleteCommand, QueryCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');

const client = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(client);

// Helper to parse API Gateway event
function parseEvent(event) {
  const path = event.path || event.resource;
  const method = event.httpMethod;
  const body = event.body ? JSON.parse(event.body) : null;
  const pathParams = event.pathParameters || {};
  const queryParams = event.queryStringParameters || {};
  const userId = event.requestContext?.authorizer?.claims?.sub || null;
  const userEmail = event.requestContext?.authorizer?.claims?.email || null;

  return { path, method, body, pathParams, queryParams, userId, userEmail };
}

// Helper to create API response
function createResponse(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type,Authorization',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    },
    body: JSON.stringify(body),
  };
}

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
async function listGroups() {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.GROUPS_TABLE,
    IndexName: 'activeGroupsIndex',
    KeyConditionExpression: 'active = :active',
    ExpressionAttributeValues: {
      ':active': 'true',
    },
  }));

  return createResponse(200, { groups: result.Items });
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
async function listGroupMembers(groupId) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.GROUP_MEMBERS_TABLE,
    KeyConditionExpression: 'groupId = :groupId',
    ExpressionAttributeValues: {
      ':groupId': groupId,
    },
  }));

  return createResponse(200, { members: result.Items });
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
async function listEvents(queryParams) {
  const result = await docClient.send(new QueryCommand({
    TableName: process.env.EVENTS_TABLE,
    IndexName: 'dateEventsIndex',
    KeyConditionExpression: 'eventType = :eventType',
    ExpressionAttributeValues: {
      ':eventType': 'all',
    },
    ScanIndexForward: true,
  }));

  return createResponse(200, { events: result.Items });
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
exports.handler = async (event) => {
  try {
    const { path, method, body, pathParams, queryParams, userId, userEmail } = parseEvent(event);

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
      return await listGroups();
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
      return await listGroupMembers(pathParams.groupId);
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
      return await listEvents(queryParams);
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
    return createResponse(500, { error: error.message });
  }
};
