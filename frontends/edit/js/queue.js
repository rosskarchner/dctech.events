(function() {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  let categoriesBySlug = {};
  let currentDrafts = [];
  let expandedDraftId = null;

  function draftLabel(draft) {
    return draft.draft_type === 'group'
      ? (draft.name || draft.title || 'Untitled')
      : (draft.title || 'Untitled');
  }

  function renderCategoryCheckboxes(draft) {
    return Object.entries(categoriesBySlug)
      .sort((a, b) => a[1].name.localeCompare(b[1].name))
      .map(([slug, cat]) => {
        const checked = (draft.categories || []).includes(slug) ? 'checked' : '';
        return `
          <label class="category-checkbox">
            <input type="checkbox" name="categories" value="${escapeHtml(slug)}" ${checked}>
            ${escapeHtml(cat.name || slug)}
          </label>
        `;
      }).join('');
  }

  function renderDraftDetails(draft) {
    const detailLines = [
      draft.date ? `<div><strong>Date:</strong> ${escapeHtml(draft.date)}</div>` : '',
      draft.time ? `<div><strong>Time:</strong> ${escapeHtml(draft.time)}</div>` : '',
      draft.location ? `<div><strong>Location:</strong> ${escapeHtml(draft.location)}</div>` : '',
      draft.url ? `<div><strong>URL:</strong> <a href="${escapeHtml(draft.url)}" target="_blank" rel="noopener">${escapeHtml(draft.url)}</a></div>` : '',
      draft.description ? `<div><strong>Description:</strong> ${escapeHtml(draft.description)}</div>` : '',
    ].filter(Boolean).join('');

    return `
      <tr class="approve-form-row">
        <td colspan="5">
          <div class="approve-form">
            <div class="approve-form-header">
              <strong>Approving:</strong> ${escapeHtml(draftLabel(draft))}
              ${draft.date ? `&mdash; ${escapeHtml(draft.date)}` : ''}
              <span class="approve-form-submitter">submitted by ${escapeHtml(draft.submitter_email || 'unknown')}</span>
            </div>
            <div class="approve-form-categories">
              <span class="approve-form-label">Categories:</span>
              ${renderCategoryCheckboxes(draft)}
            </div>
            <div class="draft-detail" style="margin: 1rem 0;">${detailLines || '<div>No additional details.</div>'}</div>
            <div class="approve-form-actions">
              <button type="button" class="btn btn-success btn-sm" data-action="confirm-approve" data-draft-id="${escapeHtml(draft.id)}">Confirm Approve</button>
              <button type="button" class="btn btn-outline btn-sm" data-action="cancel-approve">Cancel</button>
            </div>
          </div>
        </td>
      </tr>
    `;
  }

  function renderQueue() {
    const container = document.getElementById('queue-list');
    if (!container) return;

    if (!currentDrafts.length) {
      container.innerHTML = '<div class="draft-queue"><h2>Pending Submissions</h2><p>No pending submissions.</p></div>';
      return;
    }

    const rows = currentDrafts.map((draft) => {
      const mainRow = `
        <tr id="draft-${escapeHtml(draft.id)}">
          <td>${escapeHtml(draft.draft_type)}</td>
          <td>
            ${escapeHtml(draftLabel(draft))}
            ${draft.draft_type === 'event' && draft.date ? `<br><small>${escapeHtml(draft.date)}</small>` : ''}
          </td>
          <td>${escapeHtml(draft.submitter_email || '')}</td>
          <td>${escapeHtml(draft.created_at || '')}</td>
          <td>
            <button type="button" data-action="approve" data-draft-id="${escapeHtml(draft.id)}">Approve</button>
            <button type="button" data-action="reject" data-draft-id="${escapeHtml(draft.id)}">Reject</button>
            <button type="button" data-action="details" data-draft-id="${escapeHtml(draft.id)}">Details</button>
          </td>
        </tr>
      `;
      const detailRow = expandedDraftId === draft.id ? renderDraftDetails(draft) : '';
      return mainRow + detailRow;
    }).join('');

    container.innerHTML = `
      <div class="draft-queue">
        <h2>Pending Submissions</h2>
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Title / Name</th>
              <th>Submitted By</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  async function loadQueue() {
    const loading = document.getElementById('queue-loading');
    if (loading) loading.style.display = 'block';

    try {
      const [queueResponse, categoriesResponse] = await Promise.all([
        DctechAuth.authorizedFetch('/api/admin/queue'),
        fetch(DctechAuth.getApiUrl('/api/categories')),
      ]);
      const queuePayload = await queueResponse.json();
      const categoriesPayload = await categoriesResponse.json();

      if (!queueResponse.ok) {
        throw new Error(queuePayload.error || 'Failed to load moderation queue.');
      }
      if (!categoriesResponse.ok) {
        throw new Error('Failed to load categories.');
      }

      currentDrafts = queuePayload.drafts || [];
      categoriesBySlug = categoriesPayload || {};
      renderQueue();
    } catch (err) {
      const container = document.getElementById('queue-list');
      if (container) {
        container.innerHTML = `<div class="message message-error"><p>${escapeHtml(err.message)}</p></div>`;
      }
    } finally {
      if (loading) loading.style.display = 'none';
    }
  }

  async function expandDraft(draftId) {
    if (expandedDraftId === draftId) {
      expandedDraftId = null;
      renderQueue();
      return;
    }

    const response = await DctechAuth.authorizedFetch(`/api/admin/drafts/${draftId}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Failed to load draft details.');
    }

    currentDrafts = currentDrafts.map((draft) => (
      draft.id === draftId ? payload.draft : draft
    ));
    expandedDraftId = draftId;
    renderQueue();
  }

  async function approveDraft(draftId) {
    const row = document.querySelector(`button[data-action="confirm-approve"][data-draft-id="${draftId}"]`)?.closest('tr');
    const formData = new URLSearchParams();
    if (row) {
      row.querySelectorAll('input[name="categories"]:checked').forEach((input) => {
        formData.append('categories', input.value);
      });
    }

    const response = await DctechAuth.authorizedFetch(`/api/admin/drafts/${draftId}/approve`, {
      method: 'POST',
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Failed to approve draft.');
    }

    expandedDraftId = null;
    await loadQueue();
  }

  async function rejectDraft(draftId) {
    const response = await DctechAuth.authorizedFetch(`/api/admin/drafts/${draftId}/reject`, {
      method: 'POST',
      body: new URLSearchParams(),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Failed to reject draft.');
    }

    expandedDraftId = null;
    await loadQueue();
  }

  function bindEvents() {
    const refreshButton = document.getElementById('queue-refresh');
    if (refreshButton) {
      refreshButton.addEventListener('click', async () => {
        expandedDraftId = null;
        await loadQueue();
      });
    }

    document.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;

      const action = button.getAttribute('data-action');
      const draftId = button.getAttribute('data-draft-id');

      try {
        if (action === 'approve' || action === 'details') {
          await expandDraft(draftId);
        } else if (action === 'cancel-approve') {
          expandedDraftId = null;
          renderQueue();
        } else if (action === 'confirm-approve') {
          await approveDraft(draftId);
        } else if (action === 'reject') {
          await rejectDraft(draftId);
        }
      } catch (err) {
        const container = document.getElementById('queue-list');
        if (container) {
          container.insertAdjacentHTML('afterbegin', `<div class="message message-error"><p>${escapeHtml(err.message)}</p></div>`);
        }
      }
    });
  }

  async function initQueuePage() {
    const isAdmin = DctechAuth.requireAdmin();
    if (!isAdmin) return;
    bindEvents();
    await loadQueue();
  }

  window.DctechQueuePage = {
    init: initQueuePage,
  };
})();
