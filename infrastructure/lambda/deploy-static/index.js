/**
 * Custom Resource Lambda for deploying static assets to S3
 *
 * This Lambda is triggered during CDK stack deployment to upload
 * static assets (CSS, JS, images) to the S3 bucket.
 */

const { S3Client, PutObjectCommand, ListObjectsV2Command, DeleteObjectCommand, DeleteObjectsCommand } = require('@aws-sdk/client-s3');
const { CloudFrontClient, CreateInvalidationCommand } = require('@aws-sdk/client-cloudfront');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const s3Client = new S3Client({});
const cloudFrontClient = new CloudFrontClient({});

const BUCKET_NAME = process.env.BUCKET_NAME;
const DISTRIBUTION_ID = process.env.DISTRIBUTION_ID;
const STATIC_ASSETS_PATH = '/var/task/static'; // Path where static assets are bundled

// AWS API limits
const MAX_S3_DELETE_BATCH_SIZE = 1000; // Maximum objects per S3 DeleteObjects request
const MAX_CLOUDFRONT_INVALIDATION_PATHS = 3000; // Maximum paths per CloudFront invalidation

/**
 * Get MIME type from file extension
 */
function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.eot': 'application/vnd.ms-fontobject',
  };
  return mimeTypes[ext] || 'application/octet-stream';
}

/**
 * Recursively get all files in a directory
 */
function getAllFiles(dirPath, arrayOfFiles = []) {
  const files = fs.readdirSync(dirPath);

  files.forEach(file => {
    const filePath = path.join(dirPath, file);
    if (fs.statSync(filePath).isDirectory()) {
      arrayOfFiles = getAllFiles(filePath, arrayOfFiles);
    } else {
      arrayOfFiles.push(filePath);
    }
  });

  return arrayOfFiles;
}

/**
 * Upload a file to S3
 */
async function uploadFile(filePath, bucketName) {
  const fileContent = fs.readFileSync(filePath);
  const relativePath = path.relative(STATIC_ASSETS_PATH, filePath);
  const s3Key = `static/${relativePath}`;

  const contentType = getMimeType(filePath);

  console.log(`Uploading ${s3Key} (${contentType})`);

  await s3Client.send(new PutObjectCommand({
    Bucket: bucketName,
    Key: s3Key,
    Body: fileContent,
    ContentType: contentType,
    CacheControl: 'public, max-age=31536000', // 1 year for static assets
  }));

  return s3Key;
}

/**
 * Delete all existing static assets from S3
 */
async function cleanupOldAssets(bucketName) {
  console.log('Cleaning up old static assets...');

  let continuationToken = undefined;
  let totalDeleted = 0;

  do {
    const listResponse = await s3Client.send(new ListObjectsV2Command({
      Bucket: bucketName,
      Prefix: 'static/',
      ContinuationToken: continuationToken,
    }));

    if (!listResponse.Contents || listResponse.Contents.length === 0) {
      if (!continuationToken) {
        console.log('No old assets to clean up');
      }
      break;
    }

    console.log(`Deleting batch of ${listResponse.Contents.length} files...`);

    // Batch delete in chunks
    const deleteObjects = listResponse.Contents.map(obj => ({ Key: obj.Key }));
    for (let i = 0; i < deleteObjects.length; i += MAX_S3_DELETE_BATCH_SIZE) {
      const batch = deleteObjects.slice(i, i + MAX_S3_DELETE_BATCH_SIZE);
      await s3Client.send(new DeleteObjectsCommand({
        Bucket: bucketName,
        Delete: {
          Objects: batch,
        },
      }));
      console.log(`Deleted batch of ${batch.length} files`);
      totalDeleted += batch.length;
    }

    continuationToken = listResponse.IsTruncated ? listResponse.NextContinuationToken : undefined;
  } while (continuationToken);

  console.log(`Cleanup complete: deleted ${totalDeleted} files`);
}

/**
 * Deploy all static assets
 */
async function deployStaticAssets() {
  console.log(`Deploying static assets to ${BUCKET_NAME}`);
  console.log(`Static assets path: ${STATIC_ASSETS_PATH}`);

  // Check if static assets directory exists
  if (!fs.existsSync(STATIC_ASSETS_PATH)) {
    console.log('No static assets directory found, skipping deployment');
    return [];
  }

  // Clean up old assets first
  await cleanupOldAssets(BUCKET_NAME);

  // Get all files to upload
  const files = getAllFiles(STATIC_ASSETS_PATH);
  console.log(`Found ${files.length} files to upload`);

  // Upload all files
  const uploadedKeys = [];
  for (const file of files) {
    const key = await uploadFile(file, BUCKET_NAME);
    uploadedKeys.push(key);
  }

  console.log(`Successfully uploaded ${uploadedKeys.length} files`);
  return uploadedKeys;
}

/**
 * Invalidate CloudFront cache
 */
async function invalidateCache(paths) {
  if (!DISTRIBUTION_ID) {
    console.log('No CloudFront distribution ID provided, skipping invalidation');
    return;
  }

  if (paths.length === 0) {
    console.log('No paths to invalidate');
    return;
  }

  console.log(`Invalidating CloudFront cache for ${paths.length} paths`);

  // Use wildcard if too many paths or just invalidate /static/*
  const pathsToInvalidate = paths.length > MAX_CLOUDFRONT_INVALIDATION_PATHS ? ['/static/*'] : paths.map(p => `/${p}`);

  const invalidationId = crypto.randomBytes(16).toString('hex');

  await cloudFrontClient.send(new CreateInvalidationCommand({
    DistributionId: DISTRIBUTION_ID,
    InvalidationBatch: {
      CallerReference: invalidationId,
      Paths: {
        Quantity: pathsToInvalidate.length,
        Items: pathsToInvalidate,
      },
    },
  }));

  console.log(`CloudFront invalidation created: ${invalidationId}`);
}

/**
 * Send response to CloudFormation
 */
async function sendResponse(event, context, status, data = {}) {
  const responseBody = JSON.stringify({
    Status: status,
    Reason: `See CloudWatch Log Stream: ${context.logStreamName}`,
    PhysicalResourceId: context.logStreamName,
    StackId: event.StackId,
    RequestId: event.RequestId,
    LogicalResourceId: event.LogicalResourceId,
    Data: data,
  });

  console.log('Response body:', responseBody);

  const https = require('https');
  const url = require('url');

  const parsedUrl = url.parse(event.ResponseURL);
  const options = {
    hostname: parsedUrl.hostname,
    port: 443,
    path: parsedUrl.path,
    method: 'PUT',
    headers: {
      'Content-Type': '',
      'Content-Length': responseBody.length,
    },
  };

  return new Promise((resolve, reject) => {
    const request = https.request(options, (response) => {
      console.log(`Status code: ${response.statusCode}`);
      resolve();
    });

    request.on('error', (error) => {
      console.error('sendResponse Error:', error);
      reject(error);
    });

    request.write(responseBody);
    request.end();
  });
}

/**
 * Main handler
 */
exports.handler = async (event, context) => {
  console.log('Event:', JSON.stringify(event, null, 2));

  try {
    const requestType = event.RequestType;

    if (requestType === 'Delete') {
      console.log('Delete request - cleaning up static assets');
      await cleanupOldAssets(BUCKET_NAME);
      await sendResponse(event, context, 'SUCCESS');
      return;
    }

    if (requestType === 'Create' || requestType === 'Update') {
      console.log(`${requestType} request - deploying static assets`);

      const uploadedPaths = await deployStaticAssets();

      // Invalidate CloudFront cache
      if (uploadedPaths.length > 0) {
        await invalidateCache(uploadedPaths);
      }

      await sendResponse(event, context, 'SUCCESS', {
        FilesDeployed: uploadedPaths.length,
      });
      return;
    }

    throw new Error(`Unknown request type: ${requestType}`);
  } catch (error) {
    console.error('Error:', error);
    try {
      await sendResponse(event, context, 'FAILED', {
        Error: error.message,
      });
    } catch (sendError) {
      console.error('Failed to send error response to CloudFormation:', sendError);
    }
    // Do not rethrow - response has been sent to CloudFormation
  }
};
