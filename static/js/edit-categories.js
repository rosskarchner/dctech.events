import { Octokit } from 'octokit';
import {
    REPO_CONFIG,
    ensureFork,
    createBranch,
    createOrUpdateFile,
    deleteFile,
    createPullRequest
} from './github-utils.js';
import {
    showError,
    showSuccess,
    showStatus,
    showOverlay,
    hideOverlay
} from './notifications.js';

let octokit = null;
let userData = null;
let categoriesData = [];

// GitHub OAuth Configuration
const CONFIG = {
    clientId: window.GITHUB_CONFIG?.clientId || '',
    callbackEndpoint: window.GITHUB_CONFIG?.callbackEndpoint || ''
};

// Initialize
init();

async function init() {
    setupAuthHandlers();
    setupModalHandlers();
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
        await loadCategories();
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
    const categoriesContent = document.getElementById('categories-content');
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
    categoriesContent.style.display = 'block';
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
        showError('GitHub OAuth is not configured.');
        return;
    }

    const stateObj = {
        csrf_token: crypto.randomUUID(),
        return_url: '/categories/edit/',
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
 * Load categories from API
 */
async function loadCategories() {
    try {
        const response = await fetch('/categories.json');
        if (!response.ok) {
            throw new Error('Failed to load categories');
        }
        categoriesData = await response.json();
        renderCategoriesList();
    } catch (error) {
        console.error('Error loading categories:', error);
        showError('Failed to load categories: ' + error.message);
    }
}

/**
 * Render categories list
 */
function renderCategoriesList() {
    const container = document.getElementById('categories-list');
    container.innerHTML = '';

    if (categoriesData.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #6b7280; padding: 2rem;">No categories found.</p>';
        return;
    }

    for (const category of categoriesData) {
        const row = document.createElement('div');
        row.className = 'category-row';
        row.dataset.categorySlug = category.slug;

        const details = document.createElement('div');
        details.className = 'category-details';

        const header = document.createElement('div');
        header.className = 'category-header';

        const name = document.createElement('div');
        name.className = 'category-name';
        name.textContent = category.name;

        const slugBadge = document.createElement('span');
        slugBadge.className = 'category-slug';
        slugBadge.textContent = category.slug;

        header.appendChild(name);
        header.appendChild(slugBadge);

        const description = document.createElement('div');
        description.className = 'category-description';
        description.textContent = category.description || '';

        details.appendChild(header);
        details.appendChild(description);

        const actions = document.createElement('div');
        actions.className = 'category-actions';

        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-primary';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => openEditModal(category.slug));
        actions.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-sm btn-danger';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', () => openDeleteModal(category.slug));
        actions.appendChild(deleteBtn);

        row.appendChild(details);
        row.appendChild(actions);

        container.appendChild(row);
    }
}

/**
 * Slugify text - convert name to slug (lowercase, hyphenated)
 */
function slugify(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '') // Remove non-word chars except spaces and hyphens
        .replace(/[\s_]+/g, '-')   // Replace spaces and underscores with hyphens
        .replace(/^-+|-+$/g, '');  // Remove leading/trailing hyphens
}

/**
 * Open create modal
 */
function openCreateModal() {
    document.getElementById('modal-title').textContent = 'Create New Category';
    document.getElementById('modal-mode').value = 'create';
    document.getElementById('edit-category-slug').value = '';
    document.getElementById('edit-name').value = '';
    document.getElementById('edit-slug').value = '';
    document.getElementById('edit-description').value = '';
    document.getElementById('save-button').textContent = 'Create Category';

    // Show slug input and preview, hide slug display
    document.getElementById('slug-display-group').style.display = 'none';
    document.getElementById('slug-input-group').style.display = 'block';
    document.getElementById('slug-preview-group').style.display = 'block';

    // Update slug preview as user types in name field
    const nameInput = document.getElementById('edit-name');
    const slugInput = document.getElementById('edit-slug');
    
    const updateSlugPreview = () => {
        // If slug input is empty, show auto-generated preview
        if (!slugInput.value.trim()) {
            const slug = slugify(nameInput.value);
            document.getElementById('slug-preview').textContent = slug || '(empty)';
        }
    };
    
    nameInput.removeEventListener('input', updateSlugPreview);
    nameInput.addEventListener('input', updateSlugPreview);
    updateSlugPreview();

    document.getElementById('edit-modal').classList.add('active');
}

/**
 * Open edit modal with existing data (slug read-only)
 */
function openEditModal(slug) {
    const category = categoriesData.find(c => c.slug === slug);
    if (!category) {
        showError('Category not found');
        return;
    }

    document.getElementById('modal-title').textContent = 'Edit Category';
    document.getElementById('modal-mode').value = 'edit';
    document.getElementById('edit-category-slug').value = category.slug;
    document.getElementById('edit-name').value = category.name;
    document.getElementById('edit-description').value = category.description || '';
    document.getElementById('save-button').textContent = 'Save Changes';

    // Show slug display (read-only), hide slug preview
    document.getElementById('slug-display-group').style.display = 'block';
    document.getElementById('slug-preview-group').style.display = 'none';
    document.getElementById('slug-display').textContent = category.slug;

    document.getElementById('edit-modal').classList.add('active');
}

/**
 * Close edit/create modal
 */
function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
    document.getElementById('edit-category-form').reset();
}

/**
 * Save category (create or edit)
 */
async function saveCategoryForm(e) {
    e.preventDefault();

    const mode = document.getElementById('modal-mode').value;
    const name = document.getElementById('edit-name').value.trim();
    const description = document.getElementById('edit-description').value.trim();

    if (!name) {
        showError('Category name is required');
        return;
    }

    if (mode === 'create') {
        let slug = document.getElementById('edit-slug').value.trim();
        
        // If slug is empty, auto-generate from name
        if (!slug) {
            slug = slugify(name);
        } else {
            // Validate custom slug
            slug = slug.toLowerCase().replace(/[^\w-]/g, '').replace(/[\s_]+/g, '-');
            if (!slug) {
                showError('Invalid slug - must contain at least one alphanumeric character');
                return;
            }
        }
        
        await createCategory(name, description, slug);
    } else {
        const slug = document.getElementById('edit-category-slug').value;
        await editCategory(slug, name, description);
    }
}

/**
 * Create new category
 */
async function createCategory(name, description, slug) {
    if (!slug) {
        slug = slugify(name);
    }

    if (!slug) {
        showError('Invalid category name - cannot generate slug');
        return;
    }

    // Check for duplicate slug
    if (categoriesData.some(c => c.slug === slug)) {
        showError(`Category with slug "${slug}" already exists`);
        return;
    }

    closeEditModal();
    showOverlay('Creating fork...');

    try {
        await ensureFork(octokit, userData);

        showOverlay('Creating branch...');
        const branchName = `create-category-${slug}-${Date.now()}`;
        await createBranch(octokit, userData, branchName);

        showOverlay('Creating category file...');
        const filePath = `_categories/${slug}.yaml`;
        const yamlContent = generateCategoryYAML(name, description);

        await createOrUpdateFile(
            octokit, userData, branchName, filePath, yamlContent,
            `Create category: ${name}`
        );

        showOverlay('Creating pull request...');
        const prBody = `## Create Category: ${name}\n\nSlug: \`${slug}\`\n\n${description ? `Description: ${description}\n\n` : ''}---\nSubmitted via web interface by @${userData.login}`;

        const prUrl = await createPullRequest(
            octokit, userData, branchName,
            `Create category: ${name}`,
            prBody
        );

        hideOverlay();
        showSuccess(prUrl);
    } catch (error) {
        console.error('Error creating category:', error);
        hideOverlay();
        showError(error.message);
    }
}

/**
 * Edit existing category (name and description only, slug read-only)
 */
async function editCategory(slug, newName, newDescription) {
    closeEditModal();
    showOverlay('Creating fork...');

    try {
        await ensureFork(octokit, userData);

        showOverlay('Creating branch...');
        const branchName = `edit-category-${slug}-${Date.now()}`;
        await createBranch(octokit, userData, branchName);

        showOverlay('Updating category file...');
        const filePath = `_categories/${slug}.yaml`;
        const yamlContent = generateCategoryYAML(newName, newDescription);

        await createOrUpdateFile(
            octokit, userData, branchName, filePath, yamlContent,
            `Update category: ${newName}`
        );

        showOverlay('Creating pull request...');
        const prBody = `## Edit Category: ${newName}\n\nSlug: \`${slug}\` (unchanged)\n\nUpdated name and/or description.\n\n---\nSubmitted via web interface by @${userData.login}`;

        const prUrl = await createPullRequest(
            octokit, userData, branchName,
            `Edit category: ${newName}`,
            prBody
        );

        hideOverlay();
        showSuccess(prUrl);
    } catch (error) {
        console.error('Error editing category:', error);
        hideOverlay();
        showError(error.message);
    }
}

/**
 * Open delete confirmation modal
 */
async function openDeleteModal(slug) {
    const category = categoriesData.find(c => c.slug === slug);
    if (!category) {
        showError('Category not found');
        return;
    }

    document.getElementById('delete-category-slug').value = slug;

    // Fetch usage stats
    showOverlay('Checking category usage...');
    try {
        const [eventsRes, groupsRes] = await Promise.all([
            fetch('/events.json'),
            fetch('/groups.json')
        ]);

        const events = await eventsRes.json();
        const groups = await groupsRes.json();

        const eventsWithCategory = events.filter(e =>
            e.categories && e.categories.includes(slug)
        );
        const groupsWithCategory = groups.filter(g =>
            g.categories && g.categories.includes(slug)
        );

        const usageStats = document.getElementById('usage-stats');
        usageStats.innerHTML = `
            <strong>Usage Statistics:</strong>
            <ul style="margin: 0.5rem 0;">
                <li>${eventsWithCategory.length} event(s) use this category</li>
                <li>${groupsWithCategory.length} group(s) use this category</li>
            </ul>
        `;

        hideOverlay();

        // Show delete modal
        document.getElementById('delete-modal').classList.add('active');
    } catch (error) {
        console.error('Error fetching usage stats:', error);
        hideOverlay();
        showError('Failed to load usage stats: ' + error.message);
    }
}

/**
 * Close delete modal
 */
function closeDeleteModal() {
    document.getElementById('delete-modal').classList.remove('active');
}

/**
 * Delete category
 */
async function deleteCategory() {
    const slug = document.getElementById('delete-category-slug').value;
    const category = categoriesData.find(c => c.slug === slug);

    if (!category) {
        showError('Category not found');
        return;
    }

    closeDeleteModal();
    showOverlay('Creating fork...');

    try {
        await ensureFork(octokit, userData);

        showOverlay('Creating branch...');
        const branchName = `delete-category-${slug}-${Date.now()}`;
        await createBranch(octokit, userData, branchName);

        showOverlay('Deleting category file...');
        const filePath = `_categories/${slug}.yaml`;

        await deleteFile(
            octokit, userData, branchName, filePath,
            `Delete category: ${category.name}`
        );

        showOverlay('Creating pull request...');

        // Get usage stats for PR body
        const [eventsRes, groupsRes] = await Promise.all([
            fetch('/events.json'),
            fetch('/groups.json')
        ]);

        const events = await eventsRes.json();
        const groups = await groupsRes.json();

        const eventsWithCategory = events.filter(e =>
            e.categories && e.categories.includes(slug)
        );
        const groupsWithCategory = groups.filter(g =>
            g.categories && g.categories.includes(slug)
        );

        const prBody = `## Delete Category: ${category.name}\n\nSlug: \`${slug}\`\n\n**Usage at time of deletion:**\n- ${eventsWithCategory.length} event(s) use this category\n- ${groupsWithCategory.length} group(s) use this category\n\nEvents and groups using this category will not be affected.\n\n---\nSubmitted via web interface by @${userData.login}`;

        const prUrl = await createPullRequest(
            octokit, userData, branchName,
            `Delete category: ${category.name}`,
            prBody
        );

        hideOverlay();
        showSuccess(prUrl);
    } catch (error) {
        console.error('Error deleting category:', error);
        hideOverlay();
        showError(error.message);
    }
}

/**
 * Generate YAML content for category
 */
function generateCategoryYAML(name, description) {
    // Escape special YAML characters in name and description
    const escapedName = name.includes(':') || name.includes('#') || name.includes('"')
        ? `"${name.replace(/"/g, '\\"')}"`
        : name;

    let yaml = `name: ${escapedName}\n`;

    if (description) {
        // Use block scalar for multi-line descriptions
        if (description.includes('\n')) {
            yaml += `description: |\n`;
            const lines = description.split('\n');
            for (const line of lines) {
                yaml += `  ${line}\n`;
            }
        } else {
            const escapedDescription = description.includes(':') || description.includes('#') || description.includes('"')
                ? `"${description.replace(/"/g, '\\"')}"`
                : description;
            yaml += `description: ${escapedDescription}\n`;
        }
    }

    return yaml;
}



/**
 * Continue editing after successful PR
 */
function continueEditing() {
    // Just reload categories to get fresh data
    loadCategories();
}

/**
 * Setup modal event handlers
 */
function setupModalHandlers() {
    // Create button
    document.getElementById('create-category-button')?.addEventListener('click', openCreateModal);

    // Edit/Create form
    document.getElementById('edit-category-form')?.addEventListener('submit', saveCategoryForm);
    document.getElementById('modal-close')?.addEventListener('click', closeEditModal);
    document.getElementById('cancel-edit')?.addEventListener('click', closeEditModal);

    // Close modal on background click
    document.getElementById('edit-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'edit-modal') {
            closeEditModal();
        }
    });

    // Delete modal
    document.getElementById('confirm-delete')?.addEventListener('click', deleteCategory);
    document.getElementById('delete-modal-close')?.addEventListener('click', closeDeleteModal);
    document.getElementById('cancel-delete')?.addEventListener('click', closeDeleteModal);

    // Close delete modal on background click
    document.getElementById('delete-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'delete-modal') {
            closeDeleteModal();
        }
    });

    // Continue editing
    document.getElementById('continue-editing')?.addEventListener('click', continueEditing);
}
