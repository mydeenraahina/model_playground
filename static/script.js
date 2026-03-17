document.addEventListener('DOMContentLoaded', () => {
  // Fade in page once JS is ready
  document.body.classList.add('is-ready');

  const homeHero = document.getElementById('homeHero');
  const modelPage = document.getElementById('modelPage');
  const getStartedBtn = document.getElementById('getStartedBtn');

  if (homeHero && modelPage) {
    const urlParams = new URLSearchParams(window.location.search);
    const showModels = urlParams.get('view') === 'models';
    if (showModels) {
      homeHero.style.display = 'none';
      modelPage.style.display = 'flex';
    } else {
      homeHero.style.display = 'flex';
      modelPage.style.display = 'none';
    }

    if (getStartedBtn) {
      getStartedBtn.addEventListener('click', () => {
        homeHero.style.display = 'none';
        modelPage.style.display = 'flex';
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
  }

  const wannaTryBtns = document.querySelectorAll('.wanna-try-btn');
  const tryBackBtn = document.getElementById('tryBackBtn');
  const tryActions = document.getElementById('tryActions');
  const tryChoiceGrid = document.getElementById('tryChoiceGrid');
  const tryOcrScreen = document.getElementById('tryOcrScreen');
  const tryJsonScreen = document.getElementById('tryJsonScreen');
  const trySummarizeScreen = document.getElementById('trySummarizeScreen');
  const tryClassifyScreen = document.getElementById('tryClassifyScreen');
  const tryChatDocScreen = document.getElementById('tryChatDocScreen');
  const ocrChoiceCard = document.getElementById('ocrChoiceCard');
  const textToJsonChoiceCard = document.getElementById('textToJsonChoiceCard');
  const summarizeChoiceCard = document.getElementById('summarizeChoiceCard');
  const classifyChoiceCard = document.getElementById('classifyChoiceCard');
  const chatDocChoiceCard = document.getElementById('chatDocChoiceCard');
  const ocrForm = document.getElementById('ocrForm');
  const ocrResult = document.getElementById('ocrResult');
  const jsonForm = document.getElementById('jsonForm');
  const jsonResult = document.getElementById('jsonResult');
  const summarizeForm = document.getElementById('summarizeForm');
  const summarizeResult = document.getElementById('summarizeResult');
  const classifyForm = document.getElementById('classifyForm');
  const classifyResult = document.getElementById('classifyResult');
  const chatDocForm = document.getElementById('chatDocForm');
  const chatDocResult = document.getElementById('chatDocResult');
  const tryMain = document.getElementById('tryMain');

  if (!wannaTryBtns.length || !tryActions) {
    return;
  }

  // Start with try panel collapsed
  tryActions.classList.remove('is-open');
  tryActions.style.maxHeight = '0px';

  // Show choice grid, hide all try screens
  function showChoiceGrid() {
    if (tryChoiceGrid) tryChoiceGrid.style.display = 'grid';
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryChatDocScreen) tryChatDocScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'none';
  }
  function hideChoiceGrid() {
    if (tryChoiceGrid) tryChoiceGrid.style.display = 'none';
  }
  function resizeTryExpansion() {
    if (tryActions && tryActions.classList.contains('is-open')) {
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
    }
  }
  function showOcrScreen() {
    hideChoiceGrid();
    updateModelDisplay(getActiveModel());
    if (tryOcrScreen) tryOcrScreen.hidden = false;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryChatDocScreen) tryChatDocScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showJsonScreen() {
    hideChoiceGrid();
    updateModelDisplay(getActiveModel());
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = false;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryChatDocScreen) tryChatDocScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showSummarizeScreen() {
    hideChoiceGrid();
    updateModelDisplay(getActiveModel());
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = false;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryChatDocScreen) tryChatDocScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showClassifyScreen() {
    hideChoiceGrid();
    updateModelDisplay(getActiveModel());
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = false;
    if (tryChatDocScreen) tryChatDocScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showChatDocScreen() {
    hideChoiceGrid();
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryChatDocScreen) tryChatDocScreen.hidden = false;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  showChoiceGrid();

  const MODEL_NAMES = {
    'ezofis': 'EZOFIS-VL-8B-Instruct',
    'qwen': 'Qwen-3-VL-8B-Thinking',
    'gpt4o-mini': 'GPT-4o-mini',
    'hunyuan': 'Hunyuan',
    'gpt41': 'GPT-4.1'
  };

  const MODEL_FILE_ACCEPT = {
    'ezofis': '.pdf',
    'qwen': '.pdf',
    'gpt4o-mini': '.pdf,.docx,.xlsx,.xls,.md,.txt',
    'hunyuan': '.pdf',
    'gpt41': '.pdf,.docx,.xlsx,.xls,.md,.txt'
  };
  let activeModel = 'ezofis';

  function getActiveModel() {
    return (tryActions && tryActions.dataset.activeModel) || activeModel || 'ezofis';
  }

  function setActiveModel(modelId) {
    activeModel = modelId || 'ezofis';
    if (tryActions) {
      tryActions.dataset.activeModel = activeModel;
    }
    updateModelDisplay(activeModel);
  }

  function updateModelDisplay(modelId) {
    const name = MODEL_NAMES[modelId] || modelId;
    const modelInputs = ['ocr', 'json', 'summarize', 'classify'];
    modelInputs.forEach(prefix => {
      const nameEl = document.getElementById(prefix + 'ModelName');
      const inputEl = document.getElementById(prefix + 'Model');
      if (nameEl) nameEl.textContent = name;
      if (inputEl) inputEl.value = modelId || 'ezofis';
    });
    toggleModelUrlRows();
    updateAcceptedFileTypes(modelId);
    toggleChatActions(modelId);
  }

  function toggleModelUrlRows() {
    const model = document.getElementById('ocrModel')?.value || 'ezofis';
    const isAzureModel = model === 'gpt4o-mini' || model === 'gpt41';
    const urlRows = ['ocrModalUrlRow', 'jsonModalUrlRow', 'summarizeModalUrlRow', 'classifyModalUrlRow'];
    const azureRows = ['ocrAzureRow', 'ocrAzureKeyRow', 'jsonAzureRow', 'jsonAzureKeyRow', 'summarizeAzureRow', 'summarizeAzureKeyRow', 'classifyAzureRow', 'classifyAzureKeyRow'];
    urlRows.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = isAzureModel ? 'none' : '';
    });
    azureRows.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = isAzureModel ? '' : 'none';
    });
  }

  function toggleChatActions(modelId) {
    const showChat = modelId === 'gpt4o-mini';
    if (chatDocChoiceCard) {
      chatDocChoiceCard.style.display = showChat ? '' : 'none';
    }
    document.querySelectorAll('[data-action="chat"]').forEach(card => {
      card.style.display = showChat ? '' : 'none';
    });
    if (!showChat && tryChatDocScreen) {
      tryChatDocScreen.hidden = true;
    }
  }

  function updateAcceptedFileTypes(modelId) {
    const accept = MODEL_FILE_ACCEPT[modelId] || MODEL_FILE_ACCEPT['ezofis'];
    ['ocrFile', 'jsonPdfFile', 'summarizePdfFile', 'classifyPdfFile'].forEach(id => {
      const input = document.getElementById(id);
      if (input) input.setAttribute('accept', accept);
    });
  }

  setActiveModel('ezofis');

  wannaTryBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
    const card = btn.closest('.model-card');
    const cardModel = card ? card.dataset.model : null;
    if (cardModel) setActiveModel(cardModel);

    const isTryOpen = tryActions.classList.contains('is-open');

    if (isTryOpen) {
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
      void tryActions.offsetHeight;
      tryActions.classList.remove('is-open');
      tryActions.style.maxHeight = '0px';
      document.querySelectorAll('.model-card').forEach((c) => { c.style.display = ''; });
      const header = document.querySelector('.header');
      if (header) header.style.display = '';
    } else {
      document.querySelectorAll('.model-card').forEach((c) => { c.style.display = 'none'; });
      const header = document.querySelector('.header');
      if (header) header.style.display = 'none';
      showChoiceGrid();
      tryActions.classList.add('is-open');
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
    }
  });
  });

  // Back button: return to model card view
  if (tryBackBtn) {
    tryBackBtn.addEventListener('click', () => {
      document.querySelectorAll('.model-card').forEach((c) => { c.style.display = ''; });
      const header = document.querySelector('.header');
      if (header) header.style.display = '';
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
      void tryActions.offsetHeight;
      tryActions.classList.remove('is-open');
      tryActions.style.maxHeight = '0px';
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Choice grid: OCR card → show OCR screen
  if (ocrChoiceCard && tryOcrScreen && tryMain) {
    ocrChoiceCard.addEventListener('click', () => {
      showOcrScreen();
      tryMain.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // Choice grid: Text to JSON card → show Text to JSON screen
  if (textToJsonChoiceCard && tryJsonScreen) {
    textToJsonChoiceCard.addEventListener('click', () => {
      showJsonScreen();
      tryJsonScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // Choice grid: Document Summarization card → show Summarize screen
  if (summarizeChoiceCard && trySummarizeScreen) {
    summarizeChoiceCard.addEventListener('click', () => {
      showSummarizeScreen();
      trySummarizeScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // Choice grid: Document Classification card → show Classification screen
  if (classifyChoiceCard && tryClassifyScreen) {
    classifyChoiceCard.addEventListener('click', () => {
      showClassifyScreen();
      tryClassifyScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // Choice grid: Chat with Document card → show Chat screen
  if (chatDocChoiceCard && tryChatDocScreen) {
    chatDocChoiceCard.addEventListener('click', () => {
      showChatDocScreen();
      tryChatDocScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // No back / switch buttons now – click cards to change tools

  // Right-side action cards (shown on all try screens)
  const ocrInfoCards = document.querySelectorAll('[data-action="ocr"]');
  const textToJsonInfoCards = document.querySelectorAll('[data-action="json"]');
  const summarizeInfoCards = document.querySelectorAll('[data-action="summarize"]');
  const classifyInfoCards = document.querySelectorAll('[data-action="classify"]');

  if (ocrInfoCards.length && ocrForm) {
    ocrInfoCards.forEach((card) => {
      card.addEventListener('click', () => {
        showOcrScreen();
        if (tryMain) {
          tryMain.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        const firstInput = ocrForm.querySelector('input');
        if (firstInput) firstInput.focus();
      });
    });
  }

  if (textToJsonInfoCards.length) {
    textToJsonInfoCards.forEach((card) => {
      card.addEventListener('click', () => {
        showJsonScreen();
        if (tryJsonScreen) {
          tryJsonScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }

  if (summarizeInfoCards.length) {
    summarizeInfoCards.forEach((card) => {
      card.addEventListener('click', () => {
        showSummarizeScreen();
        if (trySummarizeScreen) {
          trySummarizeScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }

  if (classifyInfoCards.length) {
    classifyInfoCards.forEach((card) => {
      card.addEventListener('click', () => {
        showClassifyScreen();
        if (tryClassifyScreen) {
          tryClassifyScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }

  const chatInfoCards = document.querySelectorAll('[data-action="chat"]');
  if (chatInfoCards.length && tryChatDocScreen) {
    chatInfoCards.forEach((card) => {
      card.addEventListener('click', () => {
        showChatDocScreen();
        tryChatDocScreen.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  // OCR form submit → POST /ocr
  if (ocrForm && ocrResult) {
    ocrForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(ocrForm);
      const file = formData.get('file');
      const modalUrl = formData.get('modal_url');
      const prompt = formData.get('prompt');
      const azureEndpoint = formData.get('azure_endpoint');
      const azureApiKey = formData.get('azure_api_key');
      const model = formData.get('model') || getActiveModel();
      const needsUrl = model !== 'gpt4o-mini' && model !== 'gpt41';
      const needsAzure = model === 'gpt4o-mini' || model === 'gpt41';
      if (!file || !prompt) {
        ocrResult.textContent = 'Please fill file and prompt.';
        return;
      }
      if (needsAzure && (!azureEndpoint || !azureApiKey)) {
        ocrResult.textContent = 'Azure Endpoint and API Key are required for GPT-4o-mini or GPT-4.1.';
        return;
      }
      if (needsUrl && !modalUrl) {
        ocrResult.textContent = 'Model URL is required for EZOFIS, Qwen, or Hunyuan.';
        return;
      }
      ocrResult.textContent = 'Running OCR via backend...';
      try {
        const response = await fetch('/ocr', { method: 'POST', body: formData });
        if (!response.ok) {
          const text = await response.text();
          throw new Error(text || `Request failed with ${response.status}`);
        }
        const data = await response.json();
        ocrResult.textContent = data.text || '(No text returned from OCR service)';
      } catch (error) {
        ocrResult.textContent = `Error running OCR: ${error}`;
      }
    });
  }

  // Text to JSON form submit
  if (jsonForm && jsonResult) {
    jsonForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const jsonModel = document.getElementById('jsonModel')?.value || getActiveModel();
      const text = document.getElementById('jsonText').value.trim();
      const prompt = document.getElementById('jsonPrompt').value.trim();
      const modal_url = document.getElementById('jsonModalUrl').value.trim();
      const pdfFile = document.getElementById('jsonPdfFile')?.files?.[0];

      if (!prompt) {
        jsonResult.textContent = 'Please fill prompt.';
        return;
      }
      const needsUrl = jsonModel !== 'gpt4o-mini' && jsonModel !== 'gpt41';
      const needsAzure = jsonModel === 'gpt4o-mini' || jsonModel === 'gpt41';
      if (needsUrl && !modal_url) {
        jsonResult.textContent = 'Model URL is required for EZOFIS, Qwen, or Hunyuan.';
        return;
      }
      if (needsAzure) {
        const azureEp = document.getElementById('jsonAzureEndpoint')?.value?.trim();
        const azureKey = document.getElementById('jsonAzureKey')?.value?.trim();
        if (!azureEp || !azureKey) {
          jsonResult.textContent = 'Azure Endpoint and API Key are required for GPT-4o-mini or GPT-4.1.';
          return;
        }
      }
      if (pdfFile) {
        const formData = new FormData();
        formData.append('file', pdfFile);
        formData.append('prompt', prompt);
        formData.append('model', jsonModel);
        if (jsonModel === 'gpt4o-mini' || jsonModel === 'gpt41') {
          formData.append('azure_endpoint', document.getElementById('jsonAzureEndpoint')?.value?.trim() || '');
          formData.append('azure_api_key', document.getElementById('jsonAzureKey')?.value?.trim() || '');
        } else {
          formData.append('modal_url', modal_url);
        }
        jsonResult.textContent = `Extracting JSON from PDF (${jsonModel})...`;
        try {
          const response = await fetch('/extract-json-from-pdf', { method: 'POST', body: formData });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          jsonResult.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        } catch (error) {
          jsonResult.textContent = `Error: ${error}`;
        }
      } else {
        if (!text) {
          jsonResult.textContent = (jsonModel === 'gpt4o-mini' || jsonModel === 'gpt41') ? 'Paste text or upload a file.' : 'Paste text or upload a PDF.';
          return;
        }
        jsonResult.textContent = 'Extracting JSON...';
        try {
          const body = { text, prompt, modal_url: modal_url || '', model: jsonModel };
          if (jsonModel === 'gpt4o-mini' || jsonModel === 'gpt41') {
            body.azure_endpoint = document.getElementById('jsonAzureEndpoint')?.value?.trim() || '';
            body.azure_api_key = document.getElementById('jsonAzureKey')?.value?.trim() || '';
          }
          const response = await fetch('/extract-json', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          jsonResult.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        } catch (error) {
          jsonResult.textContent = `Error: ${error}`;
        }
      }
    });
  }

  const summarizeDoc = document.getElementById('summarizeDoc');

  // Document Summarization form submit
  if (summarizeForm && summarizeResult) {
    summarizeForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const summarizeModel = document.getElementById('summarizeModel')?.value || getActiveModel();
      const text = document.getElementById('summarizeDoc').value.trim();
      const modal_url = document.getElementById('summarizeModalUrl').value.trim();
      const promptEl = document.getElementById('summarizePrompt');
      const prompt = promptEl && promptEl.value ? promptEl.value.trim() : null;
      const pdfFile = document.getElementById('summarizePdfFile')?.files?.[0];

      const needsUrl = summarizeModel !== 'gpt4o-mini' && summarizeModel !== 'gpt41';
      const needsAzure = summarizeModel === 'gpt4o-mini' || summarizeModel === 'gpt41';
      if (needsUrl && !modal_url) {
        summarizeResult.textContent = 'Please enter Model URL.';
        return;
      }
      if (needsAzure) {
        const azureEp = document.getElementById('summarizeAzureEndpoint')?.value?.trim();
        const azureKey = document.getElementById('summarizeAzureKey')?.value?.trim();
        if (!azureEp || !azureKey) {
          summarizeResult.textContent = 'Azure Endpoint and API Key are required for GPT-4o-mini or GPT-4.1.';
          return;
        }
      }
      if (pdfFile) {
        const formData = new FormData();
        formData.append('file', pdfFile);
        formData.append('model', summarizeModel);
        if (modal_url) formData.append('modal_url', modal_url);
        if (prompt) formData.append('prompt', prompt);
        if (summarizeModel === 'gpt4o-mini' || summarizeModel === 'gpt41') {
          formData.append('azure_endpoint', document.getElementById('summarizeAzureEndpoint')?.value?.trim() || '');
          formData.append('azure_api_key', document.getElementById('summarizeAzureKey')?.value?.trim() || '');
        }
        summarizeResult.textContent = `Summarizing (${summarizeModel})...`;
        try {
          const response = await fetch('/summarize-from-pdf', { method: 'POST', body: formData });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          summarizeResult.textContent = data.summary || '(No summary returned)';
        } catch (error) {
          summarizeResult.textContent = `Error: ${error}`;
        }
      } else {
        if (!text) {
          summarizeResult.textContent = (summarizeModel === 'gpt4o-mini' || summarizeModel === 'gpt41') ? 'Paste text or upload a file.' : 'Paste text or upload a PDF.';
          return;
        }
        summarizeResult.textContent = 'Summarizing...';
        try {
          const body = { text, modal_url, prompt, model: summarizeModel };
          if (summarizeModel === 'gpt4o-mini' || summarizeModel === 'gpt41') {
            body.azure_endpoint = document.getElementById('summarizeAzureEndpoint')?.value?.trim() || '';
            body.azure_api_key = document.getElementById('summarizeAzureKey')?.value?.trim() || '';
          }
          const response = await fetch('/summarize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          summarizeResult.textContent = data.summary || '(No summary returned)';
        } catch (error) {
          summarizeResult.textContent = `Error: ${error}`;
        }
      }
    });
  }

  const classifyDoc = document.getElementById('classifyDoc');

  // Document Classification form submit
  if (classifyForm && classifyResult) {
    classifyForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const classifyModel = document.getElementById('classifyModel')?.value || getActiveModel();
      const text = document.getElementById('classifyDoc').value.trim();
      const modal_url = document.getElementById('classifyModalUrl').value.trim();
      const promptEl = document.getElementById('classifyPrompt');
      const prompt = promptEl && promptEl.value ? promptEl.value.trim() : null;
      const pdfFile = document.getElementById('classifyPdfFile')?.files?.[0];

      const needsUrl = classifyModel !== 'gpt4o-mini' && classifyModel !== 'gpt41';
      const needsAzure = classifyModel === 'gpt4o-mini' || classifyModel === 'gpt41';
      if (needsUrl && !modal_url) {
        classifyResult.textContent = 'Please enter Model URL.';
        return;
      }
      if (needsAzure) {
        const azureEp = document.getElementById('classifyAzureEndpoint')?.value?.trim();
        const azureKey = document.getElementById('classifyAzureKey')?.value?.trim();
        if (!azureEp || !azureKey) {
          classifyResult.textContent = 'Azure Endpoint and API Key are required for GPT-4o-mini or GPT-4.1.';
          return;
        }
      }
      if (pdfFile) {
        const formData = new FormData();
        formData.append('file', pdfFile);
        formData.append('model', classifyModel);
        if (modal_url) formData.append('modal_url', modal_url);
        if (prompt) formData.append('prompt', prompt);
        if (classifyModel === 'gpt4o-mini' || classifyModel === 'gpt41') {
          formData.append('azure_endpoint', document.getElementById('classifyAzureEndpoint')?.value?.trim() || '');
          formData.append('azure_api_key', document.getElementById('classifyAzureKey')?.value?.trim() || '');
        }
        classifyResult.textContent = `Classifying (${classifyModel})...`;
        try {
          const response = await fetch('/classify-from-pdf', { method: 'POST', body: formData });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          classifyResult.textContent = data.document_type || '(No result returned)';
        } catch (error) {
          classifyResult.textContent = `Error: ${error}`;
        }
      } else {
        if (!text) {
          classifyResult.textContent = (classifyModel === 'gpt4o-mini' || classifyModel === 'gpt41') ? 'Paste text or upload a file.' : 'Paste text or upload a PDF.';
          return;
        }
        classifyResult.textContent = 'Classifying...';
        try {
          const body = { text, modal_url, prompt, model: classifyModel };
          if (classifyModel === 'gpt4o-mini' || classifyModel === 'gpt41') {
            body.azure_endpoint = document.getElementById('classifyAzureEndpoint')?.value?.trim() || '';
            body.azure_api_key = document.getElementById('classifyAzureKey')?.value?.trim() || '';
          }
          const response = await fetch('/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
          const data = await response.json();
          classifyResult.textContent = data.document_type || '(No document type returned)';
        } catch (error) {
          classifyResult.textContent = `Error: ${error}`;
        }
      }
    });
  }

  // Chat with Document form submit
  if (chatDocForm && chatDocResult) {
    chatDocForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(chatDocForm);
      const file = formData.get('file');
      const prompt = formData.get('prompt');
      if (!file || !prompt) {
        chatDocResult.textContent = 'Please select a file and enter your question.';
        return;
      }
      chatDocResult.textContent = 'Asking...';
      try {
        const response = await fetch('/chat-with-document', { method: 'POST', body: formData });
        if (!response.ok) throw new Error((await response.text()) || `Request failed ${response.status}`);
        const data = await response.json();
        chatDocResult.textContent = data.answer || '(No answer returned)';
      } catch (error) {
        chatDocResult.textContent = `Error: ${error}`;
      }
    });
  }
});
