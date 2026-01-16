// Import Octokit from npm package
import { Octokit } from 'octokit';

// GitHub OAuth Configuration
// These values are passed from the Flask template via window.GITHUB_CONFIG
const CONFIG = {
    clientId: window.GITHUB_CONFIG?.clientId || '',
    redirectUri: window.location.origin + '/submit-group/', // OAuth will redirect back here
    scope: 'public_repo',
    // The OAuth callback endpoint in add.dctech.events
    callbackEndpoint: window.GITHUB_CONFIG?.callbackEndpoint || ''
};

/**
 * Get the selected city from hostname or session storage
 */
function getSelectedCity() {
    // Parse city from hostname
    const hostname = window.location.hostname;
    const parts = hostname.split('.');

    // Handle different deployment scenarios
    if (parts.length >= 3 && parts[parts.length - 2] === 'localtech') {
        // dc.localtech.events -> dc
        return parts[0];
    } else if (parts[0] === 'dctech') {
        // dctech.events -> dc (default)
        return 'dc';
    } else if (parts[0] === 'add') {
        // add.dctech.events -> check session or default
        return sessionStorage.getItem('city_slug') || 'dc';
    }

    return 'dc';  // Fallback default
}

// Repository configuration
const REPO_CONFIG = {
    owner: 'rosskarchner',
    repo: 'dctech.events',
    branch: 'main',
    getTargetDir: function() {
        return '_groups';
    }
};

// State management
let octokit = null;
let userData = null;

// Initialize on page load
function initialize() {
    initializeAuth();
    setupEventListeners();
}

// Handle both cases: DOM already loaded or still loading
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    // DOM already loaded, initialize immediately
    initialize();
}

/**
 * Initialize authentication state
 */
function initializeAuth() {
    // Check for OAuth callback
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');
    const error = urlParams.get('error');

    if (error) {
        showAuthError('Authentication failed: ' + error);
        return;
    }

    if (accessToken) {
        // Store token and clean URL
        sessionStorage.setItem('github_token', accessToken);
        window.history.replaceState({}, document.title, window.location.pathname);
        initializeOctokit(accessToken);
        return;
    }

    // Check for existing token
    const storedToken = sessionStorage.getItem('github_token');
    if (storedToken) {
        initializeOctokit(storedToken);
    }
}

/**
 * Initialize Octokit with access token
 */
async function initializeOctokit(token) {
    try {
        octokit = new Octokit({ auth: token });

        // Get user data
        const { data } = await octokit.rest.users.getAuthenticated();
        userData = data;

        // Update UI
        showAuthenticatedState();
    } catch (error) {
        console.error('Authentication error:', error);
        sessionStorage.removeItem('github_token');
        showAuthError('Failed to authenticate with GitHub');
    }
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    const githubLoginBtn = document.getElementById('github-login');
    const groupForm = document.getElementById('group-form');
    const cancelBtn = document.getElementById('cancel-btn');
    const submitAnotherBtn = document.getElementById('submit-another');

    if (githubLoginBtn) {
        githubLoginBtn.addEventListener('click', handleGitHubLogin);
    } else {
        console.error('GitHub login button not found');
    }

    if (groupForm) {
        groupForm.addEventListener('submit', handleFormSubmit);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', resetForm);
    }

    if (submitAnotherBtn) {
        submitAnotherBtn.addEventListener('click', () => {
            document.getElementById('success-message').style.display = 'none';
            resetForm();
        });
    }
}

/**
 * Handle GitHub login
 */
function handleGitHubLogin() {
    // For now, we'll use a direct OAuth flow
    // In production, this should go through the add.dctech.events OAuth handler

    if (!CONFIG.clientId) {
        showAuthError('GitHub OAuth is not configured. Please see the documentation for setup instructions.');
        return;
    }

    if (!CONFIG.callbackEndpoint) {
        showAuthError('OAuth callback endpoint is not configured. Please see the documentation for setup instructions.');
        return;
    }

    // Create state object with CSRF token, return URL, and city
    const stateObj = {
        csrf_token: generateRandomState(),
        return_url: window.location.pathname,
        city: getSelectedCity()
    };
    const state = btoa(JSON.stringify(stateObj)); // Base64 encode the state object
    sessionStorage.setItem('oauth_state', stateObj.csrf_token);

    const authUrl = new URL('https://github.com/login/oauth/authorize');
    authUrl.searchParams.set('client_id', CONFIG.clientId);
    authUrl.searchParams.set('redirect_uri', CONFIG.callbackEndpoint);
    authUrl.searchParams.set('scope', CONFIG.scope);
    authUrl.searchParams.set('state', state);

    // Redirect to GitHub OAuth
    window.location.href = authUrl.toString();
}

/**
 * Show authenticated state
 */
function showAuthenticatedState() {
    const authStatus = document.getElementById('auth-status');
    authStatus.className = 'auth-status authenticated';
    authStatus.innerHTML = `
        <p>✓ Signed in as <strong>${userData.login}</strong></p>
        <button id="sign-out" class="btn btn-secondary">Sign Out</button>
    `;

    document.getElementById('sign-out').addEventListener('click', handleSignOut);
    document.getElementById('group-form').style.display = 'block';
    document.getElementById('auth-section').querySelector('p').style.display = 'none';
}

/**
 * Handle sign out
 */
function handleSignOut() {
    sessionStorage.removeItem('github_token');
    octokit = null;
    userData = null;
    window.location.reload();
}

/**
 * Handle form submission
 */
async function handleFormSubmit(e) {
    e.preventDefault();

    if (!octokit || !userData) {
        showError('You must be signed in to submit a group');
        return;
    }

    const submitBtn = document.getElementById('submit-btn');
    const statusMessage = document.getElementById('status-message');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    statusMessage.className = 'status-message info';
    statusMessage.textContent = 'Creating pull request...';
    statusMessage.style.display = 'block';

    try {
        // Collect form data
        const formData = {
            name: document.getElementById('name').value.trim(),
            website: document.getElementById('website').value.trim(),
            ical: document.getElementById('ical').value.trim() || '',
            fallback_url: document.getElementById('fallback_url').value.trim() || ''
        };

        // Validate data
        if (!formData.name || !formData.website) {
            throw new Error('Please fill in all required fields');
        }

        // Create the PR
        const prUrl = await createPullRequest(formData);

        // Show success
        showSuccess(prUrl);

    } catch (error) {
        console.error('Submission error:', error);
        showError(error.message || 'Failed to submit group. Please try again.');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Group';
    }
}

/**
 * Create a pull request with the group data
 */
async function createPullRequest(groupData) {
    // Step 1: Check if user has a fork, create one if needed
    let forkExists = false;
    try {
        // Try to get the existing fork
        await octokit.rest.repos.get({
            owner: userData.login,
            repo: REPO_CONFIG.repo
        });
        forkExists = true;
    } catch (error) {
        if (error.status === 404) {
            // Fork doesn't exist, create it
            const statusMessage = document.getElementById('status-message');
            statusMessage.textContent = 'Creating a fork of the repository...';

            await octokit.rest.repos.createFork({
                owner: REPO_CONFIG.owner,
                repo: REPO_CONFIG.repo
            });

            // Wait for fork to be ready. GitHub's fork creation is async.
            // A more robust solution would poll the fork status, but a 3-second
            // delay is sufficient for most cases and keeps the implementation simple.
            // If the fork isn't ready in 3 seconds (rare), the subsequent branch
            // creation will fail with a clear error that the user can retry.
            statusMessage.textContent = 'Waiting for fork to be ready...';
            await new Promise(resolve => setTimeout(resolve, 3000));

            statusMessage.textContent = 'Creating pull request...';
        } else {
            throw error;
        }
    }

    // Step 2: Get the default branch ref from the upstream repo
    const { data: mainBranch } = await octokit.rest.repos.getBranch({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        branch: REPO_CONFIG.branch
    });

    const mainSha = mainBranch.commit.sha;

    // Step 3: Create a new branch in the user's fork
    const branchName = `group-submission-${Date.now()}`;
    await octokit.rest.git.createRef({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        ref: `refs/heads/${branchName}`,
        sha: mainSha
    });

    // Step 4: Create YAML content
    const yamlContent = generateYAML(groupData);
    const fileName = `${slugify(groupData.name)}.yaml`;
    const filePath = `${REPO_CONFIG.getTargetDir()}/${fileName}`;

    // Step 5: Create file in the new branch of the fork
    await octokit.rest.repos.createOrUpdateFileContents({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        path: filePath,
        message: `Add group: ${groupData.name}`,
        content: btoa(yamlContent), // Base64 encode
        branch: branchName
    });

    // Step 6: Create pull request from fork to upstream
    const { data: pr } = await octokit.rest.pulls.create({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        title: `Add group: ${groupData.name}`,
        head: `${userData.login}:${branchName}`,
        base: REPO_CONFIG.branch,
        body: `## Group Submission

**Name:** ${groupData.name}
**Website:** ${groupData.website}
${groupData.ical ? `**iCal Feed:** ${groupData.ical}\n` : ''}${groupData.fallback_url ? `**Fallback URL:** ${groupData.fallback_url}\n` : ''}
This group was submitted via the web form.`
    });

    return pr.html_url;
}

/**
 * Generate YAML content from group data
 */
function generateYAML(data) {
    let yaml = `name: ${data.name}\n`;
    yaml += `website: ${data.website}\n`;
    if (data.ical) {
        yaml += `ical: ${data.ical}\n`;
    }
    if (data.fallback_url) {
        yaml += `fallback_url: ${data.fallback_url}\n`;
    }
    yaml += `active: true\n`;

    return yaml;
}

/**
 * Convert string to URL-safe slug
 */
function slugify(text) {
    return text
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .substring(0, 50); // Limit length
}

/**
 * Show error message in the auth section (visible area)
 */
function showAuthError(message) {
    const authStatus = document.getElementById('auth-status');

    // Create or update error message element
    let errorDiv = authStatus.querySelector('.auth-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'auth-error';
        authStatus.appendChild(errorDiv);
    }

    errorDiv.textContent = '⚠ ' + message;
    errorDiv.style.display = 'block';
    errorDiv.style.marginTop = 'var(--spacing-md)';
    errorDiv.style.padding = 'var(--spacing-md)';
    errorDiv.style.backgroundColor = '#fef2f2';
    errorDiv.style.border = '1px solid #fca5a5';
    errorDiv.style.borderRadius = 'var(--border-radius)';
    errorDiv.style.color = '#991b1b';
}

/**
 * Show error message
 */
function showError(message) {
    const statusMessage = document.getElementById('status-message');
    statusMessage.className = 'status-message error';
    statusMessage.textContent = '⚠ ' + message;
    statusMessage.style.display = 'block';
}

/**
 * Show success message with PR link
 */
function showSuccess(prUrl) {
    document.getElementById('group-form').style.display = 'none';
    document.getElementById('success-message').style.display = 'block';

    const prLink = document.getElementById('pr-link');
    prLink.href = prUrl;
    prLink.textContent = prUrl;
}

/**
 * Reset form
 */
function resetForm() {
    document.getElementById('group-form').reset();
    document.getElementById('status-message').style.display = 'none';
    document.getElementById('group-form').style.display = 'block';
}

/**
 * Generate random state for OAuth
 */
function generateRandomState() {
    return Math.random().toString(36).substring(2, 15) +
           Math.random().toString(36).substring(2, 15);
}
