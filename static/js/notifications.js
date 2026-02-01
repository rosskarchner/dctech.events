/**
 * Unified notification system for dctech.events
 * Provides consistent, non-blocking notifications across all edit pages
 */

/**
 * Toast notification configuration
 */
const TOAST_CONFIG = {
    duration: 5000, // Auto-dismiss after 5 seconds (except for success/error)
    position: 'top-right', // Position of toast notifications
    zIndex: 10000
};

/**
 * Initialize notification container in the DOM
 */
function initNotificationContainer() {
    if (!document.getElementById('notification-container')) {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: ${TOAST_CONFIG.zIndex};
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        `;
        document.body.appendChild(container);
    }
}

/**
 * Create a notification element
 */
function createNotification(message, type = 'info', options = {}) {
    initNotificationContainer();
    
    const container = document.getElementById('notification-container');
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    // Icon based on type
    const icons = {
        error: '⚠',
        success: '✓',
        info: 'ℹ',
        warning: '⚠',
        status: '⟳'
    };
    
    const icon = icons[type] || icons.info;
    
    // Colors based on type
    const colors = {
        error: { bg: '#fef2f2', border: '#fca5a5', text: '#991b1b' },
        success: { bg: '#f0fdf4', border: '#86efac', text: '#166534' },
        info: { bg: '#eff6ff', border: '#93c5fd', text: '#1e40af' },
        warning: { bg: '#fffbeb', border: '#fcd34d', text: '#92400e' },
        status: { bg: '#f3f4f6', border: '#9ca3af', text: '#374151' }
    };
    
    const colorScheme = colors[type] || colors.info;
    
    notification.style.cssText = `
        background: ${colorScheme.bg};
        border: 2px solid ${colorScheme.border};
        color: ${colorScheme.text};
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        display: flex;
        align-items: start;
        gap: 0.75rem;
        animation: slideIn 0.3s ease-out;
        min-width: 300px;
        max-width: 400px;
    `;
    
    notification.innerHTML = `
        <span style="font-size: 1.25rem; flex-shrink: 0;">${icon}</span>
        <div style="flex: 1; word-break: break-word;">
            <strong style="display: block; margin-bottom: 0.25rem;">${getTitle(type)}</strong>
            <div>${message}</div>
        </div>
        ${options.dismissible !== false ? '<button class="notification-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer; padding: 0; margin-left: 0.5rem; color: inherit; opacity: 0.7; flex-shrink: 0;">&times;</button>' : ''}
    `;
    
    // Add animation styles if not already present
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(400px);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    container.appendChild(notification);
    
    // Add close button handler
    const closeBtn = notification.querySelector('.notification-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => dismissNotification(notification));
    }
    
    // Auto-dismiss for info and status messages
    if ((type === 'info' || type === 'status') && options.autoDismiss !== false) {
        setTimeout(() => dismissNotification(notification), TOAST_CONFIG.duration);
    }
    
    return notification;
}

/**
 * Get title based on notification type
 */
function getTitle(type) {
    const titles = {
        error: 'Error',
        success: 'Success',
        info: 'Info',
        warning: 'Warning',
        status: 'Processing'
    };
    return titles[type] || 'Notification';
}

/**
 * Dismiss a notification with animation
 */
function dismissNotification(notification) {
    notification.style.animation = 'slideOut 0.3s ease-in';
    setTimeout(() => {
        notification.remove();
    }, 300);
}

/**
 * Show an error notification
 * @param {string} message - Error message to display
 * @param {object} options - Additional options
 */
export function showError(message, options = {}) {
    return createNotification(message, 'error', { ...options, dismissible: true });
}

/**
 * Show a success notification with optional PR link
 * @param {string} messageOrPrUrl - Success message or PR URL
 * @param {object} options - Additional options
 */
export function showSuccess(messageOrPrUrl, options = {}) {
    let message = messageOrPrUrl;
    
    // If it's a PR URL, format it nicely
    if (messageOrPrUrl && (messageOrPrUrl.startsWith('http://') || messageOrPrUrl.startsWith('https://'))) {
        message = `Pull request created successfully!<br><a href="${messageOrPrUrl}" target="_blank" style="color: inherit; text-decoration: underline; word-break: break-all;">${messageOrPrUrl}</a>`;
    }
    
    return createNotification(message, 'success', { ...options, dismissible: true });
}

/**
 * Show a status/processing notification
 * @param {string} message - Status message to display
 * @param {object} options - Additional options
 */
export function showStatus(message, options = {}) {
    return createNotification(message, 'status', { ...options, dismissible: true, autoDismiss: false });
}

/**
 * Show an info notification
 * @param {string} message - Info message to display
 * @param {object} options - Additional options
 */
export function showInfo(message, options = {}) {
    return createNotification(message, 'info', { ...options, dismissible: true });
}

/**
 * Show a warning notification
 * @param {string} message - Warning message to display
 * @param {object} options - Additional options
 */
export function showWarning(message, options = {}) {
    return createNotification(message, 'warning', { ...options, dismissible: true });
}

/**
 * Clear all notifications
 */
export function clearNotifications() {
    const container = document.getElementById('notification-container');
    if (container) {
        const notifications = container.querySelectorAll('.notification');
        notifications.forEach(n => dismissNotification(n));
    }
}

/**
 * Show a blocking overlay with status message (for long operations)
 * @param {string} message - Message to display
 * @returns {function} Function to hide the overlay
 */
export function showOverlay(message = 'Processing...') {
    let overlay = document.getElementById('notification-overlay');
    
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'notification-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: ${TOAST_CONFIG.zIndex + 1000};
        `;
        
        overlay.innerHTML = `
            <div style="background: white; padding: 2rem; border-radius: 8px; text-align: center; min-width: 300px;">
                <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #3b82f6; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div>
                <p id="overlay-message" style="margin: 0; font-size: 1rem; color: #374151;"></p>
            </div>
        `;
        
        // Add spinner animation
        if (!document.getElementById('overlay-spinner-styles')) {
            const style = document.createElement('style');
            style.id = 'overlay-spinner-styles';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(overlay);
    }
    
    overlay.querySelector('#overlay-message').textContent = message;
    overlay.style.display = 'flex';
    
    // Return function to hide overlay
    return function hideOverlay() {
        if (overlay) {
            overlay.style.display = 'none';
        }
    };
}

/**
 * Hide the blocking overlay
 */
export function hideOverlay() {
    const overlay = document.getElementById('notification-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}
