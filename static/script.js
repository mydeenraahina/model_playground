document.addEventListener('DOMContentLoaded', () => {
  // Fade in page once JS is ready
  document.body.classList.add('is-ready');

  const homeHero = document.getElementById('homeHero');
  const modelPage = document.getElementById('modelPage');
  const getStartedBtn = document.getElementById('getStartedBtn');

  if (homeHero && modelPage) {
    // Show hero first, hide model page
    homeHero.style.display = 'flex';
    modelPage.style.display = 'none';

    if (getStartedBtn) {
      getStartedBtn.addEventListener('click', () => {
        homeHero.style.display = 'none';
        modelPage.style.display = 'flex';
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
  }

  const viewDetailsBtn = document.getElementById('viewDetailsBtn');
  const wannaTryBtn = document.getElementById('wannaTryBtn');
  const carDetails = document.getElementById('carDetails');
  const tryActions = document.getElementById('tryActions');
  const ocrButton = document.getElementById('ocrActionBtn');
  const ocrForm = document.getElementById('ocrForm');
  const ocrResult = document.getElementById('ocrResult');
  const tryMain = document.getElementById('tryMain');

  if (!viewDetailsBtn || !wannaTryBtn || !carDetails || !tryActions) {
    return;
  }

  // Start with everything collapsed (animated using .expansion styles)
  carDetails.classList.remove('is-open');
  tryActions.classList.remove('is-open');
  carDetails.style.maxHeight = '0px';
  tryActions.style.maxHeight = '0px';

  // Hide OCR inputs until the user clicks the OCR button
  if (ocrForm) {
    ocrForm.style.display = 'none';
  }
  if (ocrResult) {
    ocrResult.style.display = 'none';
  }

  viewDetailsBtn.addEventListener('click', () => {
    const isDetailsOpen = carDetails.classList.contains('is-open');

    if (isDetailsOpen) {
      // Clicking again closes it
      carDetails.style.maxHeight = carDetails.scrollHeight + 'px';
      void carDetails.offsetHeight;
      carDetails.classList.remove('is-open');
      carDetails.style.maxHeight = '0px';
      viewDetailsBtn.querySelector('.btn-label').textContent = 'View more details';
    } else {
      // Open details and close try actions
      carDetails.classList.add('is-open');
      carDetails.style.maxHeight = carDetails.scrollHeight + 'px';
       viewDetailsBtn.querySelector('.btn-label').textContent = 'View less';

      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
      void tryActions.offsetHeight;
      tryActions.classList.remove('is-open');
      tryActions.style.maxHeight = '0px';
    }
  });

  wannaTryBtn.addEventListener('click', () => {
    const isTryOpen = tryActions.classList.contains('is-open');

    if (isTryOpen) {
      // Clicking again closes it
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
      void tryActions.offsetHeight;
      tryActions.classList.remove('is-open');
      tryActions.style.maxHeight = '0px';
    } else {
      // Open try actions and close details
      tryActions.classList.add('is-open');
      tryActions.style.maxHeight = tryActions.scrollHeight + 'px';

      carDetails.style.maxHeight = carDetails.scrollHeight + 'px';
      void carDetails.offsetHeight;
      carDetails.classList.remove('is-open');
      carDetails.style.maxHeight = '0px';
      viewDetailsBtn.querySelector('.btn-label').textContent = 'View more details';
    }
  });

  // Wire OCR form to FastAPI backend in app.py
  if (ocrButton && ocrForm && ocrResult) {
    ocrButton.addEventListener('click', () => {
      // Make sure the try panel is visible
      if (!tryActions.classList.contains('is-open')) {
        tryActions.classList.add('is-open');
        tryActions.style.maxHeight = tryActions.scrollHeight + 'px';
        carDetails.style.maxHeight = carDetails.scrollHeight + 'px';
        void carDetails.offsetHeight;
        carDetails.classList.remove('is-open');
        carDetails.style.maxHeight = '0px';
        viewDetailsBtn.querySelector('.btn-label').textContent = 'View more details';
      }

      // Now show only the OCR inputs/results area
      ocrForm.style.display = 'grid';
      ocrResult.style.display = 'block';

      const target = tryMain || ocrForm;
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

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
        const response = await fetch('/ocr', {
          method: 'POST',
          body: formData,
        });

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
});
