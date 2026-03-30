/**
 * StyleLock AI - Frontend Application v51
 * 
 * Organization:
 * 1. State
 * 2. DOM References
 * 3. Screen Navigation
 * 4. Action Sheet
 * 5. Image Handling
 * 6. API Calls
 * 7. Progress Animation
 * 8. Render Functions
 * 9. Event Listeners
 * 10. Initialization
 */

// =============================================================================
// 1. STATE
// =============================================================================

const state = {
  currentScreen: 'home',
  userImageBase64: null,
  looks: [],
  selectedLook: null,
  isLoading: false
};

// =============================================================================
// 2. DOM REFERENCES
// =============================================================================

const dom = {
  // Screens
  screens: {
    home: document.getElementById('screen-home'),
    upload: document.getElementById('screen-upload'),
    loading: document.getElementById('screen-loading'),
    results: document.getElementById('screen-results'),
    cutcard: document.getElementById('screen-cutcard'),
    barber: document.getElementById('screen-barber')
  },
  
  // Home
  homeUnlockBtn: document.getElementById('home-unlock-btn'),
  
  // Upload
  uploadFrameBtn: document.getElementById('upload-frame-btn'),
  uploadTakeBtn: document.getElementById('upload-take-btn'),
  uploadPreviewContainer: document.getElementById('upload-preview-container'),
  uploadPreview: document.getElementById('upload-preview'),
  cameraInput: document.getElementById('camera-input'),
  libraryInput: document.getElementById('library-input'),
  fileInput: document.getElementById('file-input'),
  
  // Action Sheet
  actionSheet: document.getElementById('action-sheet'),
  photoLibraryBtn: document.getElementById('photo-library-btn'),
  takePhotoBtn: document.getElementById('take-photo-btn'),
  chooseFileBtn: document.getElementById('choose-file-btn'),
  cancelSheetBtn: document.getElementById('cancel-sheet-btn'),
  
  // Loading
  loadingSelfie: document.getElementById('loading-selfie'),
  progressFill: document.getElementById('progress-fill'),
  
  // Results
  resultsSwiper: document.getElementById('results-swiper'),
  resultsDots: document.getElementById('results-dots'),
  
  // Cut Card
  cutcardContent: document.getElementById('cutcard-content'),
  
  // Barber
  barberContent: document.getElementById('barber-content'),
  barberClose: document.getElementById('barber-close')
};

// =============================================================================
// 3. SCREEN NAVIGATION
// =============================================================================

function showScreen(screenName) {
  // Hide all screens
  Object.values(dom.screens).forEach(screen => {
    if (screen) screen.classList.remove('active');
  });
  
  // Show target screen
  const targetScreen = dom.screens[screenName];
  if (targetScreen) {
    targetScreen.classList.add('active');
    state.currentScreen = screenName;
  }
  
  console.log(`Screen: ${screenName}`);
}

// =============================================================================
// 4. ACTION SHEET
// =============================================================================

function showActionSheet() {
  if (dom.actionSheet) {
    dom.actionSheet.classList.add('visible');
  }
}

function hideActionSheet() {
  if (dom.actionSheet) {
    dom.actionSheet.classList.remove('visible');
  }
}

// =============================================================================
// 5. IMAGE HANDLING
// =============================================================================

function handleImageSelection(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  
  hideActionSheet();
  
  const reader = new FileReader();
  reader.onload = (e) => {
    state.userImageBase64 = e.target.result;
    
    // Show preview
    if (dom.uploadPreview) {
      dom.uploadPreview.src = state.userImageBase64;
    }
    if (dom.uploadPreviewContainer) {
      dom.uploadPreviewContainer.classList.add('visible');
    }
    
    // Transition to loading after brief delay
    setTimeout(() => {
      startProcessing();
    }, 800);
  };
  
  reader.readAsDataURL(file);
}

// =============================================================================
// 6. API CALLS
// =============================================================================

async function handlePayment() {
  try {
    const response = await fetch('/api/create-order', { method: 'POST' });
    const data = await response.json();
    
    if (data.demo) {
      // Demo mode - skip payment
      showScreen('upload');
      return;
    }
    
    // Real payment with Razorpay
    const options = {
      key: data.key_id,
      amount: data.amount,
      currency: data.currency,
      name: 'StyleLock',
      description: 'Unlock Your 3 Looks',
      order_id: data.order_id,
      handler: function(response) {
        // Payment successful
        showScreen('upload');
      },
      theme: {
        color: '#c8e64a'
      }
    };
    
    const rzp = new Razorpay(options);
    rzp.open();
    
  } catch (error) {
    console.error('Payment error:', error);
    // Fallback to upload screen
    showScreen('upload');
  }
}

async function generateLooks() {
  try {
    const response = await fetch('/api/generate-looks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: state.userImageBase64 })
    });
    
    const data = await response.json();
    
    if (data.success && data.looks) {
      return data.looks;
    } else {
      throw new Error(data.error || 'Failed to generate looks');
    }
    
  } catch (error) {
    console.error('Generate looks error:', error);
    // Return fallback looks
    return getFallbackLooks();
  }
}

function getFallbackLooks() {
  return [
    {
      name: 'BOLD',
      image: '/static/images/hairstyle_bold.jpg',
      top_length: '3 inches',
      sides: '0.5 fade',
      texture: 'textured',
      products: 'matte clay'
    },
    {
      name: 'CLEAN',
      image: '/static/images/hairstyle_clean.jpg',
      top_length: '2 inches',
      sides: 'skin fade',
      texture: 'smooth',
      products: 'pomade'
    },
    {
      name: 'TRENDING',
      image: '/static/images/hairstyle_trending.jpg',
      top_length: '4 inches',
      sides: '1 guard',
      texture: 'wavy',
      products: 'sea salt spray'
    }
  ];
}

// =============================================================================
// 7. PROGRESS ANIMATION
// =============================================================================

function animateProgress(fromPercent, toPercent, duration) {
  return new Promise(resolve => {
    const startTime = performance.now();
    const startValue = parseFloat(fromPercent);
    const endValue = parseFloat(toPercent);
    
    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Ease-out curve
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const currentValue = startValue + (endValue - startValue) * easeOut;
      
      if (dom.progressFill) {
        dom.progressFill.style.width = `${currentValue}%`;
      }
      
      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        resolve();
      }
    }
    
    requestAnimationFrame(update);
  });
}

async function startProcessing() {
  // Show loading screen with user's selfie
  if (dom.loadingSelfie && state.userImageBase64) {
    dom.loadingSelfie.src = state.userImageBase64;
  }
  
  showScreen('loading');
  
  // Reset progress
  if (dom.progressFill) {
    dom.progressFill.style.width = '0%';
  }
  
  state.isLoading = true;
  
  try {
    // Phase 1: Analyzing (0% -> 30%)
    await animateProgress(0, 30, 1500);
    
    // Phase 2: Call API (30% -> 70%)
    const looksPromise = generateLooks();
    await animateProgress(30, 70, 2000);
    
    // Wait for API response
    state.looks = await looksPromise;
    
    // Phase 3: Finalizing (70% -> 100%)
    await animateProgress(70, 100, 1000);
    
    // Small delay before showing results
    await delay(300);
    
    // Show results
    renderResults();
    showScreen('results');
    
  } catch (error) {
    console.error('Processing error:', error);
    
    // Use fallback looks
    state.looks = getFallbackLooks();
    await animateProgress(70, 100, 500);
    
    renderResults();
    showScreen('results');
    
  } finally {
    state.isLoading = false;
  }
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// =============================================================================
// 8. RENDER FUNCTIONS
// =============================================================================

function renderResults() {
  if (!dom.resultsSwiper || !dom.resultsDots) return;
  
  // Render slides
  dom.resultsSwiper.innerHTML = state.looks.map((look, index) => `
    <div class="result-slide" data-index="${index}">
      <div class="result-card">
        <div class="result-card-image">
          <img src="${look.image}" alt="${look.name}">
          <div class="result-style-name">${look.name}</div>
        </div>
        <div class="result-specs">
          <div class="result-spec">
            <div class="result-spec-label">Top</div>
            <div class="result-spec-value">${look.top_length}</div>
          </div>
          <div class="result-spec">
            <div class="result-spec-label">Sides</div>
            <div class="result-spec-value">${look.sides}</div>
          </div>
          <div class="result-spec">
            <div class="result-spec-label">Texture</div>
            <div class="result-spec-value">${look.texture}</div>
          </div>
          <div class="result-spec">
            <div class="result-spec-label">Products</div>
            <div class="result-spec-value">${look.products}</div>
          </div>
        </div>
        <button class="result-cta" onclick="selectLook(${index})">Select This Look</button>
      </div>
    </div>
  `).join('');
  
  // Render dots
  dom.resultsDots.innerHTML = state.looks.map((_, index) => `
    <div class="dot ${index === 0 ? 'active' : ''}" data-index="${index}"></div>
  `).join('');
  
  // Setup scroll listener for dots
  setupResultsScrollListener();
}

function setupResultsScrollListener() {
  if (!dom.resultsSwiper) return;
  
  dom.resultsSwiper.addEventListener('scroll', () => {
    const scrollLeft = dom.resultsSwiper.scrollLeft;
    const slideWidth = dom.resultsSwiper.offsetWidth;
    const activeIndex = Math.round(scrollLeft / slideWidth);
    
    // Update dots
    document.querySelectorAll('.results-dots .dot').forEach((dot, index) => {
      dot.classList.toggle('active', index === activeIndex);
    });
  });
}

function selectLook(index) {
  state.selectedLook = state.looks[index];
  renderCutCard();
  showScreen('cutcard');
}

function renderCutCard() {
  if (!dom.cutcardContent || !state.selectedLook) return;
  
  const look = state.selectedLook;
  const today = new Date().toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
  
  dom.cutcardContent.innerHTML = `
    <div class="cutcard-header">
      <div class="cutcard-logo">STYLELOCK</div>
      <div class="cutcard-date">${today}</div>
    </div>
    <div class="cutcard-style-name">${look.name}</div>
    <div class="cutcard-specs">
      <div class="cutcard-spec">
        <div class="cutcard-spec-label">Top</div>
        <div class="cutcard-spec-value">${look.top_length}</div>
      </div>
      <div class="cutcard-spec">
        <div class="cutcard-spec-label">Sides</div>
        <div class="cutcard-spec-value">${look.sides}</div>
      </div>
      <div class="cutcard-spec">
        <div class="cutcard-spec-label">Texture</div>
        <div class="cutcard-spec-value">${look.texture}</div>
      </div>
      <div class="cutcard-spec">
        <div class="cutcard-spec-label">Products</div>
        <div class="cutcard-spec-value">${look.products}</div>
      </div>
    </div>
    <button class="cutcard-barber-btn" onclick="showBarberMode()">Barber Mode</button>
  `;
}

function showBarberMode() {
  renderBarberMode();
  showScreen('barber');
}

function renderBarberMode() {
  if (!dom.barberContent || !state.selectedLook) return;
  
  const look = state.selectedLook;
  
  dom.barberContent.innerHTML = `
    <div class="barber-image">
      <img src="${look.image}" alt="${look.name}">
    </div>
    <div class="barber-specs">
      <div class="barber-spec">
        <div class="barber-spec-label">Top Length</div>
        <div class="barber-spec-value">${look.top_length}</div>
      </div>
      <div class="barber-spec">
        <div class="barber-spec-label">Sides</div>
        <div class="barber-spec-value">${look.sides}</div>
      </div>
      <div class="barber-spec">
        <div class="barber-spec-label">Texture</div>
        <div class="barber-spec-value">${look.texture}</div>
      </div>
      <div class="barber-spec">
        <div class="barber-spec-label">Products</div>
        <div class="barber-spec-value">${look.products}</div>
      </div>
    </div>
    <div class="barber-footer">
      <span class="barber-logo">STYLELOCK</span>
    </div>
  `;
}

// =============================================================================
// 9. EVENT LISTENERS
// =============================================================================

function setupEventListeners() {
  // Home - Unlock button
  if (dom.homeUnlockBtn) {
    dom.homeUnlockBtn.addEventListener('click', handlePayment);
  }
  
  // Upload - Show action sheet
  if (dom.uploadFrameBtn) {
    dom.uploadFrameBtn.addEventListener('click', showActionSheet);
  }
  if (dom.uploadTakeBtn) {
    dom.uploadTakeBtn.addEventListener('click', showActionSheet);
  }
  
  // Action Sheet buttons
  if (dom.photoLibraryBtn) {
    dom.photoLibraryBtn.addEventListener('click', () => {
      dom.libraryInput?.click();
    });
  }
  if (dom.takePhotoBtn) {
    dom.takePhotoBtn.addEventListener('click', () => {
      dom.cameraInput?.click();
    });
  }
  if (dom.chooseFileBtn) {
    dom.chooseFileBtn.addEventListener('click', () => {
      dom.fileInput?.click();
    });
  }
  if (dom.cancelSheetBtn) {
    dom.cancelSheetBtn.addEventListener('click', hideActionSheet);
  }
  
  // Close action sheet on overlay click
  if (dom.actionSheet) {
    dom.actionSheet.addEventListener('click', (e) => {
      if (e.target === dom.actionSheet) {
        hideActionSheet();
      }
    });
  }
  
  // File inputs
  if (dom.cameraInput) {
    dom.cameraInput.addEventListener('change', handleImageSelection);
  }
  if (dom.libraryInput) {
    dom.libraryInput.addEventListener('change', handleImageSelection);
  }
  if (dom.fileInput) {
    dom.fileInput.addEventListener('change', handleImageSelection);
  }
  
  // Barber - Close button
  if (dom.barberClose) {
    dom.barberClose.addEventListener('click', () => {
      showScreen('cutcard');
    });
  }
}

// =============================================================================
// 10. INITIALIZATION
// =============================================================================

function init() {
  console.log('StyleLock AI v51 initializing...');
  
  setupEventListeners();
  showScreen('home');
  
  console.log('StyleLock AI v51 ready');
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Expose functions needed by inline onclick handlers
window.selectLook = selectLook;
window.showBarberMode = showBarberMode;
