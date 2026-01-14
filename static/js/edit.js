// Import Octokit from npm package
import { Octokit } from 'octokit';

// GitHub OAuth Configuration
const CONFIG = {
    clientId: window.GITHUB_CONFIG?.clientId || '',
    redirectUri: window.location.origin + window.location.pathname,
    scope: 'public_repo',
    callbackEndpoint: window.GITHUB_CONFIG?.callbackEndpoint || ''
};

// Repository configuration
const REPO_CONFIG = {
    owner: 'rosskarchner',
    repo: 'dctech.events',
    branch: 'main'
};

// State management
let octokit = null;
let userData = null;

// Get event data passed from Flask template
const EVENT_DATA = window.EVENT_DATA || {};
const CATEGORIES = window.CATEGORIES || {};

// Initialize on page load
function initialize() {
    // Check for dev preview mode (no OAuth required)
    if (window.location.search.includes('dev=true')) {
        showAuthenticatedState(true);
    } else {
        initializeAuth();
    }
    setupEventListeners();
    populateFormFromEventData();
}

// Handle both cases: DOM already loaded or still loading
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

/**
 * Initialize authentication state
 */
function initializeAuth() {
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');
    const error = urlParams.get('error');

    if (error) {
        showAuthError('Authentication failed: ' + error);
        return;
    }

    if (accessToken) {
        sessionStorage.setItem('github_token', accessToken);
        // Remove token from URL but keep hash for event navigation
        const url = new URL(window.location.href);
        url.searchParams.delete('access_token');
        window.history.replaceState({}, document.title, url.toString());
        initializeOctokit(accessToken);
        return;
    }

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
        const { data } = await octokit.rest.users.getAuthenticated();
        userData = data;
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
    const editForm = document.getElementById('edit-form');
    const timingRadios = document.querySelectorAll('input[name="timing"]');

    if (githubLoginBtn) {
        githubLoginBtn.addEventListener('click', handleGitHubLogin);
    }

    if (editForm) {
        editForm.addEventListener('submit', handleFormSubmit);
    }

    timingRadios.forEach(radio => {
        radio.addEventListener('change', handleTimingChange);
    });
}

/**
 * Populate form fields from event data
 */
function populateFormFromEventData() {
    if (!EVENT_DATA || Object.keys(EVENT_DATA).length === 0) {
        return;
    }

    // Parse location into city and state
    if (EVENT_DATA.location) {
        const locationParts = EVENT_DATA.location.split(',').map(s => s.trim());
        if (locationParts.length >= 2) {
            const cityField = document.getElementById('city');
            const stateField = document.getElementById('state');
            if (cityField) cityField.value = locationParts[0];
            if (stateField) {
                const stateValue = locationParts[locationParts.length - 1].toUpperCase();
                // Try to match state abbreviation
                const stateOptions = stateField.options;
                for (let i = 0; i < stateOptions.length; i++) {
                    if (stateOptions[i].value === stateValue || 
                        stateOptions[i].text.toUpperCase().includes(stateValue)) {
                        stateField.value = stateOptions[i].value;
                        break;
                    }
                }
            }
        }
    }

    // Parse time if present (format: HH:MM in 24-hour)
    if (EVENT_DATA.time) {
        const timeParts = EVENT_DATA.time.split(':');
        if (timeParts.length >= 2) {
            let hour = parseInt(timeParts[0], 10);
            const minute = timeParts[1];
            let ampm = 'AM';
            
            if (hour >= 12) {
                ampm = 'PM';
                if (hour > 12) hour -= 12;
            }
            if (hour === 0) hour = 12;

            const hourSelect = document.getElementById('time-hour');
            const minuteSelect = document.getElementById('time-minute');
            const ampmSelect = document.getElementById('time-ampm');
            
            if (hourSelect) hourSelect.value = hour.toString();
            if (minuteSelect) {
                // Round to nearest 15 minutes
                const minInt = parseInt(minute, 10);
                const roundedMin = Math.round(minInt / 15) * 15;
                minuteSelect.value = roundedMin === 60 ? '00' : roundedMin.toString().padStart(2, '0');
            }
            if (ampmSelect) ampmSelect.value = ampm;
        }
    }

    // Enable/disable time selectors based on timing option
    handleTimingChange();
}

/**
 * Handle timing option change
 */
function handleTimingChange() {
    const timingValue = document.querySelector('input[name="timing"]:checked')?.value;
    const timeSelectors = document.querySelectorAll('.time-selector select');
    
    if (timingValue === 'specific') {
        timeSelectors.forEach(select => {
            select.disabled = false;
        });
    } else {
        timeSelectors.forEach(select => {
            select.disabled = true;
        });
    }
}

/**
 * Handle GitHub login
 */
function handleGitHubLogin() {
    if (!CONFIG.clientId) {
        showAuthError('GitHub OAuth is not configured.');
        return;
    }

    if (!CONFIG.callbackEndpoint) {
        showAuthError('OAuth callback endpoint is not configured.');
        return;
    }

    const stateObj = {
        csrf_token: generateRandomState(),
        return_url: window.location.pathname + window.location.hash,
        city: 'dc'
    };
    const state = btoa(JSON.stringify(stateObj));
    sessionStorage.setItem('oauth_state', stateObj.csrf_token);

    const authUrl = new URL('https://github.com/login/oauth/authorize');
    authUrl.searchParams.set('client_id', CONFIG.clientId);
    authUrl.searchParams.set('redirect_uri', CONFIG.callbackEndpoint);
    authUrl.searchParams.set('scope', CONFIG.scope);
    authUrl.searchParams.set('state', state);

    window.location.href = authUrl.toString();
}

/**
 * Show authenticated state
 */
function showAuthenticatedState(devMode = false) {
    const authStatus = document.getElementById('auth-status');
    if (devMode) {
        authStatus.className = 'auth-status authenticated';
        authStatus.innerHTML = `
            <p>✓ Dev Preview Mode (No authentication required)</p>
        `;
        userData = { login: 'dev-user' };
    } else {
        authStatus.className = 'auth-status authenticated';
        authStatus.innerHTML = `
            <p>✓ Signed in as <strong>${userData.login}</strong></p>
            <button id="sign-out" class="btn btn-secondary">Sign Out</button>
        `;
        document.getElementById('sign-out').addEventListener('click', handleSignOut);
    }

    document.getElementById('edit-form').style.display = 'block';
    const authIntro = document.getElementById('auth-section').querySelector('p');
    if (authIntro) authIntro.style.display = 'none';
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

    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    const statusMessage = document.getElementById('status-message');
    statusMessage.style.display = 'none';

    try {
        // Get time value
        const timingValue = document.querySelector('input[name="timing"]:checked')?.value;
        let time24 = '';
        
        if (timingValue === 'specific') {
            const hour = document.getElementById('time-hour').value;
            const minute = document.getElementById('time-minute').value;
            const ampm = document.getElementById('time-ampm').value;
            
            if (hour && minute && ampm) {
                let hour24 = parseInt(hour, 10);
                if (ampm === 'PM' && hour24 !== 12) hour24 += 12;
                if (ampm === 'AM' && hour24 === 12) hour24 = 0;
                time24 = `${hour24.toString().padStart(2, '0')}:${minute}`;
            }
        }

        const city = document.getElementById('city').value.trim();
        const state = document.getElementById('state').value;

        // Get selected categories
        const categoryCheckboxes = document.querySelectorAll('input[name="categories"]:checked');
        const selectedCategories = Array.from(categoryCheckboxes).map(cb => cb.value);

        const formData = {
            title: document.getElementById('title').value.trim(),
            date: document.getElementById('date').value,
            time: time24,
            url: document.getElementById('url').value.trim(),
            location: city && state ? `${city}, ${state}` : '',
            end_date: document.getElementById('end_date').value || '',
            cost: document.getElementById('cost').value.trim() || '',
            description: document.getElementById('description').value.trim() || '',
            categories: selectedCategories,
            edited_by: userData.login
        };

        // Validate required fields
        if (!formData.title || !formData.date || !formData.location) {
            throw new Error('Please fill in all required fields');
        }

        // Create the PR
        const prUrl = await createEditPullRequest(formData);

        // Show success
        showSuccess(prUrl);

    } catch (error) {
        console.error('Submission error:', error);
        showError(error.message || 'Failed to submit changes. Please try again.');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Changes';
    }
}

/**
 * Calculate MD5 hash for event identification
 * Matches the algorithm in generate_month_data.py
 */
function calculateEventHash(date, time, title, url = null) {
    const uidParts = [date, time, title];
    if (url) {
        uidParts.push(url);
    }
    const uidBase = uidParts.join('-');
    return md5(uidBase);
}

/**
 * Simple MD5 implementation for hash calculation
 * Based on RFC 1321
 */
function md5(string) {
    function rotateLeft(value, amount) {
        return (value << amount) | (value >>> (32 - amount));
    }

    function addUnsigned(x, y) {
        const lsw = (x & 0xFFFF) + (y & 0xFFFF);
        const msw = (x >> 16) + (y >> 16) + (lsw >> 16);
        return (msw << 16) | (lsw & 0xFFFF);
    }

    function F(x, y, z) { return (x & y) | ((~x) & z); }
    function G(x, y, z) { return (x & z) | (y & (~z)); }
    function H(x, y, z) { return x ^ y ^ z; }
    function I(x, y, z) { return y ^ (x | (~z)); }

    function FF(a, b, c, d, x, s, ac) {
        a = addUnsigned(a, addUnsigned(addUnsigned(F(b, c, d), x), ac));
        return addUnsigned(rotateLeft(a, s), b);
    }

    function GG(a, b, c, d, x, s, ac) {
        a = addUnsigned(a, addUnsigned(addUnsigned(G(b, c, d), x), ac));
        return addUnsigned(rotateLeft(a, s), b);
    }

    function HH(a, b, c, d, x, s, ac) {
        a = addUnsigned(a, addUnsigned(addUnsigned(H(b, c, d), x), ac));
        return addUnsigned(rotateLeft(a, s), b);
    }

    function II(a, b, c, d, x, s, ac) {
        a = addUnsigned(a, addUnsigned(addUnsigned(I(b, c, d), x), ac));
        return addUnsigned(rotateLeft(a, s), b);
    }

    function utf8Encode(str) {
        let utf8 = '';
        for (let i = 0; i < str.length; i++) {
            let c = str.charCodeAt(i);
            if (c < 128) {
                utf8 += String.fromCharCode(c);
            } else if (c < 2048) {
                utf8 += String.fromCharCode((c >> 6) | 192);
                utf8 += String.fromCharCode((c & 63) | 128);
            } else {
                utf8 += String.fromCharCode((c >> 12) | 224);
                utf8 += String.fromCharCode(((c >> 6) & 63) | 128);
                utf8 += String.fromCharCode((c & 63) | 128);
            }
        }
        return utf8;
    }

    const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    const K = [
        0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a,
        0xa8304613, 0xfd469501, 0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
        0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821, 0xf61e2562, 0xc040b340,
        0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
        0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8,
        0x676f02d9, 0x8d2a4c8a, 0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
        0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70, 0x289b7ec6, 0xeaa127fa,
        0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
        0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92,
        0xffeff47d, 0x85845dd1, 0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
        0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391
    ];

    string = utf8Encode(string);

    let words = [];
    for (let i = 0; i < string.length * 8; i += 8) {
        words[i >> 5] |= (string.charCodeAt(i / 8) & 0xff) << (i % 32);
    }

    const len = string.length * 8;
    words[len >> 5] |= 0x80 << (len % 32);
    words[(((len + 64) >>> 9) << 4) + 14] = len;

    let a = 0x67452301;
    let b = 0xefcdab89;
    let c = 0x98badcfe;
    let d = 0x10325476;

    for (let i = 0; i < words.length; i += 16) {
        const aa = a, bb = b, cc = c, dd = d;

        a = FF(a, b, c, d, words[i + 0] || 0, S[0], K[0]);
        d = FF(d, a, b, c, words[i + 1] || 0, S[1], K[1]);
        c = FF(c, d, a, b, words[i + 2] || 0, S[2], K[2]);
        b = FF(b, c, d, a, words[i + 3] || 0, S[3], K[3]);
        a = FF(a, b, c, d, words[i + 4] || 0, S[0], K[4]);
        d = FF(d, a, b, c, words[i + 5] || 0, S[1], K[5]);
        c = FF(c, d, a, b, words[i + 6] || 0, S[2], K[6]);
        b = FF(b, c, d, a, words[i + 7] || 0, S[3], K[7]);
        a = FF(a, b, c, d, words[i + 8] || 0, S[0], K[8]);
        d = FF(d, a, b, c, words[i + 9] || 0, S[1], K[9]);
        c = FF(c, d, a, b, words[i + 10] || 0, S[2], K[10]);
        b = FF(b, c, d, a, words[i + 11] || 0, S[3], K[11]);
        a = FF(a, b, c, d, words[i + 12] || 0, S[0], K[12]);
        d = FF(d, a, b, c, words[i + 13] || 0, S[1], K[13]);
        c = FF(c, d, a, b, words[i + 14] || 0, S[2], K[14]);
        b = FF(b, c, d, a, words[i + 15] || 0, S[3], K[15]);

        a = GG(a, b, c, d, words[i + 1] || 0, S[4], K[16]);
        d = GG(d, a, b, c, words[i + 6] || 0, S[5], K[17]);
        c = GG(c, d, a, b, words[i + 11] || 0, S[6], K[18]);
        b = GG(b, c, d, a, words[i + 0] || 0, S[7], K[19]);
        a = GG(a, b, c, d, words[i + 5] || 0, S[4], K[20]);
        d = GG(d, a, b, c, words[i + 10] || 0, S[5], K[21]);
        c = GG(c, d, a, b, words[i + 15] || 0, S[6], K[22]);
        b = GG(b, c, d, a, words[i + 4] || 0, S[7], K[23]);
        a = GG(a, b, c, d, words[i + 9] || 0, S[4], K[24]);
        d = GG(d, a, b, c, words[i + 14] || 0, S[5], K[25]);
        c = GG(c, d, a, b, words[i + 3] || 0, S[6], K[26]);
        b = GG(b, c, d, a, words[i + 8] || 0, S[7], K[27]);
        a = GG(a, b, c, d, words[i + 13] || 0, S[4], K[28]);
        d = GG(d, a, b, c, words[i + 2] || 0, S[5], K[29]);
        c = GG(c, d, a, b, words[i + 7] || 0, S[6], K[30]);
        b = GG(b, c, d, a, words[i + 12] || 0, S[7], K[31]);

        a = HH(a, b, c, d, words[i + 5] || 0, S[8], K[32]);
        d = HH(d, a, b, c, words[i + 8] || 0, S[9], K[33]);
        c = HH(c, d, a, b, words[i + 11] || 0, S[10], K[34]);
        b = HH(b, c, d, a, words[i + 14] || 0, S[11], K[35]);
        a = HH(a, b, c, d, words[i + 1] || 0, S[8], K[36]);
        d = HH(d, a, b, c, words[i + 4] || 0, S[9], K[37]);
        c = HH(c, d, a, b, words[i + 7] || 0, S[10], K[38]);
        b = HH(b, c, d, a, words[i + 10] || 0, S[11], K[39]);
        a = HH(a, b, c, d, words[i + 13] || 0, S[8], K[40]);
        d = HH(d, a, b, c, words[i + 0] || 0, S[9], K[41]);
        c = HH(c, d, a, b, words[i + 3] || 0, S[10], K[42]);
        b = HH(b, c, d, a, words[i + 6] || 0, S[11], K[43]);
        a = HH(a, b, c, d, words[i + 9] || 0, S[8], K[44]);
        d = HH(d, a, b, c, words[i + 12] || 0, S[9], K[45]);
        c = HH(c, d, a, b, words[i + 15] || 0, S[10], K[46]);
        b = HH(b, c, d, a, words[i + 2] || 0, S[11], K[47]);

        a = II(a, b, c, d, words[i + 0] || 0, S[12], K[48]);
        d = II(d, a, b, c, words[i + 7] || 0, S[13], K[49]);
        c = II(c, d, a, b, words[i + 14] || 0, S[14], K[50]);
        b = II(b, c, d, a, words[i + 5] || 0, S[15], K[51]);
        a = II(a, b, c, d, words[i + 12] || 0, S[12], K[52]);
        d = II(d, a, b, c, words[i + 3] || 0, S[13], K[53]);
        c = II(c, d, a, b, words[i + 10] || 0, S[14], K[54]);
        b = II(b, c, d, a, words[i + 1] || 0, S[15], K[55]);
        a = II(a, b, c, d, words[i + 8] || 0, S[12], K[56]);
        d = II(d, a, b, c, words[i + 15] || 0, S[13], K[57]);
        c = II(c, d, a, b, words[i + 6] || 0, S[14], K[58]);
        b = II(b, c, d, a, words[i + 13] || 0, S[15], K[59]);
        a = II(a, b, c, d, words[i + 4] || 0, S[12], K[60]);
        d = II(d, a, b, c, words[i + 11] || 0, S[13], K[61]);
        c = II(c, d, a, b, words[i + 2] || 0, S[14], K[62]);
        b = II(b, c, d, a, words[i + 9] || 0, S[15], K[63]);

        a = addUnsigned(a, aa);
        b = addUnsigned(b, bb);
        c = addUnsigned(c, cc);
        d = addUnsigned(d, dd);
    }

    const hex = (n) => {
        let s = '';
        for (let i = 0; i < 4; i++) {
            s += ((n >> (i * 8 + 4)) & 0xf).toString(16) + ((n >> (i * 8)) & 0xf).toString(16);
        }
        return s;
    };

    return hex(a) + hex(b) + hex(c) + hex(d);
}

/**
 * Generate a diff description of changes for PR body
 */
function generateDiffDescription(originalEvent, formData) {
    const changes = [];
    
    const fields = [
        { key: 'title', label: 'Title' },
        { key: 'date', label: 'Date' },
        { key: 'time', label: 'Time' },
        { key: 'url', label: 'URL' },
        { key: 'location', label: 'Location' },
        { key: 'end_date', label: 'End Date' },
        { key: 'cost', label: 'Cost' },
        { key: 'description', label: 'Description' }
    ];
    
    for (const field of fields) {
        const original = originalEvent[field.key] || '';
        const updated = formData[field.key] || '';
        if (original !== updated) {
            changes.push(`- **${field.label}:** \`${original || '(empty)'}\` → \`${updated || '(empty)'}\``);
        }
    }
    
    // Handle categories specially
    const originalCats = (originalEvent.categories || []).sort();
    const updatedCats = (formData.categories || []).sort();
    if (JSON.stringify(originalCats) !== JSON.stringify(updatedCats)) {
        changes.push(`- **Categories:** \`${originalCats.join(', ') || '(none)'}\` → \`${updatedCats.join(', ') || '(none)'}\``);
    }
    
    return changes.length > 0 ? changes.join('\n') : 'No changes detected';
}

/**
 * Create a pull request with the event edit
 */
async function createEditPullRequest(formData) {
    const statusMessage = document.getElementById('status-message');
    
    // Step 1: Check if user has a fork, create one if needed
    try {
        await octokit.rest.repos.get({
            owner: userData.login,
            repo: REPO_CONFIG.repo
        });
    } catch (error) {
        if (error.status === 404) {
            statusMessage.textContent = 'Creating a fork of the repository...';
            statusMessage.className = 'status-message info';
            statusMessage.style.display = 'block';
            
            await octokit.rest.repos.createFork({
                owner: REPO_CONFIG.owner,
                repo: REPO_CONFIG.repo
            });
            
            statusMessage.textContent = 'Waiting for fork to be ready...';
            await new Promise(resolve => setTimeout(resolve, 3000));
        } else {
            throw error;
        }
    }

    statusMessage.textContent = 'Creating pull request...';
    statusMessage.className = 'status-message info';
    statusMessage.style.display = 'block';

    // Step 2: Get the default branch ref from the upstream repo
    const { data: mainBranch } = await octokit.rest.repos.getBranch({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        branch: REPO_CONFIG.branch
    });

    const mainSha = mainBranch.commit.sha;

    // Step 3: Determine file path based on event source
    let filePath;
    let fileName;
    
    if (EVENT_DATA.source === 'manual' && EVENT_DATA.slug) {
        // Manual event - update the existing file in _single_events
        fileName = `${EVENT_DATA.slug}.yaml`;
        filePath = `_single_events/${fileName}`;
    } else {
        // iCal event - create override file
        // Use the guid if available, otherwise calculate hash
        const eventHash = EVENT_DATA.guid || calculateEventHash(
            EVENT_DATA.date,
            EVENT_DATA.time || '',
            EVENT_DATA.title,
            EVENT_DATA.url
        );
        fileName = `${eventHash}.yaml`;
        filePath = `_event_overrides/${fileName}`;
    }

    // Step 4: Create a new branch in the user's fork
    const branchName = `edit-event-${Date.now()}`;
    await octokit.rest.git.createRef({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        ref: `refs/heads/${branchName}`,
        sha: mainSha
    });

    // Step 5: Generate YAML content
    const yamlContent = generateEditYAML(formData, EVENT_DATA);

    // Step 6: Check if file exists (for updates) and get its SHA
    let existingSha = null;
    try {
        const { data: existingFile } = await octokit.rest.repos.getContent({
            owner: userData.login,
            repo: REPO_CONFIG.repo,
            path: filePath,
            ref: branchName
        });
        existingSha = existingFile.sha;
    } catch (error) {
        // File doesn't exist, that's fine for override files
        if (error.status !== 404) {
            throw error;
        }
    }

    // Step 7: Create or update file in the new branch
    const commitOptions = {
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        path: filePath,
        message: `Edit event: ${formData.title}`,
        content: btoa(unescape(encodeURIComponent(yamlContent))), // Handle UTF-8
        branch: branchName
    };
    
    if (existingSha) {
        commitOptions.sha = existingSha;
    }
    
    await octokit.rest.repos.createOrUpdateFileContents(commitOptions);

    // Step 8: Generate diff description
    const diffDescription = generateDiffDescription(EVENT_DATA, formData);

    // Step 9: Create pull request from fork to upstream
    const { data: pr } = await octokit.rest.pulls.create({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        title: `Edit event: ${formData.title}`,
        head: `${userData.login}:${branchName}`,
        base: REPO_CONFIG.branch,
        body: `## Event Edit

**Original Event:** ${EVENT_DATA.title}
**Source:** ${EVENT_DATA.source || 'unknown'}

### Changes
${diffDescription}

---
This edit was submitted via the web form by @${formData.edited_by}.`
    });

    return pr.html_url;
}

/**
 * Generate YAML content for event edit
 */
function generateEditYAML(formData, originalEvent) {
    let yaml = `title: "${formData.title.replace(/"/g, '\\"')}"\n`;
    yaml += `date: '${formData.date}'\n`;
    
    if (formData.time) {
        yaml += `time: '${formData.time}'\n`;
    }
    
    if (formData.url) {
        yaml += `url: ${formData.url}\n`;
    }
    
    if (formData.location) {
        yaml += `location: ${formData.location}\n`;
    }
    
    if (formData.end_date) {
        yaml += `end_date: '${formData.end_date}'\n`;
    }
    
    if (formData.cost) {
        yaml += `cost: '${formData.cost}'\n`;
    }
    
    if (formData.description) {
        // Multi-line description
        yaml += `description: |\n  ${formData.description.replace(/\n/g, '\n  ')}\n`;
    }
    
    if (formData.categories && formData.categories.length > 0) {
        yaml += `categories:\n`;
        for (const cat of formData.categories) {
            yaml += `  - ${cat}\n`;
        }
    }
    
    // Preserve group from original event if present
    if (originalEvent.group) {
        yaml += `group: "${originalEvent.group.replace(/"/g, '\\"')}"\n`;
    }
    
    yaml += `edited_by: ${formData.edited_by}\n`;

    return yaml;
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
 * Show error in auth section
 */
function showAuthError(message) {
    const authStatus = document.getElementById('auth-status');
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
 * Show success message with PR link
 */
function showSuccess(prUrl) {
    document.getElementById('edit-form').style.display = 'none';
    document.getElementById('success-message').style.display = 'block';

    const prLink = document.getElementById('pr-link');
    prLink.href = prUrl;
    prLink.textContent = prUrl;
}

/**
 * Generate random state for OAuth
 */
function generateRandomState() {
    return Math.random().toString(36).substring(2, 15) +
           Math.random().toString(36).substring(2, 15);
}
