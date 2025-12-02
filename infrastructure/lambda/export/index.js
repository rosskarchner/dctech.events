const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, QueryCommand } = require('@aws-sdk/lib-dynamodb');
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const yaml = require('js-yaml');

const dynamoClient = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(dynamoClient);
const s3Client = new S3Client({});

/**
 * Export groups and events to YAML files in S3
 * This Lambda runs on a schedule (every 5 minutes) to keep the exports fresh
 */
exports.handler = async (event) => {
  try {
    console.log('Starting export process...');

    // Fetch all active groups
    const groupsResult = await docClient.send(new QueryCommand({
      TableName: process.env.GROUPS_TABLE,
      IndexName: 'activeGroupsIndex',
      KeyConditionExpression: 'active = :active',
      ExpressionAttributeValues: {
        ':active': 'true',
      },
    }));

    // Fetch all upcoming events
    const eventsResult = await docClient.send(new QueryCommand({
      TableName: process.env.EVENTS_TABLE,
      IndexName: 'dateEventsIndex',
      KeyConditionExpression: 'eventType = :eventType',
      ExpressionAttributeValues: {
        ':eventType': 'all',
      },
      ScanIndexForward: true,
    }));

    // Transform groups to match the _groups YAML format
    const groupsData = {};
    for (const group of groupsResult.Items) {
      // Use a slug-like key (group name lowercased and hyphenated)
      const key = group.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');

      groupsData[key] = {
        active: group.active === 'true',
        name: group.name,
        ical: group.ical || '',
        submitted_by: group.createdBy || 'anonymous',
        submitter_link: '',
        website: group.website || '',
      };
    }

    // Transform events to match the _single_events YAML format
    const eventsData = {};
    const now = new Date();

    for (const event of eventsResult.Items) {
      const eventDate = new Date(event.eventDate);

      // Only include future events
      if (eventDate >= now) {
        // Use date + title as key
        const dateStr = event.eventDate;
        const titleSlug = event.title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
        const key = `${dateStr}-${titleSlug}`;

        eventsData[key] = {
          date: event.eventDate,
          location: event.location || '',
          submitted_by: event.createdBy || 'anonymous',
          submitter_link: '',
          time: event.time || '',
          title: event.title,
          url: event.url || '',
        };
      }
    }

    // Convert to YAML
    const groupsYaml = yaml.dump(groupsData, {
      lineWidth: -1,
      noRefs: true,
    });

    const eventsYaml = yaml.dump(eventsData, {
      lineWidth: -1,
      noRefs: true,
    });

    // Upload to S3
    await s3Client.send(new PutObjectCommand({
      Bucket: process.env.WEBSITE_BUCKET,
      Key: 'groups.yaml',
      Body: groupsYaml,
      ContentType: 'application/x-yaml',
      CacheControl: 'max-age=300', // Cache for 5 minutes
    }));

    await s3Client.send(new PutObjectCommand({
      Bucket: process.env.WEBSITE_BUCKET,
      Key: 'events.yaml',
      Body: eventsYaml,
      ContentType: 'application/x-yaml',
      CacheControl: 'max-age=300', // Cache for 5 minutes
    }));

    console.log(`Export complete: ${Object.keys(groupsData).length} groups, ${Object.keys(eventsData).length} events`);

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Export completed successfully',
        groupsCount: Object.keys(groupsData).length,
        eventsCount: Object.keys(eventsData).length,
      }),
    };
  } catch (error) {
    console.error('Export error:', error);
    throw error;
  }
};
