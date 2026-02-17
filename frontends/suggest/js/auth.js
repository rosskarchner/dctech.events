/**
 * Cognito Authentication Module for suggest.dctech.events
 *
 * Handles OAuth 2.0 Authorization Code flow with Cognito Hosted UI.
 * Stores tokens in sessionStorage and attaches them to HTMX requests.
 */

const AUTH_CONFIG = {
  userPoolClientId: '58j1h73i72v1kaim503bk2amgb',
  cognitoDomain: 'https://login.dctech.events',
  redirectUri: 'https://suggest.dctech.events/auth/callback.html',
  logoutUri: 'https://suggest.dctech.events/',
  scopes: 'email openid profile',
  apiBaseUrl: 'https://next.dctech.events',
};

const TOKEN_KEYS = {
  accessToken: 'dctech_access_token',
  idToken: 'dctech_id_token',
  refreshToken: 'dctech_refresh_token',
  tokenExpiry: 'dctech_token_expiry',
  userInfo: 'dctech_user_info',
};

// ---- Token Storage ----

function storeTokens(tokenResponse) {
  const now = Date.now();
  const expiresIn = tokenResponse.expires_in || 3600;

  sessionStorage.setItem(TOKEN_KEYS.accessToken, tokenResponse.access_token);
  sessionStorage.setItem(TOKEN_KEYS.idToken, tokenResponse.id_token);
  sessionStorage.setItem(TOKEN_KEYS.tokenExpiry, String(now + expiresIn * 1000));

  if (tokenResponse.refresh_token) {
    sessionStorage.setItem(TOKEN_KEYS.refreshToken, tokenResponse.refresh_token);
  }

  // Decode ID token to extract user info
  try {
    const payload = JSON.parse(atob(tokenResponse.id_token.split('.')[1]));
    sessionStorage.setItem(TOKEN_KEYS.userInfo, JSON.stringify({
      email: payload.email,
      name: payload.name || payload.email,
      sub: payload.sub,
      groups: payload['cognito:groups'] || [],
    }));
  } catch (e) {
    console.warn('Failed to decode ID token:', e);
  }
}

function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEYS.accessToken);
}

function getIdToken() {
  return sessionStorage.getItem(TOKEN_KEYS.idToken);
}

function getRefreshToken() {
  return sessionStorage.getItem(TOKEN_KEYS.refreshToken);
}

function getUserInfo() {
  const raw = sessionStorage.getItem(TOKEN_KEYS.userInfo);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function isAuthenticated() {
  const token = getAccessToken();
  const expiry = sessionStorage.getItem(TOKEN_KEYS.tokenExpiry);
  if (!token || !expiry) return false;
  return Date.now() < parseInt(expiry, 10);
}

function clearTokens() {
  Object.values(TOKEN_KEYS).forEach(key => sessionStorage.removeItem(key));
}

// ---- Token Refresh ----

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    console.warn('No refresh token available');
    return false;
  }

  try {
    const params = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: AUTH_CONFIG.userPoolClientId,
      refresh_token: refreshToken,
    });

    const response = await fetch(`${AUTH_CONFIG.cognitoDomain}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    });

    if (!response.ok) {
      console.error('Token refresh failed:', response.status);
      clearTokens();
      return false;
    }

    const tokenData = await response.json();
    // Refresh response does not include a new refresh_token; keep the existing one
    tokenData.refresh_token = tokenData.refresh_token || refreshToken;
    storeTokens(tokenData);
    return true;
  } catch (err) {
    console.error('Token refresh error:', err);
    clearTokens();
    return false;
  }
}

/**
 * Ensure we have a valid token, refreshing if needed.
 * Returns the access token or null.
 */
async function ensureValidToken() {
  if (isAuthenticated()) {
    return getAccessToken();
  }

  const refreshed = await refreshAccessToken();
  if (refreshed) {
    return getAccessToken();
  }

  return null;
}

// ---- Login / Logout ----

function getLoginUrl(returnPath) {
  const state = returnPath || '/submit-event.html';
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: AUTH_CONFIG.userPoolClientId,
    redirect_uri: AUTH_CONFIG.redirectUri,
    scope: AUTH_CONFIG.scopes,
    state: state,
  });
  return `${AUTH_CONFIG.cognitoDomain}/login?${params.toString()}`;
}

function login(returnPath) {
  window.location.href = getLoginUrl(returnPath);
}

function logout() {
  clearTokens();
  const params = new URLSearchParams({
    client_id: AUTH_CONFIG.userPoolClientId,
    logout_uri: AUTH_CONFIG.logoutUri,
  });
  window.location.href = `${AUTH_CONFIG.cognitoDomain}/logout?${params.toString()}`;
}

// ---- Authorization Code Exchange ----

async function exchangeCodeForTokens(code) {
  const params = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: AUTH_CONFIG.userPoolClientId,
    code: code,
    redirect_uri: AUTH_CONFIG.redirectUri,
  });

  const response = await fetch(`${AUTH_CONFIG.cognitoDomain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token exchange failed (${response.status}): ${errorText}`);
  }

  const tokenData = await response.json();
  storeTokens(tokenData);
  return tokenData;
}

// ---- HTMX Integration ----

function setupHtmxAuth() {
  // Attach Authorization header and rewrite relative URLs to API base
  document.addEventListener('htmx:configRequest', function(event) {
    const path = event.detail.path || '';

    // Rewrite relative URLs to the API base
    if (path.startsWith('/')) {
      event.detail.path = AUTH_CONFIG.apiBaseUrl + path;
    }

    // Add auth header for API requests (use cached token synchronously)
    if (event.detail.path.startsWith(AUTH_CONFIG.apiBaseUrl)) {
      const token = getIdToken();
      if (token) {
        event.detail.headers['Authorization'] = 'Bearer ' + token;
      }
    }
  });

  // Handle 401 responses by redirecting to login
  document.addEventListener('htmx:responseError', function(event) {
    if (event.detail.xhr && event.detail.xhr.status === 401) {
      clearTokens();
      login(window.location.pathname);
    }
  });
}

// ---- UI Helpers ----

function updateAuthUI() {
  const user = getUserInfo();
  const loggedIn = isAuthenticated();

  // Show/hide elements based on auth state
  document.querySelectorAll('[data-auth="logged-in"]').forEach(el => {
    el.classList.toggle('hidden', !loggedIn);
  });
  document.querySelectorAll('[data-auth="logged-out"]').forEach(el => {
    el.classList.toggle('hidden', loggedIn);
  });

  // Populate user info
  if (loggedIn && user) {
    document.querySelectorAll('[data-user="email"]').forEach(el => {
      el.textContent = user.email;
    });
    document.querySelectorAll('[data-user="name"]').forEach(el => {
      el.textContent = user.name;
    });
  }
}

/**
 * Require authentication to access the current page.
 * Shows a sign-in message if not authenticated.
 */
function requireAuth() {
  if (isAuthenticated()) return true;
  document.querySelector('main').innerHTML = `
    <div class="card" style="text-align:center; padding: 2rem;">
      <h2>Sign in required</h2>
      <p>You need to sign in to access this page.</p>
      <a href="${getLoginUrl(window.location.pathname)}" class="btn btn-primary">Sign In</a>
    </div>`;
  return false;
}

// ---- Initialization ----

function initAuth() {
  setupHtmxAuth();
  updateAuthUI();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAuth);
} else {
  initAuth();
}

// Export for use by other scripts
window.DctechAuth = {
  AUTH_CONFIG,
  login,
  logout,
  isAuthenticated,
  getUserInfo,
  getAccessToken,
  getIdToken,
  ensureValidToken,
  requireAuth,
  exchangeCodeForTokens,
  clearTokens,
  updateAuthUI,
  storeTokens,
};
