/**
 * Authentication helper functions
 */

// Check if the user is authenticated
function isAuthenticated() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        console.log('No auth token found');
        return false;
    }
    
    // Check if token is expired
    try {
        const payload = parseJwt(token);
        const expiry = payload.exp * 1000; // Convert to milliseconds
        const now = Date.now();
        
        if (now >= expiry) {
            console.log('Token expired');
            localStorage.removeItem('authToken');
            return false;
        }
        
        return true;
    } catch (e) {
        console.error('Error parsing token:', e);
        localStorage.removeItem('authToken');
        return false;
    }
}

// Parse JWT token
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));

        return JSON.parse(jsonPayload);
    } catch (e) {
        console.error('Error parsing JWT:', e);
        throw e;
    }
}

// Handle login success
function handleLoginSuccess(token, refreshToken) {
    // Store the tokens
    localStorage.setItem('authToken', token);
    if (refreshToken) {
        localStorage.setItem('refreshToken', refreshToken);
    }
    
    // Get the redirect URL directly from the URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const redirectUrl = urlParams.get('redirect') || '/';
    console.log('Redirect URL from query params:', redirectUrl);
    
    // Redirect to the URL
    window.location.href = redirectUrl;
}

// Logout function
function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('loginRedirect');
    window.location.href = '/';
}

// Add event listener for logout buttons
document.addEventListener('DOMContentLoaded', function() {
    const logoutButtons = document.querySelectorAll('.logout-button');
    logoutButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            logout();
        });
    });
});
