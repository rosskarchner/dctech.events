// Check if the user is authenticated
function isAuthenticated() {
  try {
    const idToken = localStorage.getItem('id_token');
    const expiration = localStorage.getItem('token_expiration');
    
    if (!idToken || !expiration) {
      return false;
    }
    
    // Check if token is expired
    const now = Math.floor(Date.now() / 1000);
    if (now > parseInt(expiration, 10)) {
      return false;
    }
    
    return true;
  } catch (error) {
    console.error('Error checking authentication:', error);
    return false;
  }
}

// Sign out the user
function signOut() {
  localStorage.removeItem('id_token');
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expiration');
  localStorage.removeItem('user_email');
  localStorage.removeItem('user_name');
  
  window.location.href = '/';
}

// Get the current user's information
function getCurrentUser() {
  if (!isAuthenticated()) {
    return null;
  }
  
  return {
    email: localStorage.getItem('user_email'),
    name: localStorage.getItem('user_name')
  };
}

// Redirect to login
function login(returnTo = window.location.pathname) {
  localStorage.setItem('auth_return_to', returnTo);
  window.location.href = 'https://api.dctech.events/api/login-redirect';
}
