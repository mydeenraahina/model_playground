document.addEventListener('DOMContentLoaded', () => {
  document.body.classList.add('is-ready');

  const state = {
    activeView: 'dashboard',
    authMode: 'login',
    user: null,
    selectedModel: null,
    latestResults: [],
    history: [],
    expandedHistoryId: null,
    performanceLabels: {
      ocr: 'OCR',
      text_to_json: 'Text to JSON',
      document_summarization: 'Document summarization',
      document_classification: 'Document classification',
      chatbot: 'Chatbot',
      text_generation: 'Text generation',
    },
    allOptions: [
      'ocr',
      'text_to_json',
      'document_summarization',
      'document_classification',
      'chatbot',
      'text_generation',
    ],
    pendingIssue: null,
  };

  const authSection = document.getElementById('authSection');
  const searchSection = document.getElementById('searchSection');
  const issueSection = document.getElementById('issueSection');
  const latestResultsSection = document.getElementById('latestResultsSection');
  const historySection = document.getElementById('historySection');
  const logoutBtn = document.getElementById('logoutBtn');
  const loginModeBtn = document.getElementById('loginModeBtn');
  const registerModeBtn = document.getElementById('registerModeBtn');
  const authEmailRow = document.getElementById('authEmailRow');
  const authForm = document.getElementById('authForm');
  const authUsername = document.getElementById('authUsername');
  const authEmail = document.getElementById('authEmail');
  const authPassword = document.getElementById('authPassword');
  const authSubmitBtn = document.getElementById('authSubmitBtn');
  const authStatus = document.getElementById('authStatus');
  const searchForm = document.getElementById('searchForm');
  const searchQuery = document.getElementById('searchQuery');
  const searchStatus = document.getElementById('searchStatus');
  const searchHistoryMatches = document.getElementById('searchHistoryMatches');
  const newModelSection = document.getElementById('newModelSection');
  const newModelForm = document.getElementById('newModelForm');
  const newModelName = document.getElementById('newModelName');
  const newModelProvider = document.getElementById('newModelProvider');
  const newModelEndpoint = document.getElementById('newModelEndpoint');
  const newModelApiKey = document.getElementById('newModelApiKey');
  const newModelApiVersion = document.getElementById('newModelApiVersion');
  const newModelPrompt = document.getElementById('newModelPrompt');
  const newModelFile = document.getElementById('newModelFile');
  const newModelCapabilities = document.getElementById('newModelCapabilities');
  const newModelRunBtn = document.getElementById('newModelRunBtn');
  const newModelStatus = document.getElementById('newModelStatus');
  const issueForm = document.getElementById('issueForm');
  const issueContext = document.getElementById('issueContext');
  const issueEmail = document.getElementById('issueEmail');
  const issueDescription = document.getElementById('issueDescription');
  const issueStatus = document.getElementById('issueStatus');
  const cancelIssueBtn = document.getElementById('cancelIssueBtn');
  const latestResults = document.getElementById('latestResults');
  const historyList = document.getElementById('historyList');
  const historyEmpty = document.getElementById('historyEmpty');
  const historySearch = document.getElementById('historySearch');
  const historyStatusFilter = document.getElementById('historyStatusFilter');
  const exportHistoryBtn = document.getElementById('exportHistoryBtn');
  const dashboardView = document.getElementById('dashboardView');
  const dashboardShowcase = document.getElementById('dashboardShowcase');
  const historyView = document.getElementById('historyView');
  const dashboardNav = document.getElementById('dashboardNav');
  const historyNav = document.getElementById('historyNav');
  const historyTotalStat = document.getElementById('historyTotalStat');
  const historySuccessStat = document.getElementById('historySuccessStat');
  const historyAvgTimeStat = document.getElementById('historyAvgTimeStat');
  const historyFieldsStat = document.getElementById('historyFieldsStat');
  const totalExtractionsStat = document.getElementById('totalExtractionsStat');
  const successRateStat = document.getElementById('successRateStat');
  const avgProcessingStat = document.getElementById('avgProcessingStat');
  const latestModelStat = document.getElementById('latestModelStat');
  const primaryTestOptions = [
    'ocr',
    'text_to_json',
    'document_summarization',
    'document_classification',
  ];

  function performanceLabel(option) {
    return state.performanceLabels[option] || option;
  }

  function prettyJson(value) {
    return JSON.stringify(value, null, 2);
  }

  function formatDuration(ms) {
    const value = Number(ms || 0);
    if (value >= 1000) {
      return `${(value / 1000).toFixed(value >= 10000 ? 1 : 2)} s`;
    }
    return `${value} ms`;
  }

  function formatMetricValue(value) {
    if (value === null || value === undefined || value === '') {
      return 'Not scored';
    }
    const numeric = Number(value);
    if (Number.isNaN(numeric)) {
      return String(value);
    }
    const percent = numeric <= 1 ? numeric * 100 : numeric;
    return `${percent.toFixed(percent >= 10 ? 1 : 2)}%`;
  }

  function getRunFieldCount(run) {
    const output = run?.output_json;
    if (Array.isArray(output)) {
      return output.length;
    }
    if (output && typeof output === 'object') {
      return Object.keys(output).length;
    }
    return 0;
  }

  function getRunFilename(run) {
    const filePath = run?.input_file_path || '';
    if (filePath) {
      return filePath.split(/[/\\\\]/).pop() || filePath;
    }
    return `${run.model_name} (${performanceLabel(run.performance_type)})`;
  }

  function normalizeModelName(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  function compactModelName(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '');
  }

  function formatCreatedAt(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value || '';
    }
    return date.toLocaleString();
  }

  function getHistoryStatus(run) {
    return run.success ? 'completed' : 'failed';
  }

  function getEstimatedStageBreakdown(run) {
    const totalSeconds = Math.max(Number(run.time_taken_ms || 0) / 1000, 0);
    const weights = [0.15, 0.55, 0.2, 0.1];
    const labels = [
      { title: 'Uploading', tone: 'blue', note: 'Input received' },
      { title: 'AI Analysis', tone: 'violet', note: 'Model inference' },
      { title: 'Data Extraction', tone: 'green', note: 'Structured output build' },
      { title: 'Output Rendering', tone: 'amber', note: 'Response packaging' },
    ];

    return labels.map((item, index) => ({
      ...item,
      seconds: totalSeconds ? totalSeconds * weights[index] : 0,
    }));
  }

  function getStageIconSvg(stageTitle) {
    const icons = {
      Uploading: `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 16V4"></path>
          <path d="M8 8l4-4 4 4"></path>
          <path d="M4 20h16"></path>
        </svg>
      `,
      'AI Analysis': `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3l1.8 3.6L18 8.4l-3 2.9.7 4.3-3.7-2-3.7 2 .7-4.3-3-2.9 4.2-.8L12 3z"></path>
        </svg>
      `,
      'Data Extraction': `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="4" width="16" height="16" rx="2"></rect>
          <path d="M8 8h8"></path>
          <path d="M8 12h8"></path>
          <path d="M8 16h5"></path>
        </svg>
      `,
      'Output Rendering': `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="2"></rect>
          <path d="M7 9h10"></path>
          <path d="M7 13h6"></path>
        </svg>
      `,
    };

    return icons[stageTitle] || `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"></circle>
      </svg>
    `;
  }

  function getFilteredHistoryRuns() {
    const query = historySearch?.value?.trim().toLowerCase() || '';
    const status = historyStatusFilter?.value || 'all';

    return (state.history || []).filter((run) => {
      const runStatus = getHistoryStatus(run);
      if (status !== 'all' && runStatus !== status) {
        return false;
      }

      if (!query) {
        return true;
      }

      const haystack = [
        getRunFilename(run),
        run.model_name,
        run.provider,
        performanceLabel(run.performance_type),
        run.created_at,
      ]
        .join(' ')
        .toLowerCase();

      return haystack.includes(query);
    });
  }

  function getHistoryMatchesForModel(modelName) {
    const normalized = normalizeModelName(modelName);
    const compact = compactModelName(modelName);
    if (!normalized) {
      return [];
    }

    return (state.history || []).filter((run) => {
      const runName = normalizeModelName(run.model_name);
      const runCompact = compactModelName(run.model_name);
      return (
        runName.includes(normalized) ||
        normalized.includes(runName) ||
        runCompact.includes(compact) ||
        compact.includes(runCompact)
      );
    });
  }

  function renderSearchHistoryMatches(query, matchedModelName = '') {
    if (!searchHistoryMatches) {
      return;
    }

    const lookupValue = matchedModelName || query;
    const matches = getHistoryMatchesForModel(lookupValue);
    if (!query || !matches.length) {
      searchHistoryMatches.hidden = true;
      searchHistoryMatches.innerHTML = '';
      return;
    }

    searchHistoryMatches.hidden = false;
    searchHistoryMatches.innerHTML = `
      <div class="search-history-matches__header">
        <div>
          <div class="search-history-matches__title">Relevant history</div>
          <div class="search-history-matches__subtitle">
            Found ${matches.length} previous run${matches.length === 1 ? '' : 's'} for <strong>${escapeHtml(lookupValue)}</strong>.
          </div>
        </div>
        <button class="btn-secondary" type="button" data-open-history-model="${escapeHtml(lookupValue)}">Open history</button>
      </div>
      <div class="search-history-matches__list">
        ${matches
          .slice(0, 3)
          .map(
            (run) => `
          <button class="search-history-matches__item" type="button" data-history-run-id="${run.id}" data-history-model="${escapeHtml(run.model_name)}">
            <div class="search-history-matches__item-title">${escapeHtml(run.model_name)}</div>
            <div class="search-history-matches__item-meta">
              <span>${escapeHtml(performanceLabel(run.performance_type))}</span>
              <span>${escapeHtml(formatCreatedAt(run.created_at))}</span>
              <span>${formatDuration(run.time_taken_ms)}</span>
            </div>
          </button>
        `
          )
          .join('')}
      </div>
    `;
  }

  function updateDashboardShowcaseVisibility() {
    if (!dashboardShowcase || !dashboardView || dashboardView.hidden) {
      return;
    }
    const hasSearchContext =
      Boolean(searchQuery?.value?.trim()) ||
      (newModelSection && !newModelSection.hidden) ||
      (searchHistoryMatches && !searchHistoryMatches.hidden);
    dashboardShowcase.hidden = hasSearchContext;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...options,
    });
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();
    if (!response.ok) {
      const message = payload?.detail || payload?.message || payload || `Request failed: ${response.status}`;
      throw new Error(message);
    }
    return payload;
  }

  function setAuthMode(mode) {
    state.authMode = mode;
    const isRegister = mode === 'register';
    if (authEmailRow) authEmailRow.hidden = !isRegister;
    if (authSubmitBtn) authSubmitBtn.textContent = isRegister ? 'Create account' : 'Login';
    if (loginModeBtn) loginModeBtn.classList.toggle('is-active', !isRegister);
    if (registerModeBtn) registerModeBtn.classList.toggle('is-active', isRegister);
    if (authStatus) authStatus.textContent = '';
  }

  function renderCapabilities() {
    newModelCapabilities.innerHTML = '';
    primaryTestOptions.forEach((option) => {
      const label = document.createElement('label');
      label.className = 'manager-checkbox';
      label.innerHTML = `<input type="radio" name="manager_test_option" value="${option}" /> <span>${performanceLabel(option)}</span>`;
      newModelCapabilities.appendChild(label);
    });
  }

  function getAdHocSelectedOptions() {
    const selectedInput = newModelCapabilities.querySelector('input[type="radio"]:checked');
    return selectedInput ? [selectedInput.value] : [];
  }

  function buildAdHocModel(nameOverride = '') {
    const name = (nameOverride || newModelName?.value || searchQuery?.value || '').trim();
    return {
      model_key: '__adhoc__',
      name,
      provider: newModelProvider?.value || 'azure',
      available_options: getAdHocSelectedOptions(),
      default_prompt: newModelPrompt?.value?.trim() || '',
      endpoint_url: newModelEndpoint?.value?.trim() || '',
      api_version: newModelApiVersion?.value?.trim() || '',
      builtin: false,
      adHoc: true,
    };
  }

  function setLoggedIn(loggedIn) {
    if (authSection) authSection.hidden = loggedIn;
    if (searchSection) searchSection.hidden = !loggedIn;
    if (logoutBtn) logoutBtn.hidden = !loggedIn;
    if (dashboardView) dashboardView.hidden = !loggedIn || state.activeView !== 'dashboard';
    if (historyView) historyView.hidden = !loggedIn || state.activeView !== 'history';
    if (historySection) historySection.hidden = !loggedIn;
    if (!loggedIn) {
      if (issueSection) issueSection.hidden = true;
      if (latestResultsSection) latestResultsSection.hidden = true;
      if (newModelSection) newModelSection.hidden = true;
      if (searchHistoryMatches) searchHistoryMatches.hidden = true;
    }
    updateDashboardShowcaseVisibility();
  }

  function setActiveView(view) {
    state.activeView = view;
    if (dashboardNav) dashboardNav.classList.toggle('is-active', view === 'dashboard');
    if (historyNav) historyNav.classList.toggle('is-active', view === 'history');
    if (state.user) {
      setLoggedIn(true);
    }
    updateDashboardShowcaseVisibility();
  }

  function renderOverviewStats() {
    const runs = state.history || [];
    const totalRuns = runs.length;
    const successRuns = runs.filter((run) => run.success).length;
    const successRate = totalRuns ? Math.round((successRuns / totalRuns) * 100) : 0;
    const avgMs = totalRuns
      ? Math.round(runs.reduce((sum, run) => sum + (run.time_taken_ms || 0), 0) / totalRuns)
      : 0;
    const latestModel = state.latestResults[0]?.model_name || runs[0]?.model_name || 'No model yet';

    if (totalExtractionsStat) totalExtractionsStat.textContent = String(totalRuns);
    if (successRateStat) successRateStat.textContent = `${successRate}%`;
    if (avgProcessingStat) avgProcessingStat.textContent = `${avgMs} ms`;
    if (latestModelStat) latestModelStat.textContent = latestModel;
  }

  function renderSelectedModel() {
    const model = state.selectedModel;
    if (!model) {
      if (newModelSection) newModelSection.hidden = true;
      return;
    }

    if (newModelName) newModelName.value = model.name || '';
    if (newModelProvider) newModelProvider.value = model.provider || 'azure';
    if (newModelEndpoint) newModelEndpoint.value = model.endpoint_url || '';
    if (newModelApiVersion) newModelApiVersion.value = model.api_version || '';
    if (newModelPrompt) newModelPrompt.value = model.default_prompt || '';
    if (newModelApiKey) newModelApiKey.value = '';
    if (newModelFile) newModelFile.value = '';

    newModelCapabilities.innerHTML = '';
    const options = primaryTestOptions;
    options.forEach((option) => {
      const label = document.createElement('label');
      label.className = 'manager-checkbox';
      label.innerHTML = `<input type="radio" name="manager_test_option" value="${option}" /> <span>${performanceLabel(option)}</span>`;
      newModelCapabilities.appendChild(label);
    });

    if (newModelSection) newModelSection.hidden = false;
    if (newModelStatus) newModelStatus.textContent = '';
  }

  function renderResults() {
    latestResults.innerHTML = '';
    latestResultsSection.hidden = state.latestResults.length === 0;
    state.latestResults.forEach((result) => {
      const card = document.createElement('article');
      card.className = 'manager-result';
      const body = result.output_text
        ? `<pre class="manager-output">${escapeHtml(result.output_text)}</pre>`
        : result.output_json
        ? `<pre class="manager-output">${escapeHtml(prettyJson(result.output_json))}</pre>`
        : '';
      const error = !result.success && result.error_message
        ? `<div class="manager-status manager-status--error">${escapeHtml(result.error_message)}</div>`
        : '';
      card.innerHTML = `
        <div class="manager-result__head">
          <div>
            <strong>${performanceLabel(result.performance_type)}</strong>
            <div class="caption">${escapeHtml(result.model_name)} · ${escapeHtml(result.provider)}</div>
          </div>
          <button class="btn-secondary" type="button" data-share-id="${result.id}">Share</button>
        </div>
        <div class="manager-metrics">
          <span>Time: ${formatDuration(result.time_taken_ms)}</span>
          <span>Confidence: ${formatMetricValue(result.confidence)}</span>
          <span>Accuracy: ${formatMetricValue(result.accuracy)}</span>
        </div>
        ${body}
        ${error}
      `;
      latestResults.appendChild(card);
    });
    renderOverviewStats();
  }

  function renderHistory() {
    const runs = getFilteredHistoryRuns();
    historyList.innerHTML = '';
    historyEmpty.hidden = runs.length > 0;

    const totalRuns = runs.length;
    const successRuns = runs.filter((run) => run.success).length;
    const successRate = totalRuns ? Math.round((successRuns / totalRuns) * 100) : 0;
    const avgMs = totalRuns
      ? Math.round(runs.reduce((sum, run) => sum + (run.time_taken_ms || 0), 0) / totalRuns)
      : 0;
    const totalFields = runs.reduce((sum, run) => sum + getRunFieldCount(run), 0);

    if (historyTotalStat) historyTotalStat.textContent = String(totalRuns);
    if (historySuccessStat) historySuccessStat.textContent = `${successRate}%`;
    if (historyAvgTimeStat) historyAvgTimeStat.textContent = formatDuration(avgMs);
    if (historyFieldsStat) historyFieldsStat.textContent = String(totalFields);

    runs.forEach((run) => {
      const item = document.createElement('article');
      const isExpanded = state.expandedHistoryId === run.id;
      item.className = `manager-history__item${isExpanded ? ' is-expanded' : ''}`;
      const status = getHistoryStatus(run);
      const filename = getRunFilename(run);
      const fieldCount = getRunFieldCount(run);
      const outputPreview = run.output_text
        ? `<pre class="manager-output">${escapeHtml(run.output_text)}</pre>`
        : run.output_json
        ? `<pre class="manager-output">${escapeHtml(prettyJson(run.output_json))}</pre>`
        : `<div class="history-report__empty">No structured output preview is available for this run yet.</div>`;
      const stageCards = getEstimatedStageBreakdown(run)
        .map(
          (stage) => `
            <article class="history-stage-card history-stage-card--${stage.tone}">
              <div class="history-stage-card__head">
                <span class="history-stage-card__icon" aria-hidden="true">${getStageIconSvg(stage.title)}</span>
                <div class="history-stage-card__title">${stage.title}</div>
              </div>
              <div class="history-stage-card__value">${stage.seconds.toFixed(2)}s</div>
              <div class="history-stage-card__note">${stage.note}</div>
              <div class="history-stage-card__bar"></div>
            </article>
          `
        )
        .join('');
      item.innerHTML = `
        <button class="history-summary" type="button" data-history-id="${run.id}" aria-expanded="${isExpanded ? 'true' : 'false'}">
          <div class="history-run">
            <div class="history-run__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <path d="M14 2v6h6"></path>
                <path d="M8 13h8"></path>
                <path d="M8 17h5"></path>
              </svg>
            </div>
            <div class="history-run__meta">
              <div class="history-run__title">${escapeHtml(filename)}</div>
              <div class="history-run__subline">
                <span class="history-pill">${escapeHtml(run.provider)}</span>
                <span class="history-pill">${escapeHtml(performanceLabel(run.performance_type))}</span>
              </div>
              <div class="history-run__subline-secondary">
                <span>${escapeHtml(formatCreatedAt(run.created_at))}</span>
                ${run.error_message ? `<span class="manager-status manager-status--error">${escapeHtml(run.error_message)}</span>` : ''}
              </div>
            </div>
          </div>
          <div class="history-metrics">
            <div class="history-metric">
              <div class="history-metric__label">Time</div>
              <div class="history-metric__value">${formatDuration(run.time_taken_ms)}</div>
            </div>
            <div class="history-metric">
              <div class="history-metric__label">Fields</div>
              <div class="history-metric__value">${fieldCount}</div>
            </div>
            <div class="history-metric">
              <div class="history-metric__label">Confidence</div>
              <div class="history-metric__value">${formatMetricValue(run.confidence)}</div>
            </div>
            <div class="history-metric">
              <div class="history-metric__label">Accuracy</div>
              <div class="history-metric__value">${formatMetricValue(run.accuracy)}</div>
            </div>
            <div class="history-status history-status--${status}">
              ${status === 'completed' ? 'Completed' : 'Failed'}
            </div>
            <span class="history-chevron" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 6l6 6-6 6"></path>
              </svg>
            </span>
          </div>
        </button>
        ${
          isExpanded
            ? `
          <div class="history-report">
            <div class="history-report__header">
              <div class="history-report__title-wrap">
                <span class="history-report__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <path d="M14 2v6h6"></path>
                    <path d="M8 13h8"></path>
                    <path d="M8 17h5"></path>
                  </svg>
                </span>
                <div>
                  <div class="history-report__title">Performance Report</div>
                  <div class="history-report__subtitle">Detailed timing and output view for this execution.</div>
                </div>
              </div>
              <div class="history-report__actions">
                <button class="btn-secondary" type="button" data-view-output="${run.id}">View Output</button>
                <button class="btn-secondary" type="button" data-export-run="${run.id}">Export Report</button>
              </div>
            </div>
            <div class="history-stage-grid">
              ${stageCards}
            </div>
            <div class="history-total-card">
              <div>
                <div class="history-total-card__label">Total Processing Time</div>
                <div class="history-total-card__note">From request start to final output readiness</div>
              </div>
              <div class="history-total-card__value">${formatDuration(run.time_taken_ms)}</div>
            </div>
            <div class="history-report__output" id="history-output-${run.id}" hidden>
              ${outputPreview}
            </div>
          </div>
        `
            : ''
        }
      `;
      historyList.appendChild(item);
    });
    renderOverviewStats();
  }

  function openIssue(option) {
    state.pendingIssue = {
      model_name: state.selectedModel?.name || searchQuery.value.trim(),
      performance_type: option,
    };
    issueContext.textContent = `Model: ${state.pendingIssue.model_name} | Option: ${performanceLabel(option)}`;
    issueEmail.value = state.user?.email || '';
    issueDescription.value = '';
    issueStatus.textContent = '';
    issueSection.hidden = false;
  }

  function closeIssue() {
    state.pendingIssue = null;
    issueSection.hidden = true;
    issueStatus.textContent = '';
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  async function loadHistory() {
    try {
      const data = await api('/api/history');
      state.history = data.runs || [];
    } catch (error) {
      state.history = [];
    }
    renderHistory();
  }

  async function fetchCurrentUser() {
    const data = await api('/api/auth/me');
    state.user = data.user || null;
    setLoggedIn(Boolean(state.user));
    if (state.user) {
      await loadHistory();
    } else {
      window.location.href = '/';
    }
  }

  if (loginModeBtn) loginModeBtn.addEventListener('click', () => setAuthMode('login'));
  if (registerModeBtn) registerModeBtn.addEventListener('click', () => setAuthMode('register'));
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await api('/api/auth/logout', { method: 'POST' });
      window.location.href = '/';
    });
  }

  if (dashboardNav) {
    dashboardNav.addEventListener('click', (event) => {
      event.preventDefault();
      setActiveView('dashboard');
    });
  }

  if (historyNav) {
    historyNav.addEventListener('click', (event) => {
      event.preventDefault();
      setActiveView('history');
      historyView?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  if (authForm) {
    authForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (authStatus) authStatus.textContent = '';
      try {
        const data = await api(`/api/auth/${state.authMode}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: authUsername.value.trim(),
            password: authPassword.value,
            email: authEmail.value.trim() || null,
          }),
        });
        state.user = data.user;
        authForm.reset();
        setLoggedIn(true);
        await loadHistory();
      } catch (error) {
        if (authStatus) authStatus.textContent = String(error.message || error);
      }
    });
  }

  searchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    searchStatus.textContent = '';
    state.selectedModel = null;
    newModelSection.hidden = true;
    renderSearchHistoryMatches('', '');
    updateDashboardShowcaseVisibility();
    try {
      const query = searchQuery.value.trim();
      const data = await api(`/api/models/search?q=${encodeURIComponent(query)}`);
      if (data.exists) {
        state.selectedModel = data.model;
        renderSelectedModel();
        searchStatus.textContent = `Found ${data.model.name}. Enter your credentials and run the test.`;
        renderSearchHistoryMatches(query, data.model.name);
      } else {
        newModelName.value = query;
        state.selectedModel = buildAdHocModel(query);
        newModelSection.hidden = false;
        renderSelectedModel();
        searchStatus.textContent = 'Enter your credentials and run the test.';
        renderSearchHistoryMatches(query, query);
      }
    } catch (error) {
      searchStatus.textContent = String(error.message || error);
    }
    updateDashboardShowcaseVisibility();
  });

  newModelForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    newModelStatus.textContent = '';
    const selectedOptions = getAdHocSelectedOptions();
    const currentQuery = searchQuery?.value?.trim() || '';
    const currentName = newModelName.value.trim() || currentQuery;
    const matchedName =
      state.selectedModel?.name && normalizeModelName(state.selectedModel.name) === normalizeModelName(currentName)
        ? state.selectedModel.name
        : '';
    state.selectedModel = matchedName && state.selectedModel?.model_key !== '__adhoc__'
      ? state.selectedModel
      : buildAdHocModel(currentName);
    if (!currentName) {
      newModelStatus.textContent = 'Enter the model name before continuing.';
      return;
    }
    if (!selectedOptions.length) {
      newModelStatus.textContent = 'Select at least one testing option.';
      return;
    }

    if (newModelRunBtn) {
      newModelRunBtn.disabled = true;
      newModelRunBtn.textContent = 'Running...';
    }
    newModelStatus.textContent = '';

    try {
      const formData = new FormData();
      formData.append('model_key', state.selectedModel.adHoc ? '__adhoc__' : state.selectedModel.model_key);
      formData.append('selected_options_json', JSON.stringify(selectedOptions));
      formData.append('prompt', newModelPrompt.value.trim());
      formData.append('input_text', '');
      formData.append('endpoint_url', newModelEndpoint.value.trim());
      formData.append('api_key', newModelApiKey.value.trim());
      formData.append('api_version', newModelApiVersion.value.trim());
      if (state.selectedModel.adHoc) {
        formData.append('custom_model_name', newModelName.value.trim() || state.selectedModel.name);
        formData.append('custom_provider', newModelProvider.value);
        formData.append('custom_capabilities_json', JSON.stringify(selectedOptions));
        formData.append('custom_default_prompt', newModelPrompt.value.trim());
      }
      if (newModelFile?.files?.[0]) {
        formData.append('file', newModelFile.files[0]);
      }
      const data = await api('/api/execute', {
        method: 'POST',
        body: formData,
      });
      state.latestResults = data.results || [];
      renderResults();
      newModelStatus.textContent = 'Tests completed.';
      await loadHistory();
    } catch (error) {
      newModelStatus.textContent = String(error.message || error);
    } finally {
      if (newModelRunBtn) {
        newModelRunBtn.disabled = false;
        newModelRunBtn.textContent = 'Run evaluation';
      }
    }
  });

  issueForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!state.pendingIssue) {
      return;
    }
    try {
      await api('/api/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_name: state.pendingIssue.model_name,
          performance_type: state.pendingIssue.performance_type,
          email: issueEmail.value.trim(),
          description: issueDescription.value.trim(),
        }),
      });
      issueStatus.textContent = 'Issue submitted successfully.';
    } catch (error) {
      issueStatus.textContent = String(error.message || error);
    }
  });

  if (cancelIssueBtn) cancelIssueBtn.addEventListener('click', closeIssue);

  if (latestResults) {
    latestResults.addEventListener('click', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const shareId = target.getAttribute('data-share-id');
      if (!shareId) {
        return;
      }
      const result = state.latestResults.find((item) => String(item.id) === shareId);
      if (!result) {
        return;
      }
      const payload = JSON.stringify(
        {
          model: result.model_name,
          type: result.performance_type,
          provider: result.provider,
          output_text: result.output_text,
          output_json: result.output_json,
          confidence: result.confidence,
          accuracy: result.accuracy,
          time_taken_ms: result.time_taken_ms,
        },
        null,
        2
      );
      try {
        await navigator.clipboard.writeText(payload);
      } catch (error) {
        if (newModelStatus) {
          newModelStatus.textContent = 'Could not copy result to clipboard.';
        }
      }
    });
  }

  if (historySearch) {
    historySearch.addEventListener('input', renderHistory);
  }

  if (historyStatusFilter) {
    historyStatusFilter.addEventListener('change', renderHistory);
  }

  if (exportHistoryBtn) {
    exportHistoryBtn.addEventListener('click', async () => {
      const runs = getFilteredHistoryRuns().map((run) => ({
        id: run.id,
        file: getRunFilename(run),
        model: run.model_name,
        provider: run.provider,
        type: performanceLabel(run.performance_type),
        created_at: run.created_at,
        time_taken_ms: run.time_taken_ms,
        confidence: run.confidence,
        accuracy: run.accuracy,
        fields_extracted: getRunFieldCount(run),
        success: run.success,
        error_message: run.error_message,
      }));

      const blob = new Blob([JSON.stringify(runs, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'model-testing-history.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });
  }

  if (historyList) {
    historyList.addEventListener('click', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }

      const summaryButton = target.closest('[data-history-id]');
      if (summaryButton instanceof HTMLElement) {
        const runId = Number(summaryButton.getAttribute('data-history-id'));
        state.expandedHistoryId = state.expandedHistoryId === runId ? null : runId;
        renderHistory();
        return;
      }

      const outputButton = target.closest('[data-view-output]');
      if (outputButton instanceof HTMLElement) {
        const runId = outputButton.getAttribute('data-view-output');
        const output = document.getElementById(`history-output-${runId}`);
        if (output) {
          output.hidden = !output.hidden;
        }
        return;
      }

      const exportButton = target.closest('[data-export-run]');
      if (exportButton instanceof HTMLElement) {
        const runId = Number(exportButton.getAttribute('data-export-run'));
        const run = state.history.find((item) => item.id === runId);
        if (!run) {
          return;
        }
        const payload = {
          id: run.id,
          file: getRunFilename(run),
          model: run.model_name,
          provider: run.provider,
          type: performanceLabel(run.performance_type),
          created_at: run.created_at,
          time_taken_ms: run.time_taken_ms,
          confidence: run.confidence,
          accuracy: run.accuracy,
          output_text: run.output_text,
          output_json: run.output_json,
          error_message: run.error_message,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `history-run-${run.id}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }
    });
  }

  if (searchQuery) {
    searchQuery.addEventListener('input', () => {
      const query = searchQuery.value.trim();
      if (!query) {
        if (newModelSection) newModelSection.hidden = true;
        state.selectedModel = null;
        if (searchStatus) searchStatus.textContent = '';
        renderSearchHistoryMatches('', '');
      } else {
        renderSearchHistoryMatches(query, query);
      }
      updateDashboardShowcaseVisibility();
    });
  }

  if (searchHistoryMatches) {
    searchHistoryMatches.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }

      const openButton = target.closest('[data-open-history-model]');
      const itemButton = target.closest('[data-history-model]');
      const modelName = openButton?.getAttribute('data-open-history-model') || itemButton?.getAttribute('data-history-model');
      if (!modelName) {
        return;
      }
      const runId = itemButton?.getAttribute('data-history-run-id');

      if (historySearch) {
        historySearch.value = modelName;
      }
      if (historyStatusFilter) {
        historyStatusFilter.value = 'all';
      }
      state.expandedHistoryId = runId ? Number(runId) : null;
      setActiveView('history');
      renderHistory();
      historyView?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  renderCapabilities();
  setAuthMode('login');
  setActiveView('dashboard');
  renderOverviewStats();
  fetchCurrentUser().catch((error) => {
    if (authStatus) authStatus.textContent = String(error.message || error);
    setLoggedIn(false);
    window.location.href = '/';
  });
});
