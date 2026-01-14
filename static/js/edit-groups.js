import { Octokit } from 'octokit';
import {
    REPO_CONFIG,
    ensureFork,
    createBranch,
    createOrUpdateFile,
    createPullRequest
} from './github-utils.js';

let octokit = null;
let userData = null;
let groupsData = [];
const selectedGroups = new Set();

// GitHub OAuth Configuration
const CONFIG = {
    clientId: window.GITHUB_CONFIG?.clientId || '',
    callbackEndpoint: window.GITHUB_CONFIG?.callbackEndpoint || ''
};

// Initialize
init();

async function init() {
    setupAuthHandlers();
    await checkAuthStatus();
}

/**
 * Check authentication status on page load
 */
async function checkAuthStatus() {
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access_token');

    if (accessToken) {
        sessionStorage.setItem('github_token', accessToken);
        window.history.replaceState({}, document.title, window.location.pathname);
        await initializeOctokit(accessToken);
        return;
    }

    const storedToken = sessionStorage.getItem('github_token');
    if (storedToken) {
        await initializeOctokit(storedToken);
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
        console.log('Authenticated as:', userData.login);
        showAuthenticatedState();
        await loadGroups();
    } catch (error) {
        console.error('Authentication error:', error);
        sessionStorage.removeItem('github_token');
    }
}

/**
 * Show authenticated state UI
 */
function showAuthenticatedState() {
    const authStatus = document.getElementById('auth-status');
    const groupsContent = document.getElementById('groups-content');
    const authSectionP = document.querySelector('#auth-section > p');

    authStatus.className = 'auth-status authenticated';
    authStatus.innerHTML = `
        <p>✓ Signed in as <strong>${userData.login}</strong></p>
        <button id="sign-out" class="btn btn-secondary">Sign Out</button>
    `;
    document.getElementById('sign-out').addEventListener('click', handleSignOut);

    if (authSectionP) {
        authSectionP.style.display = 'none';
    }
    groupsContent.style.display = 'block';
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
 * Setup auth button handlers
 */
function setupAuthHandlers() {
    const githubLoginBtn = document.getElementById('github-login');
    if (githubLoginBtn) {
        githubLoginBtn.addEventListener('click', handleGitHubLogin);
    }
}

/**
 * Handle GitHub login
 */
function handleGitHubLogin() {
    if (!CONFIG.clientId || !CONFIG.callbackEndpoint) {
        alert('GitHub OAuth is not configured.');
        return;
    }

    const stateObj = {
        csrf_token: crypto.randomUUID(),
        return_url: '/groups/edit/',
        city: 'dc'
    };
    const state = btoa(JSON.stringify(stateObj));
    sessionStorage.setItem('oauth_state', stateObj.csrf_token);

    const authUrl = new URL('https://github.com/login/oauth/authorize');
    authUrl.searchParams.set('client_id', CONFIG.clientId);
    authUrl.searchParams.set('redirect_uri', CONFIG.callbackEndpoint);
    authUrl.searchParams.set('scope', 'public_repo');
    authUrl.searchParams.set('state', state);

    window.location.href = authUrl.toString();
}

/**
 * Load groups from API
 */
async function loadGroups() {
    try {
        const response = await fetch('/groups.json');
        if (!response.ok) {
            throw new Error('Failed to load groups');
        }
        groupsData = await response.json();
        renderGroupsList();
    } catch (error) {
        console.error('Error loading groups:', error);
        alert('Failed to load groups: ' + error.message);
    }
}

/**
 * Render groups list
 */
function renderGroupsList() {
    const container = document.getElementById('groups-list');
    container.innerHTML = '';

    if (groupsData.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 2rem;">No groups found.</p>';
        return;
    }

    for (const group of groupsData) {
        const row = document.createElement('div');
        row.className = 'group-row';
        row.dataset.groupId = group.id;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'group-checkbox';
        checkbox.dataset.groupId = group.id;
        checkbox.addEventListener('change', handleCheckboxChange);

        const checkboxContainer = document.createElement('div');
        checkboxContainer.className = 'group-checkbox';
        checkboxContainer.appendChild(checkbox);

        const details = document.createElement('div');
        details.className = 'group-details';

        const name = document.createElement('div');
        name.className = 'group-name';
        name.textContent = group.name;

        const meta = document.createElement('div');
        meta.className = 'group-meta';

        const websiteSpan = document.createElement('span');
        websiteSpan.className = 'group-website';
        websiteSpan.textContent = group.website;
        meta.appendChild(websiteSpan);

        if (group.categories && group.categories.length > 0) {
            const categoriesSpan = document.createElement('span');
            categoriesSpan.className = 'current-categories';
            categoriesSpan.textContent = `Categories: ${group.categories.join(', ')}`;
            meta.appendChild(categoriesSpan);
        }

        details.appendChild(name);
        details.appendChild(meta);

        const actions = document.createElement('div');
        actions.className = 'group-actions';
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-primary';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => openEditModal(group));
        actions.appendChild(editBtn);

        row.appendChild(checkboxContainer);
        row.appendChild(details);
        row.appendChild(actions);

        container.appendChild(row);
    }
}

/**
 * Handle checkbox change
 */
function handleCheckboxChange(e) {
    const groupId = e.target.dataset.groupId;
    const row = e.target.closest('.group-row');

    if (e.target.checked) {
        selectedGroups.add(groupId);
        row.classList.add('selected');
    } else {
        selectedGroups.delete(groupId);
        row.classList.remove('selected');
    }

    updateControls();
}

/**
 * Update control visibility
 */
function updateControls() {
    const controls = document.getElementById('category-controls');
    const count = selectedGroups.size;

    controls.style.display = count > 0 ? 'flex' : 'none';
    document.getElementById('selected-count').textContent =
        `${count} group${count !== 1 ? 's' : ''} selected`;
}

/**
 * Apply category to selected groups
 */
async function applyCategoryToGroups() {
    const category = document.getElementById('category-select').value;
    const groupIds = Array.from(selectedGroups);

    if (!category) {
        alert('Please select a category');
        return;
    }

    if (groupIds.length === 0) {
        alert('Please select at least one group');
        return;
    }

    showStatus('Creating fork...');

    try {
        await ensureFork(octokit, userData);

        showStatus('Creating branch...');
        const branchName = `categorize-groups-${Date.now()}`;
        await createBranch(octokit, userData, branchName);

        showStatus('Updating group files...');
        const updatedGroups = [];

        for (const groupId of groupIds) {
            const group = groupsData.find(g => g.id === groupId);
            const filePath = `_groups/${groupId}.yaml`;

            // Fetch existing file content
            const { data: file } = await octokit.rest.repos.getContent({
                owner: REPO_CONFIG.owner,
                repo: REPO_CONFIG.repo,
                path: filePath,
                ref: REPO_CONFIG.branch
            });

            const existingContent = atob(file.content);
            const updatedContent = updateGroupYAMLWithCategories(existingContent, [category]);

            await createOrUpdateFile(
                octokit, userData, branchName, filePath, updatedContent,
                `Add ${category} category to ${group.name}`
            );

            updatedGroups.push(group.name);
        }

        showStatus('Creating pull request...');
        const prBody = `## Bulk Group Categorization\n\nAssigned category **${category}** to ${updatedGroups.length} group(s):\n\n${updatedGroups.map(n => `- ${n}`).join('\n')}\n\n---\nSubmitted via web interface by @${userData.login}`;

        const prUrl = await createPullRequest(
            octokit, userData, branchName,
            `Assign ${category} category to ${updatedGroups.length} groups`,
            prBody
        );

        showSuccess(prUrl);
        clearState();
    } catch (error) {
        showError(error.message);
    }
}

/**
 * Update group YAML with categories (bulk)
 */
function updateGroupYAMLWithCategories(existingYAML, newCategories) {
    const lines = existingYAML.split('\n');
    const result = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.match(/^categories:/)) {
            // Skip existing categories
            while (i + 1 < lines.length && lines[i + 1].match(/^  -/)) {
                i++;
            }
            continue;
        }

        result.push(line);
    }

    // Remove trailing empty lines
    while (result.length > 0 && result[result.length - 1].trim() === '') {
        result.pop();
    }

    // Add categories
    result.push('categories:');
    for (const cat of newCategories) {
        result.push(`  - ${cat}`);
    }
    result.push('');

    return result.join('\n');
}

/**
 * Open edit modal for individual group
 */
function openEditModal(group) {
    document.getElementById('edit-group-id').value = group.id;
    document.getElementById('edit-name').value = group.name;
    document.getElementById('edit-website').value = group.website || '';
    document.getElementById('edit-ical').value = group.ical || '';
    document.getElementById('edit-fallback-url').value = group.fallback_url || '';
    document.getElementById('edit-active').checked = group.active !== false;

    // Set categories multi-select
    const categoriesSelect = document.getElementById('edit-categories');
    Array.from(categoriesSelect.options).forEach(option => {
        option.selected = group.categories && group.categories.includes(option.value);
    });

    document.getElementById('edit-modal').classList.add('active');
}

/**
 * Close edit modal
 */
function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
    document.getElementById('edit-group-form').reset();
}

/**
 * Save individual group edit
 */
async function saveIndividualEdit(e) {
    e.preventDefault();

    const groupId = document.getElementById('edit-group-id').value;
    const group = groupsData.find(g => g.id === groupId);

    const updatedData = {
        name: document.getElementById('edit-name').value,
        website: document.getElementById('edit-website').value,
        ical: document.getElementById('edit-ical').value,
        fallback_url: document.getElementById('edit-fallback-url').value,
        active: document.getElementById('edit-active').checked,
        categories: Array.from(document.getElementById('edit-categories').selectedOptions)
            .map(opt => opt.value)
    };

    closeEditModal();
    showStatus('Creating fork...');

    try {
        await ensureFork(octokit, userData);

        showStatus('Creating branch...');
        const branchName = `edit-group-${groupId}-${Date.now()}`;
        await createBranch(octokit, userData, branchName);

        showStatus('Updating group file...');

        // Fetch existing file to get all fields
        const { data: file } = await octokit.rest.repos.getContent({
            owner: REPO_CONFIG.owner,
            repo: REPO_CONFIG.repo,
            path: `_groups/${groupId}.yaml`,
            ref: REPO_CONFIG.branch
        });

        const existingContent = atob(file.content);
        const updatedYAML = updateGroupYAMLWithAllFields(existingContent, updatedData);

        await createOrUpdateFile(
            octokit, userData, branchName, `_groups/${groupId}.yaml`, updatedYAML,
            `Update ${updatedData.name} group details`
        );

        showStatus('Creating pull request...');
        const prBody = `## Edit Group: ${updatedData.name}\n\nUpdated group details via web interface.\n\n---\nSubmitted by @${userData.login}`;

        const prUrl = await createPullRequest(
            octokit, userData, branchName,
            `Edit group: ${updatedData.name}`,
            prBody
        );

        showSuccess(prUrl);
        await loadGroups(); // Refresh list
    } catch (error) {
        showError(error.message);
    }
}

/**
 * Update group YAML with all fields (individual edit)
 */
function updateGroupYAMLWithAllFields(existingYAML, updatedData) {
    // Build new YAML with all fields
    let yaml = `name: ${updatedData.name}\n`;
    yaml += `website: ${updatedData.website}\n`;

    if (updatedData.ical) {
        yaml += `ical: ${updatedData.ical}\n`;
    }

    if (updatedData.fallback_url) {
        yaml += `fallback_url: ${updatedData.fallback_url}\n`;
    }

    yaml += `active: ${updatedData.active}\n`;

    if (updatedData.categories && updatedData.categories.length > 0) {
        yaml += 'categories:\n';
        for (const cat of updatedData.categories) {
            yaml += `  - ${cat}\n`;
        }
    }

    // Preserve fields we don't edit (submitted_by, submitter_link, suppress_urls)
    const existingLines = existingYAML.split('\n');
    for (const line of existingLines) {
        if (line.match(/^submitted_by:/)) {
            yaml += line + '\n';
        } else if (line.match(/^submitter_link:/)) {
            yaml += line + '\n';
        } else if (line.match(/^suppress_urls:/)) {
            // Copy suppress_urls and all its items
            yaml += line + '\n';
            const idx = existingLines.indexOf(line);
            for (let i = idx + 1; i < existingLines.length; i++) {
                if (existingLines[i].match(/^  -/)) {
                    yaml += existingLines[i] + '\n';
                } else {
                    break;
                }
            }
        }
    }

    return yaml;
}

/**
 * Show status overlay
 */
function showStatus(message) {
    document.getElementById('status-message').textContent = message;
    document.getElementById('status-overlay').style.display = 'flex';
}

/**
 * Show success message
 */
function showSuccess(prUrl) {
    alert(`Pull request created successfully!\n\nView at: ${prUrl}`);
    document.getElementById('status-overlay').style.display = 'none';
    window.open(prUrl, '_blank');
}

/**
 * Show error message
 */
function showError(message) {
    alert(`Error: ${message}`);
    document.getElementById('status-overlay').style.display = 'none';
}

/**
 * Clear bulk selection state
 */
function clearState() {
    selectedGroups.clear();
    document.querySelectorAll('.group-checkbox:checked').forEach(cb => {
        cb.checked = false;
        cb.closest('.group-row').classList.remove('selected');
    });
    document.getElementById('category-select').value = '';
    updateControls();
}

// Setup event listeners
document.getElementById('apply-category-button')?.addEventListener('click', applyCategoryToGroups);
document.getElementById('select-all')?.addEventListener('click', () => {
    document.querySelectorAll('.group-checkbox input').forEach(cb => {
        cb.checked = true;
        cb.dispatchEvent(new Event('change'));
    });
});
document.getElementById('clear-selection')?.addEventListener('click', clearState);

// Modal event listeners
document.getElementById('edit-group-form')?.addEventListener('submit', saveIndividualEdit);
document.getElementById('modal-close')?.addEventListener('click', closeEditModal);
document.getElementById('cancel-edit')?.addEventListener('click', closeEditModal);

// Close modal on background click
document.getElementById('edit-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'edit-modal') {
        closeEditModal();
    }
});
