/**
 * Date Navigation Component
 * Handles mobile drawer toggle and scroll position tracking
 */

(function() {
    'use strict';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        const dateNav = document.getElementById('date-nav');
        const toggleBtn = document.getElementById('date-nav-toggle');
        const closeBtn = document.getElementById('date-nav-close');

        if (!dateNav || !toggleBtn) {
            return; // Date navigation not present on this page
        }

        // Mobile drawer toggle
        toggleBtn.addEventListener('click', function() {
            const isOpen = dateNav.classList.contains('open');
            if (isOpen) {
                closeDateNav();
            } else {
                openDateNav();
            }
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', closeDateNav);
        }

        // Close on outside click (mobile only)
        document.addEventListener('click', function(e) {
            if (window.innerWidth < 1024 &&
                dateNav.classList.contains('open') &&
                !dateNav.contains(e.target) &&
                !toggleBtn.contains(e.target)) {
                closeDateNav();
            }
        });

        // Close on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && dateNav.classList.contains('open')) {
                closeDateNav();
                toggleBtn.focus(); // Return focus to toggle button
            }
        });

        // Smooth scrolling for date links
        const dateLinks = dateNav.querySelectorAll('.date-link, .quick-jump-link');
        dateLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetId = this.getAttribute('href').substring(1); // Remove #
                const targetElement = document.getElementById(targetId);

                if (targetElement) {
                    // Close mobile drawer if open
                    if (window.innerWidth < 1024) {
                        closeDateNav();
                    }

                    // Smooth scroll to target
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });

                    // Update URL without triggering scroll
                    history.pushState(null, null, '#' + targetId);
                }
            });
        });

        // Scroll tracking - highlight current date in navigation
        let ticking = false;
        window.addEventListener('scroll', function() {
            if (!ticking) {
                window.requestAnimationFrame(function() {
                    updateActiveDate();
                    ticking = false;
                });
                ticking = true;
            }
        });

        // Initial active date update
        updateActiveDate();
    }

    function openDateNav() {
        const dateNav = document.getElementById('date-nav');
        const toggleBtn = document.getElementById('date-nav-toggle');

        dateNav.classList.add('open');
        toggleBtn.setAttribute('aria-expanded', 'true');

        // Prevent body scroll when drawer is open (mobile)
        if (window.innerWidth < 1024) {
            document.body.style.overflow = 'hidden';
        }
    }

    function closeDateNav() {
        const dateNav = document.getElementById('date-nav');
        const toggleBtn = document.getElementById('date-nav-toggle');

        dateNav.classList.remove('open');
        toggleBtn.setAttribute('aria-expanded', 'false');

        // Restore body scroll
        document.body.style.overflow = '';
    }

    function updateActiveDate() {
        // Find which date section is currently in view
        const dayContainers = document.querySelectorAll('.day-container');
        const dateLinks = document.querySelectorAll('.date-link');

        if (dayContainers.length === 0 || dateLinks.length === 0) {
            return;
        }

        let currentDate = null;
        const scrollPosition = window.scrollY + 100; // Offset for better UX

        // Find the current date section in viewport
        dayContainers.forEach(function(container) {
            const heading = container.querySelector('.day-heading');
            if (heading) {
                const dateId = heading.id;
                const containerTop = container.offsetTop;
                const containerBottom = containerTop + container.offsetHeight;

                if (scrollPosition >= containerTop && scrollPosition < containerBottom) {
                    currentDate = dateId;
                }
            }
        });

        // Update active state in navigation
        dateLinks.forEach(function(link) {
            const linkDate = link.getAttribute('data-date');
            if (linkDate === currentDate) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    // Handle window resize - close drawer if resizing to desktop
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            if (window.innerWidth >= 1024) {
                closeDateNav();
            }
        }, 250);
    });
})();
