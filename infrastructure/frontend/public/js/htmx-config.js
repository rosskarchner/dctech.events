// HTMX Configuration for organize.dctech.events
(function() {
    'use strict';

    // Wait for htmx to be available
    document.addEventListener('DOMContentLoaded', function() {
        // Configure HTMX to use the API URL from config
        document.body.addEventListener('htmx:configRequest', function(event) {
            // Prepend API URL to all relative paths starting with /api
            if (event.detail.path.startsWith('/api')) {
                event.detail.path = window.CONFIG.apiUrl.replace(/\/$/, '') + event.detail.path;
            }

            // Add auth token if user is authenticated
            if (window.auth && window.auth.isAuthenticated()) {
                window.auth.getIdToken((err, token) => {
                    if (!err && token) {
                        event.detail.headers['Authorization'] = `Bearer ${token}`;
                    }
                });
            }
        });

        // Global error handler
        document.body.addEventListener('htmx:responseError', function(event) {
            console.error('HTMX request failed:', event.detail);
            const target = event.detail.target;
            if (target) {
                target.innerHTML = '<div class="message error">Request failed. Please try again.</div>';
            }
        });

        // Show loading indicators
        document.body.addEventListener('htmx:beforeRequest', function(event) {
            const indicators = document.querySelectorAll('.htmx-indicator');
            indicators.forEach(ind => ind.style.display = 'inline');
        });

        document.body.addEventListener('htmx:afterRequest', function(event) {
            const indicators = document.querySelectorAll('.htmx-indicator');
            indicators.forEach(ind => ind.style.display = 'none');
        });
    });
})();
