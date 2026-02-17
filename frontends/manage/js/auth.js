/**
 * Auth utilities for manage.dctech.events
 *
 * Handles Cognito OAuth 2.0 authorization code flow:
 * - Redirects unauthenticated users to Cognito login
 * - Exchanges authorization codes for tokens
 * - Verifies admin group membership from ID token
 * - Attaches Authorization header to all HTMX requests
 */

const AUTH_CONFIG = {
  cognitoDomain: 'https://login.dctech.events',
  clientId: '58j1h73i72v1kaim503bk2amgb',
  apiBaseUrl: 'https://next.dctech.events',
  redirectUri: window.location.origin + '/auth/callback.html',
  logoutUri: window.location.origin + '/',
  scopes: 'email openid profile',
  requiredGroup: 'admins',
};

/**
 * Decode a base64url-encoded string (used in JWTs).
 */
function base64UrlDecode(str) {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4 !== 0) {
    base64 += '=';
  }
  return atob(base64);
}

/**
 * Decode the payload of a JWT without verifying the signature.
 * Signature verification is handled server-side by API Gateway's Cognito authorizer.
 */
function decodeIdToken(token) {
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid JWT format');
  }
  const payload = JSON.parse(base64UrlDecode(parts[1]));
  return payload;
}

/**
 * Check whether the decoded ID token indicates admin group membership.
 */
function isAdmin(tokenPayload) {
  const groups = tokenPayload['cognito:groups'] || [];
  return groups.includes(AUTH_CONFIG.requiredGroup);
}

/**
 * Retrieve stored tokens from sessionStorage.
 */
function getTokens() {
  const data = sessionStorage.getItem('manage_auth');
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

/**
 * Store tokens in sessionStorage.
 */
function setTokens(tokens) {
  sessionStorage.setItem('manage_auth', JSON.stringify(tokens));
}

/**
 * Clear stored tokens.
 */
function clearTokens() {
  sessionStorage.removeItem('manage_auth');
}

/**
 * Get the current access token, or null if not authenticated.
 */
function getAccessToken() {
  const tokens = getTokens();
  if (!tokens || !tokens.access_token) return null;

  // Check expiry
  if (tokens.expires_at && Date.now() >= tokens.expires_at) {
    clearTokens();
    return null;
  }

  return tokens.access_token;
}

/**
 * Get the current ID token, or null if not authenticated.
 */
function getIdToken() {
  const tokens = getTokens();
  if (!tokens || !tokens.id_token) return null;
  return tokens.id_token;
}

/**
 * Build the Cognito authorization URL and redirect the user there.
 */
function redirectToLogin() {
  const state = crypto.randomUUID();
  sessionStorage.setItem('oauth_state', state);

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: AUTH_CONFIG.clientId,
    redirect_uri: AUTH_CONFIG.redirectUri,
    scope: AUTH_CONFIG.scopes,
    state: state,
  });

  window.location.href = `${AUTH_CONFIG.cognitoDomain}/oauth2/authorize?${params.toString()}`;
}

/**
 * Exchange an authorization code for tokens via the Cognito token endpoint.
 */
async function exchangeCodeForTokens(code) {
  const response = await fetch(`${AUTH_CONFIG.cognitoDomain}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: AUTH_CONFIG.clientId,
      code: code,
      redirect_uri: AUTH_CONFIG.redirectUri,
    }).toString(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token exchange failed: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Sign the user out: clear tokens and redirect to Cognito logout.
 */
function signOut() {
  clearTokens();
  const params = new URLSearchParams({
    client_id: AUTH_CONFIG.clientId,
    logout_uri: AUTH_CONFIG.logoutUri,
  });
  window.location.href = `${AUTH_CONFIG.cognitoDomain}/logout?${params.toString()}`;
}

/**
 * Require authentication and admin group membership.
 * Call this at the top of every admin page.
 * Redirects to login if not authenticated, or to an error page if not admin.
 */
function requireAdmin() {
  const token = getAccessToken();
  if (!token) {
    redirectToLogin();
    return false;
  }

  const idToken = getIdToken();
  if (!idToken) {
    redirectToLogin();
    return false;
  }

  try {
    const payload = decodeIdToken(idToken);
    if (!isAdmin(payload)) {
      document.body.innerHTML = `
        <div style="max-width:600px;margin:80px auto;text-align:center;font-family:system-ui,sans-serif;">
          <h1>Access Denied</h1>
          <p>You are not a member of the <strong>admins</strong> group.</p>
          <p>Contact an administrator if you believe this is an error.</p>
          <button onclick="signOut()" style="margin-top:1rem;padding:0.5rem 1.5rem;cursor:pointer;">Sign Out</button>
        </div>
      `;
      return false;
    }
  } catch (e) {
    console.error('Failed to decode ID token:', e);
    clearTokens();
    redirectToLogin();
    return false;
  }

  return true;
}

/**
 * Get the current user's display info from the ID token.
 */
function getCurrentUser() {
  const idToken = getIdToken();
  if (!idToken) return null;
  try {
    const payload = decodeIdToken(idToken);
    return {
      email: payload.email || '',
      name: payload.name || payload.email || 'Admin',
      groups: payload['cognito:groups'] || [],
    };
  } catch {
    return null;
  }
}

/**
 * Update the user info display in the nav bar.
 */
function updateUserDisplay() {
  const user = getCurrentUser();
  const el = document.getElementById('user-info');
  if (el && user) {
    el.textContent = user.name;
  }
}

/**
 * Configure HTMX to include the Authorization header on every request
 * and set the API base URL.
 */
function setupHtmx() {
  // Add Authorization header to all HTMX requests
  document.body.addEventListener('htmx:configRequest', function (event) {
    const token = getAccessToken();
    if (token) {
      event.detail.headers['Authorization'] = 'Bearer ' + token;
    }

    // Rewrite relative URLs to the API base
    const path = event.detail.path;
    if (path && path.startsWith('/')) {
      event.detail.path = AUTH_CONFIG.apiBaseUrl + path;
    }
  });

  // Handle 401 responses by redirecting to login
  document.body.addEventListener('htmx:responseError', function (event) {
    if (event.detail.xhr && event.detail.xhr.status === 401) {
      clearTokens();
      redirectToLogin();
    }
  });
}

/**
 * Initialize auth on page load.
 * Returns true if the user is authenticated and authorized.
 */
function initAuth() {
  if (!requireAdmin()) {
    return false;
  }
  setupHtmx();
  updateUserDisplay();
  return true;
}

// Expose to global scope for use in inline handlers
window.AUTH_CONFIG = AUTH_CONFIG;
window.signOut = signOut;
window.redirectToLogin = redirectToLogin;
window.initAuth = initAuth;
window.getAccessToken = getAccessToken;
window.getIdToken = getIdToken;
window.getCurrentUser = getCurrentUser;
window.exchangeCodeForTokens = exchangeCodeForTokens;
window.decodeIdToken = decodeIdToken;
window.isAdmin = isAdmin;
window.setTokens = setTokens;
window.clearTokens = clearTokens;
window.base64UrlDecode = base64UrlDecode;
