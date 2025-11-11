/**
 * CloudFront Function for LocalTech Events subdomain routing
 *
 * This function intercepts viewer requests and routes them to the appropriate
 * S3 prefix based on the subdomain:
 *
 * - localtech.events → /index.html (homepage)
 * - dc.localtech.events → /dc/index.html (DC city site)
 * - sf.localtech.events → /sf/index.html (SF city site)
 * - etc.
 *
 * Note: CloudFront Functions are lightweight and run in CloudFront edge locations.
 * They have limited capabilities compared to Lambda@Edge but are faster and cheaper.
 */

function handler(event) {
    var request = event.request;
    var host = request.headers.host.value;

    // Extract subdomain from host header
    // host can be:
    // - localtech.events (apex)
    // - dc.localtech.events (subdomain)
    // - www.localtech.events (www redirect)

    var subdomain = null;
    var parts = host.split('.');

    // If there are 3 or more parts (e.g., dc.localtech.events), extract subdomain
    if (parts.length >= 3) {
        subdomain = parts[0];

        // Redirect www to apex
        if (subdomain === 'www') {
            return {
                statusCode: 301,
                statusDescription: 'Moved Permanently',
                headers: {
                    'location': { value: 'https://localtech.events' + request.uri }
                }
            };
        }
    }

    // Rewrite the URI based on subdomain
    var uri = request.uri;

    if (subdomain && subdomain !== 'www') {
        // City subdomain: prepend /city-slug/
        // e.g., /events/ → /dc/events/
        uri = '/' + subdomain + uri;
    }
    // else: apex domain, keep URI as-is (homepage content in root)

    // Handle directory requests (ensure they get index.html)
    if (uri.endsWith('/')) {
        uri += 'index.html';
    }

    // If no extension, assume it's a directory and add /index.html
    var hasExtension = /\.[a-zA-Z0-9]+$/.test(uri);
    if (!hasExtension) {
        uri += '/index.html';
    }

    request.uri = uri;

    return request;
}
