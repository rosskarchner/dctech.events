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
