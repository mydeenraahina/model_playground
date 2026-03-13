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
  const ocrChoiceCard = document.getElementById('ocrChoiceCard');
  const textToJsonChoiceCard = document.getElementById('textToJsonChoiceCard');
  const summarizeChoiceCard = document.getElementById('summarizeChoiceCard');
  const classifyChoiceCard = document.getElementById('classifyChoiceCard');
  const ocrForm = document.getElementById('ocrForm');
  const ocrResult = document.getElementById('ocrResult');
  const jsonForm = document.getElementById('jsonForm');
  const jsonResult = document.getElementById('jsonResult');
  const summarizeForm = document.getElementById('summarizeForm');
  const summarizeResult = document.getElementById('summarizeResult');
  const classifyForm = document.getElementById('classifyForm');
  const classifyResult = document.getElementById('classifyResult');
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
    // When just showing the 4 cards, hide the back button
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
    if (tryOcrScreen) tryOcrScreen.hidden = false;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showJsonScreen() {
    hideChoiceGrid();
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = false;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showSummarizeScreen() {
    hideChoiceGrid();
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = false;
    if (tryClassifyScreen) tryClassifyScreen.hidden = true;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  function showClassifyScreen() {
    hideChoiceGrid();
    if (tryOcrScreen) tryOcrScreen.hidden = true;
    if (tryJsonScreen) tryJsonScreen.hidden = true;
    if (trySummarizeScreen) trySummarizeScreen.hidden = true;
    if (tryClassifyScreen) tryClassifyScreen.hidden = false;
    if (tryBackBtn) tryBackBtn.style.display = 'inline-block';
    requestAnimationFrame(resizeTryExpansion);
  }
  showChoiceGrid();

  wannaTryBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
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

  // OCR form submit → POST /ocr
  if (ocrForm && ocrResult) {
    ocrForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(ocrForm);
      const file = formData.get('file');
      const modalUrl = formData.get('modal_url');
      const prompt = formData.get('prompt');
      if (!file || !modalUrl || !prompt) {
        ocrResult.textContent = 'Please fill all fields before running OCR.';
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

  // Text to JSON form submit → POST /extract-json
  if (jsonForm && jsonResult) {
    jsonForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = document.getElementById('jsonText').value.trim();
      const prompt = document.getElementById('jsonPrompt').value.trim();
      const modal_url = document.getElementById('jsonModalUrl').value.trim();
      if (!text || !prompt || !modal_url) {
        jsonResult.textContent = 'Please fill all fields.';
        return;
      }
      jsonResult.textContent = 'Extracting JSON...';
      try {
        const response = await fetch('/extract-json', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, prompt, modal_url }),
        });
        if (!response.ok) {
          const errText = await response.text();
          throw new Error(errText || `Request failed with ${response.status}`);
        }
        const data = await response.json();
        jsonResult.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      } catch (error) {
        jsonResult.textContent = `Error: ${error}`;
      }
    });
  }

  // Document Summarization: file input (read .txt into textarea)
  const summarizeFile = document.getElementById('summarizeFile');
  const summarizeDoc = document.getElementById('summarizeDoc');
  if (summarizeFile && summarizeDoc) {
    summarizeFile.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => { summarizeDoc.value = reader.result || ''; };
      reader.readAsText(file);
    });
  }

  // Document Summarization form submit → POST /summarize
  if (summarizeForm && summarizeResult) {
    summarizeForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = document.getElementById('summarizeDoc').value.trim();
      const modal_url = document.getElementById('summarizeModalUrl').value.trim();
      const promptEl = document.getElementById('summarizePrompt');
      const prompt = promptEl && promptEl.value ? promptEl.value.trim() : null;
      if (!text || !modal_url) {
        summarizeResult.textContent = 'Please enter document text and Model URL.';
        return;
      }
      summarizeResult.textContent = 'Summarizing...';
      try {
        const response = await fetch('/summarize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, modal_url, prompt }),
        });
        if (!response.ok) {
          const errText = await response.text();
          throw new Error(errText || `Request failed with ${response.status}`);
        }
        const data = await response.json();
        summarizeResult.textContent = data.summary || '(No summary returned)';
      } catch (error) {
        summarizeResult.textContent = `Error: ${error}`;
      }
    });
  }

  // Document Classification: file input (read .txt into textarea)
  const classifyFile = document.getElementById('classifyFile');
  const classifyDoc = document.getElementById('classifyDoc');
  if (classifyFile && classifyDoc) {
    classifyFile.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => { classifyDoc.value = reader.result || ''; };
      reader.readAsText(file);
    });
  }

  // Document Classification form submit → POST /classify
  if (classifyForm && classifyResult) {
    classifyForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = document.getElementById('classifyDoc').value.trim();
      const modal_url = document.getElementById('classifyModalUrl').value.trim();
      const promptEl = document.getElementById('classifyPrompt');
      const prompt = promptEl && promptEl.value ? promptEl.value.trim() : null;

      if (!text || !modal_url) {
        classifyResult.textContent = 'Please enter document text and Model URL.';
        return;
      }

      classifyResult.textContent = 'Classifying...';
      try {
        const response = await fetch('/classify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, modal_url, prompt }),
        });
        if (!response.ok) {
          const errText = await response.text();
          throw new Error(errText || `Request failed with ${response.status}`);
        }
        const data = await response.json();
        classifyResult.textContent = data.document_type || '(No document type returned)';
      } catch (error) {
        classifyResult.textContent = `Error: ${error}`;
      }
    });
  }
});
