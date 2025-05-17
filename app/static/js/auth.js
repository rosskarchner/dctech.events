// auth.js - Client-side authentication utilities

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a protected page that requires authentication
    if (document.body.classList.contains('requires-auth')) {
        checkAuthentication();
    }
});

// Function to check if the user is authenticated
function checkAuthentication() {
    fetch('/api/auth/user')
        .then(response => response.json())
        .then(data => {
            if (!data.authenticated) {
                // Redirect to login page if not authenticated
                window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
            } else if (document.body.classList.contains('requires-moderator') && 
                      !data.user.groups.includes('localhost-moderators')) {
                // Check if the page requires moderator privileges
                showAccessDenied();
            }
        })
        .catch(error => {
            console.error('Error checking authentication:', error);
        });
}

// Function to show access denied message
function showAccessDenied() {
    const main = document.querySelector('main');
    if (main) {
        main.innerHTML = `
            <div class="access-denied">
                <h2>Access Denied</h2>
                <p>You don't have permission to access this page. This page requires moderator privileges.</p>
                <p><a href="/">Return to Home</a></p>
            </div>
        `;
    }
}

// Function to determine if we're running locally
function isLocalEnvironment() {
    // Check if we're running on localhost or a local Docker container
    return window.location.hostname === 'localhost' || 
           window.location.hostname === '127.0.0.1' ||
           window.location.hostname.includes('docker');
}

// Function to get the appropriate login redirect URL
function getLoginRedirectUrl() {
    if (isLocalEnvironment()) {
        return '/login?next=' + encodeURIComponent(window.location.pathname);
    } else {
        return 'https://api.dctech.events/api/login-redirect';
    }
}