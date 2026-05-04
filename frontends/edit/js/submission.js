(function() {
  function detectSiteFromHostname() {
    const host = window.location.hostname;
    if (host === 'dcstem.events' || host === 'www.dcstem.events' || host.includes('dcstem')) {
      return 'dcstem';
    }
    return 'dctech';
  }

  function setSiteField() {
    const site = detectSiteFromHostname();
    const siteField = document.getElementById('site-field');
    if (siteField) {
      siteField.value = site;
    }
  }

  function setResponse(container, message, isError) {
    if (!container) return;
    container.innerHTML = `<div class="message ${isError ? 'message-error' : 'message-success'}"><p>${message}</p></div>`;
  }

  function collectFormData(form) {
    const data = new URLSearchParams();
    const formData = new FormData(form);
    for (const [key, value] of formData.entries()) {
      data.append(key, value);
    }
    return data;
  }

  async function loadCategories() {
    const container = document.getElementById('category-checkboxes');
    if (!container) return;

    try {
      const response = await fetch(DctechAuth.getApiUrl('/api/categories'));
      if (!response.ok) throw new Error('Failed to load categories');
      const categories = await response.json();

      container.innerHTML = '';
      Object.entries(categories)
        .sort((a, b) => a[1].name.localeCompare(b[1].name))
        .forEach(([slug, cat]) => {
          const label = document.createElement('label');
          label.innerHTML = `<input type="checkbox" name="categories" value="${slug}"> ${cat.name}`;
          container.appendChild(label);
        });
    } catch (err) {
      console.error('Error loading categories:', err);
      container.innerHTML = '<span class="error">Failed to load categories. Please try again later.</span>';
    }
  }

  async function handleSubmit(form, typeLabel) {
    const responseArea = document.getElementById('form-response');
    const submitButton = form.querySelector('button[type="submit"]');
    const originalDisabled = submitButton ? submitButton.disabled : false;
    if (submitButton) submitButton.disabled = true;

    try {
      const response = await DctechAuth.authorizedFetch('/api/submissions', {
        method: 'POST',
        body: collectFormData(form),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `Failed to submit ${typeLabel}.`);
      }

      form.reset();
      setResponse(responseArea, `Thanks — your ${typeLabel} was submitted for review. Draft ID: ${payload.draft_id}.`, false);
      if (typeLabel === 'event') {
        loadCategories();
      }
    } catch (err) {
      setResponse(responseArea, err.message, true);
    } finally {
      if (submitButton) submitButton.disabled = originalDisabled;
    }
  }

  function initSubmissionPage() {
    setSiteField();
    const hasAuth = DctechAuth.requireAuth();
    if (!hasAuth) return;

    const eventForm = document.getElementById('event-form');
    if (eventForm) {
      loadCategories();
      eventForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await handleSubmit(eventForm, 'event');
      });
    }

    const groupForm = document.getElementById('group-form');
    if (groupForm) {
      groupForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await handleSubmit(groupForm, 'group');
      });
    }
  }

  window.DctechSubmissionPage = {
    init: initSubmissionPage,
  };
})();
