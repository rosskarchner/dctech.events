(function() {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDate(isoString) {
    if (!isoString) return 'Unknown';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  }

  async function loadSubscribers() {
    const listDiv = document.getElementById('subscribers-list');
    const loadingDiv = document.getElementById('subscribers-loading');
    const countDiv = document.getElementById('subscriber-count');

    if (!listDiv || !loadingDiv || !countDiv) {
      console.error('Required DOM elements not found');
      return;
    }

    // Show loading indicator
    loadingDiv.style.display = 'block';
    listDiv.innerHTML = '';

    try {
      const response = await DctechAuth.authorizedFetch('/api/admin/subscribers');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const subscribers = data.subscribers || [];

      // Update count
      countDiv.textContent = subscribers.length;

      if (subscribers.length === 0) {
        listDiv.innerHTML = '<p style="padding: 1rem; text-align: center; color: #666;">No subscribers found.</p>';
      } else {
        // Build table
        let html = `
          <table class="subscribers-table">
            <thead>
              <tr>
                <th>Email Address</th>
                <th>Subscribed</th>
              </tr>
            </thead>
            <tbody>
        `;

        for (const sub of subscribers) {
          html += `
            <tr>
              <td class="email">${escapeHtml(sub.email)}</td>
              <td class="timestamp">${escapeHtml(formatDate(sub.subscribed_at))}</td>
            </tr>
          `;
        }

        html += `
            </tbody>
          </table>
        `;

        listDiv.innerHTML = html;
      }
    } catch (error) {
      console.error('Error loading subscribers:', error);
      listDiv.innerHTML = `
        <div class="message message-error" style="padding: 1rem;">
          <p><strong>Error loading subscribers:</strong> ${escapeHtml(error.message)}</p>
        </div>
      `;
    } finally {
      // Hide loading indicator
      loadingDiv.style.display = 'none';
    }
  }

  window.DctechSubscribersPage = {
    init() {
      const isAdmin = DctechAuth.requireAdmin();
      if (!isAdmin) return;
      loadSubscribers();
    }
  };
})();
