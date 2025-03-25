// auth.js
const isTokenExpired = (token) => {
    if (!token) return true;
    
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const expiry = payload.exp * 1000; // Convert to milliseconds
        return Date.now() >= expiry;
    } catch (e) {
        console.error('Error checking token expiry:', e);
        return true;
    }
};

const getAuthToken = async () => {
    let token = localStorage.getItem('authToken');
    
    if (!token) {
        console.error('No auth token found');
        return null;
    }

    // Add debug logging
    console.log('Token format check:', {
        hasToken: !!token,
        includes_dots: token.includes('.'),
        length: token.length
    });

    if (!token.includes('.')) {
        console.error('Invalid token format - token does not contain required "." separators');
        return null;
    }

    if (isTokenExpired(token)) {
        console.log('Token expired, attempting refresh');
        try {
            token = await refreshToken();
        } catch (e) {
            console.error('Token refresh failed:', e);
            return null;
        }
    }

    return token;
};

const checkAuth = async () => {
    const token = await getAuthToken();
    if (!token) {
        console.log('No valid token found, redirecting to login');
        window.location.href = '/login.html';
        return false;
    }
    return true;
};

// Add this if you need to decode the token payload
const decodeToken = (token) => {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        return JSON.parse(atob(base64));
    } catch (e) {
        console.error('Error decoding token:', e);
        return null;
    }
};
