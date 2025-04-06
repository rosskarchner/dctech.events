/**
 * Authentication helper functions
 */

// Check if user is authenticated
function isAuthenticated() {
    // Check for auth cookie
    return document.cookie.includes('auth_token=');
}

// Require authentication for the current page
function requireAuth() {
    if (!isAuthenticated()) {
        // Redirect to login page with return URL
        window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname + window.location.search);
        return false;
    }
    return true;
}

// Add event listener for logout buttons
document.addEventListener('DOMContentLoaded', function() {
    const logoutButtons = document.querySelectorAll('.logout-button');
    logoutButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = '/logout';
        });
    });
});
