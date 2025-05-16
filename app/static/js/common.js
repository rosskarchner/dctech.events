// Add Authorization header to all HTMX requests to api.dctech.events
// Also strip domain from URLs that match the current domain to avoid CORS issues
document.addEventListener('htmx:configRequest', function(event) {
    // Get the current domain (without trailing slash)
    const currentDomain = window.location.origin;
    
    // Log the original URL for debugging
    console.log('Original URL:', event.detail.path);
    
    // Check if we have a full URL (starts with http:// or https://)
    if (event.detail.path.startsWith('http')) {
        const url = new URL(event.detail.path);
        
        // Check if the URL's origin matches the current origin
        if (url.origin === currentDomain) {
            // Strip the origin to make it a relative URL
            event.detail.path = url.pathname + url.search + url.hash;
            console.log('Converted to relative path:', event.detail.path);
        }
    }
    
    // Check if the request is going to api.dctech.events or is a protected endpoint
    if (event.detail.path.includes('api.dctech.events') || 
        event.detail.path.includes('/api/events/review') || 
        event.detail.path.includes('/api/events/approve') || 
        event.detail.path.includes('/api/events/delete') ||
        event.detail.path.includes('/api/groups/review') ||
        event.detail.path.includes('/api/groups/approve') ||
        event.detail.path.includes('/api/groups/delete')) {
        
        // Get the access token from localStorage
        const accessToken = localStorage.getItem('access_token');
        
        // If we have a token, add it to the headers
        if (accessToken) {
            event.detail.headers['Authorization'] = 'Bearer ' + accessToken;
        }
    }
});

// Handle unauthorized responses (401/403)
document.addEventListener('htmx:responseError', function(event) {
    if (event.detail.xhr.status === 401 || event.detail.xhr.status === 403) {
        // Store the current URL to return after login
        localStorage.setItem('auth_return_to', window.location.pathname);
        // Redirect to login
        window.location.href = 'https://api.dctech.events/api/login-redirect';
    }
});

// Handle the refreshGroupsList event to refresh the admin groups list
document.addEventListener('refreshGroupsList', function(event) {
    // Wait 1 second before refreshing to allow the user to see the success message
    setTimeout(function() {
        htmx.ajax('GET', 'https://api.dctech.events/api/admin/groups/all', {target: '#admin-content', swap: 'outerHTML'});

    }, 1000);
});