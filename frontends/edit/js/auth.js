(function() {
/**
 * Consolidated Cognito Authentication Module for the /edit/ UI
 *
 * Handles OAuth 2.0 Authorization Code flow with Cognito Hosted UI.
 * Supports both general users and admins.
 */

const EDIT_CONFIG = window.DctechEditConfig || {
  appBasePath: '/',
  apiBaseUrl: '',
  authCallbackPath: '/auth/callback.html',
  appHomePath: '/',
  appUrl(path) {
    const normalized = path ? path.replace(/^\/+/, '') : '';
    return `/${normalized}`;
  },
  apiUrl(path) {
    return path;
  },
};

const AUTH_CONFIG = {
  userPoolClientId: '58j1h73i72v1kaim503bk2amgb',
  cognitoDomain: 'https://login.dctech.events',
  redirectUri: window.location.origin + EDIT_CONFIG.authCallbackPath,
  logoutUri: window.location.origin + EDIT_CONFIG.appHomePath,
  scopes: 'email openid profile',
  apiPaths: ['/api/', '/admin/', '/submit', '/my-submissions', '/health'],
  adminGroup: 'admins'
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
    const base64Url = tokenResponse.id_token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    const payload = JSON.parse(jsonPayload);
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

function isAdmin() {
  const user = getUserInfo();
  return user && user.groups && user.groups.includes(AUTH_CONFIG.adminGroup);
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
    tokenData.refresh_token = tokenData.refresh_token || refreshToken;
    storeTokens(tokenData);
    return true;
  } catch (err) {
    console.error('Token refresh error:', err);
    clearTokens();
    return false;
  }
}

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

async function authorizedFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  await ensureValidToken();
  const token = getAccessToken() || getIdToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', 'Bearer ' + token);
  }

  const isAbsolute = /^https?:\/\//i.test(path);
  const url = isAbsolute ? path : EDIT_CONFIG.apiUrl(path);

  return fetch(url, {
    ...options,
    headers,
  });
}

// ---- Login / Logout ----

function getLoginUrl(returnPath) {
  const state = returnPath || EDIT_CONFIG.appHomePath;
  sessionStorage.setItem('oauth_state', state);
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
  document.addEventListener('htmx:configRequest', function(event) {
    const path = event.detail.path || '';
    
    // Check if path is an API path
    const isApiRequest = AUTH_CONFIG.apiPaths.some(p => path.startsWith(p));

    if (isApiRequest) {
      if (EDIT_CONFIG.apiBaseUrl) {
        event.detail.path = EDIT_CONFIG.apiUrl(path);
      }
      const token = getAccessToken() || getIdToken();
      if (token) {
        event.detail.headers['Authorization'] = 'Bearer ' + token;
      }
    }
  });

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
  const admin = isAdmin();

  document.querySelectorAll('[data-auth="logged-in"]').forEach(el => {
    el.classList.toggle('hidden', !loggedIn);
  });
  document.querySelectorAll('[data-auth="logged-out"]').forEach(el => {
    el.classList.toggle('hidden', loggedIn);
  });
  document.querySelectorAll('[data-auth="admin"]').forEach(el => {
    el.classList.toggle('hidden', !admin);
  });

  if (loggedIn && user) {
    document.querySelectorAll('[data-user="email"]').forEach(el => {
      el.textContent = user.email;
    });
    document.querySelectorAll('[data-user="name"]').forEach(el => {
      el.textContent = user.name;
    });
  }
}

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

function requireAdmin() {
  if (!isAuthenticated()) {
    login(window.location.pathname);
    return false;
  }
  if (!isAdmin()) {
    document.body.innerHTML = `
      <div style="max-width:600px;margin:80px auto;text-align:center;font-family:system-ui,sans-serif;">
        <h1>Access Denied</h1>
        <p>You are not a member of the <strong>admins</strong> group.</p>
        <p>Contact an administrator if you believe this is an error.</p>
        <button onclick="DctechAuth.logout()" style="margin-top:1rem;padding:0.5rem 1.5rem;cursor:pointer;">Sign Out</button>
      </div>
    `;
    return false;
  }
  return true;
}

// ---- Initialization ----

function initAuth() {
  updateAuthUI();
}

setupHtmxAuth();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAuth);
} else {
  initAuth();
}

// Export for use by other scripts
window.DctechAuth = {
  AUTH_CONFIG,
  EDIT_CONFIG,
  login,
  logout,
  signOut: logout, // Compatibility
  isAuthenticated,
  isAdmin,
  getUserInfo,
  getAccessToken,
  getIdToken,
  ensureValidToken,
  requireAuth,
  requireAdmin,
  initAuth, // Compatibility
  exchangeCodeForTokens,
  clearTokens,
  updateAuthUI,
  storeTokens,
  getApiUrl: EDIT_CONFIG.apiUrl,
  getAppUrl: EDIT_CONFIG.appUrl,
  authorizedFetch,
};
})();
