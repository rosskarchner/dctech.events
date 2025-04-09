// Add Authorization header to all HTMX requests to api.dctech.events
document.addEventListener('htmx:configRequest', function(event) {
    // Check if the request is going to api.dctech.events
    if (event.detail.path.includes('api.dctech.events')) {
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
