// Shared GitHub utilities for creating PRs
import { Octokit } from 'octokit';

// Repository configuration
export const REPO_CONFIG = {
    owner: 'rosskarchner',
    repo: 'dctech.events',
    branch: 'main'
};

/**
 * Ensure user has a fork of the repository
 */
export async function ensureFork(octokit, userData) {
    try {
        await octokit.rest.repos.get({
            owner: userData.login,
            repo: REPO_CONFIG.repo
        });
    } catch (error) {
        if (error.status === 404) {
            await octokit.rest.repos.createFork({
                owner: REPO_CONFIG.owner,
                repo: REPO_CONFIG.repo
            });
            // Wait for fork to be ready
            await new Promise(resolve => setTimeout(resolve, 3000));
        } else {
            throw error;
        }
    }
}

/**
 * Create a new branch in user's fork
 */
export async function createBranch(octokit, userData, branchName) {
    // Get the default branch ref from upstream
    const { data: mainBranch } = await octokit.rest.repos.getBranch({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        branch: REPO_CONFIG.branch
    });

    const mainSha = mainBranch.commit.sha;

    // Create branch in fork
    await octokit.rest.git.createRef({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        ref: `refs/heads/${branchName}`,
        sha: mainSha
    });

    return mainSha;
}

/**
 * Create or update a file in the repository
 */
export async function createOrUpdateFile(octokit, userData, branchName, filePath, content, commitMessage) {
    // Check if file exists and get its SHA
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
        if (error.status !== 404) {
            throw error;
        }
    }

    // Create or update file
    const commitOptions = {
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        path: filePath,
        message: commitMessage,
        content: btoa(unescape(encodeURIComponent(content))), // Handle UTF-8
        branch: branchName
    };

    if (existingSha) {
        commitOptions.sha = existingSha;
    }

    await octokit.rest.repos.createOrUpdateFileContents(commitOptions);
}

/**
 * Delete a file from the repository
 */
export async function deleteFile(octokit, userData, branchName, filePath, commitMessage) {
    // Get file SHA
    const { data: existingFile } = await octokit.rest.repos.getContent({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        path: filePath,
        ref: branchName
    });

    // Delete file
    await octokit.rest.repos.deleteFile({
        owner: userData.login,
        repo: REPO_CONFIG.repo,
        path: filePath,
        message: commitMessage,
        sha: existingFile.sha,
        branch: branchName
    });
}

/**
 * Create a pull request
 */
export async function createPullRequest(octokit, userData, branchName, title, body) {
    const { data: pr } = await octokit.rest.pulls.create({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        title: title,
        head: `${userData.login}:${branchName}`,
        base: REPO_CONFIG.branch,
        body: body
    });

    return pr.html_url;
}

/**
 * Generate YAML content for event override with duplicate_of field
 */
export function generateDuplicateOverrideYAML(primaryEventId) {
    return `duplicate_of: ${primaryEventId}\n`;
}

/**
 * Generate YAML content for event override with hidden field
 */
export function generateHiddenOverrideYAML() {
    return `hidden: true\n`;
}

/**
 * Fetch all events from events.json
 */
export async function fetchAllEvents() {
    const response = await fetch('/events.json');
    if (!response.ok) {
        throw new Error('Failed to load events data');
    }
    return await response.json();
}

/**
 * Generate YAML for category override
 * Merges with existing override if present
 */
export async function generateCategoryOverride(octokit, userData, branchName, eventId, category) {
    let existingContent = '';

    try {
        const { data: file } = await octokit.rest.repos.getContent({
            owner: userData.login,
            repo: REPO_CONFIG.repo,
            path: `_event_overrides/${eventId}.yaml`,
            ref: branchName
        });
        existingContent = atob(file.content);
    } catch (error) {
        if (error.status !== 404) throw error;
    }

    if (existingContent) {
        return mergeCategoryIntoYAML(existingContent, category);
    } else {
        return `categories:\n  - ${category}\n`;
    }
}

/**
 * Merge category into existing YAML content
 */
function mergeCategoryIntoYAML(existingYAML, newCategory) {
    const lines = existingYAML.split('\n');
    const result = [];
    let existingCategories = [];

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.match(/^categories:/)) {
            // Extract existing categories
            while (i + 1 < lines.length && lines[i + 1].match(/^  - (.+)/)) {
                i++;
                const match = lines[i].match(/^  - (.+)/);
                existingCategories.push(match[1]);
            }
            continue;
        }

        result.push(line);
    }

    // Remove trailing empty lines
    while (result.length > 0 && result[result.length - 1].trim() === '') {
        result.pop();
    }

    // Add categories (merge and dedupe)
    const allCategories = [...new Set([...existingCategories, newCategory])];
    result.push('categories:');
    for (const cat of allCategories) {
        result.push(`  - ${cat}`);
    }
    result.push('');

    return result.join('\n');
}

/**
 * Update category in single event file (for events in _single_events/)
 * Fetches the file, updates the category, and returns the updated content
 */
export async function updateSingleEventCategory(octokit, userData, branchName, eventId, category) {
    const filePath = `_single_events/${eventId}.yaml`;

    // Fetch existing file content from upstream (not the branch yet, get original)
    const { data: file } = await octokit.rest.repos.getContent({
        owner: REPO_CONFIG.owner,
        repo: REPO_CONFIG.repo,
        path: filePath,
        ref: REPO_CONFIG.branch
    });

    const existingContent = atob(file.content);
    return mergeCategoryIntoYAML(existingContent, category);
}
