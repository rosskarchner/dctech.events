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
  let editCategoriesMode = {};

  function draftLabel(draft) {
    return draft.draft_type === 'group'
      ? (draft.name || draft.title || 'Untitled')
      : (draft.title || 'Untitled');
  }

  function renderCategoryList(draft) {
    const cats = (draft.categories || [])
      .map(slug => categoriesBySlug[slug]?.name || slug)
      .filter(Boolean);
    return cats.length > 0
      ? cats.map(name => `<span class="category-badge">${escapeHtml(name)}</span>`).join('')
      : '<span class="text-muted">None selected</span>';
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

  function renderEventDetails(draft) {
    const fields = [
      draft.date ? { label: 'Date', value: draft.date } : null,
      draft.time ? { label: 'Time', value: draft.time } : null,
      draft.location ? { label: 'Location', value: draft.location } : null,
      draft.url ? { label: 'URL', value: `<a href="${escapeHtml(draft.url)}" target="_blank" rel="noopener">${escapeHtml(draft.url)}</a>` } : null,
      draft.description ? { label: 'Description', value: draft.description } : null,
    ].filter(Boolean);

    return fields.length > 0
      ? fields.map(field => `<div class="detail-row"><span class="detail-label">${escapeHtml(field.label)}:</span> <span class="detail-value">${field.value}</span></div>`).join('')
      : '<div class="text-muted">No details provided</div>';
  }

  function renderGroupDetails(draft) {
    const fields = [
      draft.website ? { label: 'Website', value: `<a href="${escapeHtml(draft.website)}" target="_blank" rel="noopener">${escapeHtml(draft.website)}</a>` } : null,
      draft.ical_url ? { label: 'iCal URL', value: `<a href="${escapeHtml(draft.ical_url)}" target="_blank" rel="noopener">${escapeHtml(draft.ical_url)}</a>` } : null,
      draft.description ? { label: 'Description', value: draft.description } : null,
    ].filter(Boolean);

    return fields.length > 0
      ? fields.map(field => `<div class="detail-row"><span class="detail-label">${escapeHtml(field.label)}:</span> <span class="detail-value">${field.value}</span></div>`).join('')
      : '<div class="text-muted">No details provided</div>';
  }

  function renderDraftDetails(draft) {
    const isEditMode = editCategoriesMode[draft.id];
    const detailContent = draft.draft_type === 'group'
      ? renderGroupDetails(draft)
      : renderEventDetails(draft);

    const categorySection = isEditMode
      ? `<div class="categories-section-edit">
           <h4>Edit Categories</h4>
           ${renderCategoryCheckboxes(draft)}
         </div>`
      : `<div class="categories-section">
           <span class="section-label">Categories:</span> ${renderCategoryList(draft)}
           <button type="button" class="btn btn-sm btn-outline" data-action="edit-categories" data-draft-id="${escapeHtml(draft.id)}" style="margin-left: 1rem;">Edit</button>
         </div>`;

    return `
      <tr class="approve-form-row">
        <td colspan="5">
          <div class="approve-form">
            <div class="approve-form-header">
              <strong>${draft.draft_type === 'group' ? 'Group:' : 'Event:'}</strong> ${escapeHtml(draftLabel(draft))}
              <span class="approve-form-submitter">by ${escapeHtml(draft.submitter_email || 'unknown')}</span>
            </div>
            <div class="draft-content">
              ${detailContent}
            </div>
            <div class="categories-wrapper">
              ${categorySection}
            </div>
            <div class="approve-form-actions">
              ${isEditMode
                ? `<button type="button" class="btn btn-success btn-sm" data-action="confirm-approve" data-draft-id="${escapeHtml(draft.id)}">Approve with Categories</button>
                   <button type="button" class="btn btn-outline btn-sm" data-action="cancel-edit-categories" data-draft-id="${escapeHtml(draft.id)}">Cancel Edit</button>`
                : `<button type="button" class="btn btn-success btn-sm" data-action="confirm-approve" data-draft-id="${escapeHtml(draft.id)}">Approve</button>
                   <button type="button" class="btn btn-danger btn-sm" data-action="reject" data-draft-id="${escapeHtml(draft.id)}">Reject</button>
                   <button type="button" class="btn btn-outline btn-sm" data-action="collapse" data-draft-id="${escapeHtml(draft.id)}">Collapse</button>`
              }
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
      return renderDraftDetails(draft);
    }).join('');

    container.innerHTML = `
      <div class="draft-queue">
        <h2>Pending Submissions (${currentDrafts.length})</h2>
        <table>
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

  async function collapseDraft(draftId) {
    expandedDraftId = null;
    editCategoriesMode[draftId] = false;
    await loadQueue();
  }

  function toggleEditCategories(draftId) {
    editCategoriesMode[draftId] = !editCategoriesMode[draftId];
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
        editCategoriesMode = {};
        await loadQueue();
      });
    }

    document.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;

      const action = button.getAttribute('data-action');
      const draftId = button.getAttribute('data-draft-id');

      try {
        if (action === 'edit-categories') {
          toggleEditCategories(draftId);
        } else if (action === 'cancel-edit-categories') {
          editCategoriesMode[draftId] = false;
          renderQueue();
        } else if (action === 'collapse') {
          await collapseDraft(draftId);
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
