(function() {
  const EXECUTE_API_BASE = 'https://j62p8vusa3.execute-api.us-east-1.amazonaws.com/prod';
  const host = window.location.hostname;
  const onMainDctechSite = host === 'dctech.events' || host === 'www.dctech.events';
  const onMainStemSite = host === 'dc.localstem.events' || host === 'www.dc.localstem.events';
  const appBasePath = (onMainDctechSite || onMainStemSite) ? '/edit/' : '/';
  const apiBaseUrl = (onMainDctechSite || onMainStemSite) ? EXECUTE_API_BASE : '';

  function ensureLeadingSlash(path) {
    return path.startsWith('/') ? path : `/${path}`;
  }

  function trimTrailingSlash(path) {
    return path.endsWith('/') ? path.slice(0, -1) : path;
  }

  function appUrl(path) {
    const normalized = path ? path.replace(/^\/+/, '') : '';
    return `${appBasePath}${normalized}`;
  }

  function apiUrl(path) {
    const normalized = ensureLeadingSlash(path);
    return apiBaseUrl ? `${trimTrailingSlash(apiBaseUrl)}${normalized}` : normalized;
  }

  window.DctechEditConfig = {
    appBasePath,
    apiBaseUrl,
    authCallbackPath: appUrl('auth/callback.html'),
    appHomePath: appBasePath,
    appUrl,
    apiUrl,
  };
})();
