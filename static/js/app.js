/* ============================================================
   STYLELOCK V53 - JavaScript
   Correct flow with action sheet
   ============================================================ */

// =============================================================================
// STATE
// =============================================================================

let imageBase64 = '';
let results = null;
let currentSlide = 0;
let currentLookIdx = 0;

// =============================================================================
// SCREEN NAVIGATION
// =============================================================================

function show(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function goHome() {
    imageBase64 = '';
    results = null;
    currentSlide = 0;
    document.getElementById('uploadPreview').classList.remove('visible');
    document.getElementById('uploadPlaceholder').style.display = 'flex';
    show('homeScreen');
}

// =============================================================================
// HOME SCREEN
// =============================================================================

document.getElementById('unlockBtn').addEventListener('click', () => {
    show('uploadScreen');
});

// =============================================================================
// UPLOAD SCREEN & ACTION SHEET
// =============================================================================

document.getElementById('takePhotoBtn').addEventListener('click', () => {
    document.getElementById('actionSheet').classList.add('active');
});

document.getElementById('cancelSheetBtn').addEventListener('click', () => {
    document.getElementById('actionSheet').classList.remove('active');
});

document.getElementById('actionSheet').addEventListener('click', (e) => {
    if (e.target.id === 'actionSheet') {
        document.getElementById('actionSheet').classList.remove('active');
    }
});

document.getElementById('photoLibraryBtn').addEventListener('click', () => {
    document.getElementById('actionSheet').classList.remove('active');
    document.getElementById('libraryInput').click();
});

document.getElementById('takePhotoCameraBtn').addEventListener('click', () => {
    document.getElementById('actionSheet').classList.remove('active');
    document.getElementById('cameraInput').click();
});

document.getElementById('chooseFileBtn').addEventListener('click', () => {
    document.getElementById('actionSheet').classList.remove('active');
    document.getElementById('fileInput').click();
});

// =============================================================================
// IMAGE HANDLING
// =============================================================================

function handleImage(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (ev) => {
        imageBase64 = ev.target.result.split(',')[1];
        
        // Show preview in upload screen
        const preview = document.getElementById('uploadPreview');
        preview.src = ev.target.result;
        preview.classList.add('visible');
        document.getElementById('uploadPlaceholder').style.display = 'none';
        
        // Also set loading selfie
        document.getElementById('loadingSelfie').src = ev.target.result;
        
        // Start payment flow
        setTimeout(() => startPayment(), 500);
    };
    reader.readAsDataURL(file);
}

document.getElementById('cameraInput').addEventListener('change', handleImage);
document.getElementById('libraryInput').addEventListener('change', handleImage);
document.getElementById('fileInput').addEventListener('change', handleImage);

// =============================================================================
// PAYMENT FLOW
// =============================================================================

async function startPayment() {
    try {
        const orderRes = await fetch('/api/create-order', { method: 'POST' });
        const orderData = await orderRes.json();
        
        if (orderData.demo) {
            // Demo mode - skip payment
            console.log('Demo mode - proceeding without payment');
            generate();
            return;
        }
        
        // Open Razorpay
        const options = {
            key: orderData.key_id,
            amount: orderData.amount,
            currency: orderData.currency,
            name: 'StyleLock',
            description: 'Unlock Your Next Self',
            order_id: orderData.order_id,
            handler: function(response) {
                console.log('Payment successful:', response);
                generate();
            },
            theme: {
                color: '#1a2f2a'
            }
        };
        
        const rzp = new Razorpay(options);
        rzp.open();
        
    } catch (err) {
        console.error('Payment error:', err);
        generate(); // Fallback
    }
}

// =============================================================================
// GENERATION FLOW
// =============================================================================

async function generate() {
    show('loadingScreen');
    
    // Animate progress bar
    const progressFill = document.getElementById('progressFill');
    const loadingText = document.getElementById('loadingText');
    
    const phases = [
        { progress: 20, text: 'Reading your face...' },
        { progress: 40, text: 'Analyzing hair texture...' },
        { progress: 60, text: 'Finding your looks...' },
        { progress: 80, text: 'Generating previews...' },
        { progress: 95, text: 'Almost there...' }
    ];
    
    let phaseIdx = 0;
    const progressInterval = setInterval(() => {
        if (phaseIdx < phases.length) {
            progressFill.style.width = phases[phaseIdx].progress + '%';
            loadingText.textContent = phases[phaseIdx].text;
            phaseIdx++;
        }
    }, 2000);
    
    try {
        const resp = await fetch('/api/generate-looks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageBase64 })
        });
        
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        
        const data = await resp.json();
        
        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.detail || 'Generation failed');
        }
        
        // Map API response
        results = {
            looks: data.looks.map(look => ({
                name: look.full_name || look.name,
                tier: look.name, // BOLD, CLEAN, TRENDING
                image: look.image,
                match_percentage: look.match_percentage,
                achievability: look.achievability,
                vibe: look.vibe,
                maintenance: look.maintenance,
                top_length: look.top_length,
                sides: look.sides,
                texture: look.texture,
                products: look.products,
                styling: look.styling,
                fringe: look.fringe
            }))
        };
        
        setTimeout(() => renderResults(), 500);
        
    } catch (e) {
        clearInterval(progressInterval);
        document.getElementById('errorText').textContent = e.message;
        show('errorScreen');
    }
}

// =============================================================================
// RESULTS CAROUSEL
// =============================================================================

function renderResults() {
    const looks = results.looks || [];
    const carousel = document.getElementById('resultsCarousel');
    const dots = document.getElementById('resultsDots');
    
    // Render dots
    dots.innerHTML = looks.map((_, i) => 
        `<div class="dot ${i === 0 ? 'active' : ''}" onclick="goSlide(${i})"></div>`
    ).join('');
    
    // Render slides
    carousel.innerHTML = looks.map((look, i) => `
        <div class="results-slide">
            <div class="slide-card">
                ${look.image 
                    ? `<img class="slide-image" src="${look.image}" alt="${look.name}">`
                    : '<div class="slide-image-placeholder">Generating...</div>'
                }
                <div class="slide-tier">
                    <div class="slide-tier-name">${look.tier}</div>
                    <div class="slide-tier-sub">AI-Generated Look</div>
                </div>
            </div>
            <div class="slide-info">
                <div class="info-item">
                    <div class="info-label">TOP</div>
                    <div class="info-value">${look.top_length || '—'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">SIDES</div>
                    <div class="info-value">${look.sides ? look.sides.split(',')[0] : '—'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">TEXTURE</div>
                    <div class="info-value">${look.texture ? look.texture.split(' ')[0] : '—'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">PRODUCTS</div>
                    <div class="info-value">${look.products ? look.products.split(',')[0] : '—'}</div>
                </div>
            </div>
            <button class="btn-select" onclick="selectLook(${i})">SELECT THIS LOOK</button>
        </div>
    `).join('');
    
    show('resultsScreen');
}

function goSlide(i) {
    currentSlide = i;
    const carousel = document.getElementById('resultsCarousel');
    carousel.style.transform = `translateX(-${i * 100}vw)`;
    
    document.querySelectorAll('.dot').forEach((d, idx) => {
        d.classList.toggle('active', idx === i);
    });
}

// Swipe support
let touchStartX = 0;
document.getElementById('resultsScreen').addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
}, { passive: true });

document.getElementById('resultsScreen').addEventListener('touchend', (e) => {
    const diff = touchStartX - e.changedTouches[0].clientX;
    const looks = results?.looks || [];
    if (Math.abs(diff) > 50) {
        if (diff > 0 && currentSlide < looks.length - 1) {
            goSlide(currentSlide + 1);
        } else if (diff < 0 && currentSlide > 0) {
            goSlide(currentSlide - 1);
        }
    }
}, { passive: true });

// =============================================================================
// CUT CARD & SELECTION
// =============================================================================

function selectLook(i) {
    currentLookIdx = i;
    const look = results.looks[i];
    
    const content = document.getElementById('cutcardContent');
    content.innerHTML = `
        <img class="cutcard-photo" src="${look.image || ''}" alt="${look.name}">
        
        <div class="cutcard-section">
            <div class="cutcard-label">FADE / SIDES</div>
            <div class="cutcard-value">SIDES</div>
            <div class="cutcard-desc">${look.sides || '—'}</div>
        </div>
        
        <div class="cutcard-section">
            <div class="cutcard-label">TOP LENGTH</div>
            <div class="cutcard-value">TOP</div>
            <div class="cutcard-desc">${look.top_length || '—'}</div>
        </div>
        
        <div class="cutcard-section">
            <div class="cutcard-label">TEXTURE</div>
            <div class="cutcard-value">TEXTURE</div>
            <div class="cutcard-desc">${look.texture || '—'}</div>
        </div>
        
        <div class="cutcard-section">
            <div class="cutcard-label">STYLING</div>
            <div class="cutcard-value">STYLING</div>
            <div class="cutcard-desc">${look.styling || '—'}</div>
        </div>
        
        <div class="cutcard-section">
            <div class="cutcard-label">PRODUCTS</div>
            <div class="cutcard-value">PRODUCTS</div>
            <div class="cutcard-desc">${look.products || '—'}</div>
        </div>
    `;
    
    document.getElementById('selectLookBtn').onclick = () => lockLook(i);
    show('cutcardScreen');
}

function backToResults() {
    show('resultsScreen');
}

// =============================================================================
// LOCKED SCREEN
// =============================================================================

function lockLook(i) {
    currentLookIdx = i;
    const look = results.looks[i];
    document.getElementById('lockedPhoto').src = look.image || '';
    show('lockedScreen');
}

function backToLocked() {
    show('lockedScreen');
}

// =============================================================================
// BARBER MODE
// =============================================================================

function showBarber() {
    const look = results.looks[currentLookIdx];
    
    document.getElementById('barberContent').innerHTML = `
        <img class="barber-photo" src="${look.image || ''}" alt="${look.name}">
        
        <div class="barber-section">
            <div class="barber-label">FADE / SIDES</div>
            <div class="barber-value">SIDES</div>
            <div class="barber-desc">${look.sides || '—'}</div>
        </div>
        
        <div class="barber-section">
            <div class="barber-label">TOP LENGTH</div>
            <div class="barber-value">TOP</div>
            <div class="barber-desc">${look.top_length || '—'}</div>
        </div>
        
        <div class="barber-section">
            <div class="barber-label">TEXTURE</div>
            <div class="barber-value">TEXTURE</div>
            <div class="barber-desc">${look.texture || '—'}</div>
        </div>
        
        <div class="barber-section">
            <div class="barber-label">STYLING</div>
            <div class="barber-value">STYLING</div>
            <div class="barber-desc">${look.styling || '—'}</div>
        </div>
        
        <div class="barber-section">
            <div class="barber-label">PRODUCTS</div>
            <div class="barber-value">PRODUCTS</div>
            <div class="barber-desc">${look.products || '—'}</div>
        </div>
    `;
    
    show('barberScreen');
}

// =============================================================================
// SAVE
// =============================================================================

function saveToPhone() {
    const look = results.looks[currentLookIdx];
    if (look && look.image) {
        const a = document.createElement('a');
        a.href = look.image;
        a.download = 'stylelock-look.jpg';
        a.target = '_blank';
        a.click();
    }
}

// =============================================================================
// INIT
// =============================================================================

console.log('🎨 StyleLock V53 loaded');
