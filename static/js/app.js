/* ============================================================
   STYLELOCK v52 - MAGAZINE EDITION JS
   Full PWA functionality
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
    document.getElementById('cameraInput').value = '';
    document.getElementById('galleryInput').value = '';
    show('homeScreen');
}

// =============================================================================
// IMAGE HANDLING
// =============================================================================

function handleImage(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = ev => {
        imageBase64 = ev.target.result.split(',')[1];
        document.getElementById('previewImg').src = ev.target.result;
        show('previewScreen');
    };
    reader.readAsDataURL(file);
}

// Setup file input listeners
document.getElementById('cameraInput').addEventListener('change', handleImage);
document.getElementById('galleryInput').addEventListener('change', handleImage);

// =============================================================================
// PAYMENT FLOW
// =============================================================================

async function startPayment() {
    // Create order
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
            description: 'Unlock Your Look',
            order_id: orderData.order_id,
            handler: function(response) {
                // Payment successful
                console.log('Payment successful:', response);
                generate();
            },
            prefill: {},
            theme: {
                color: '#0047FF'
            }
        };
        
        const rzp = new Razorpay(options);
        rzp.open();
        
    } catch (err) {
        console.error('Payment error:', err);
        // Fallback to demo mode
        generate();
    }
}

// =============================================================================
// GENERATION FLOW
// =============================================================================

async function generate() {
    show('loadingScreen');
    
    const phases = [
        { t: 'READING', s: 'Analyzing face shape...' },
        { t: 'READING', s: 'Detecting hair texture...' },
        { t: 'MATCHING', s: 'Finding your looks...' },
        { t: 'BUILDING', s: 'Generating previews...' }
    ];
    
    let i = 0;
    const interval = setInterval(() => {
        i = (i + 1) % phases.length;
        document.getElementById('loadingText').textContent = phases[i].t;
        document.getElementById('loadingStep').textContent = phases[i].s;
    }, 2500);
    
    try {
        const resp = await fetch('/api/generate-looks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageBase64 })
        });
        
        clearInterval(interval);
        
        const data = await resp.json();
        
        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.detail || 'Generation failed');
        }
        
        // Map API response to our expected format
        results = {
            recommendations: data.looks.map(look => ({
                name: look.full_name || look.name,
                tier: look.name, // BOLD, CLEAN, TRENDING
                preview_url: look.image,
                match_percentage: look.match_percentage,
                achievability: look.achievability,
                growth_weeks: look.growth_weeks || 0,
                vibe: look.vibe,
                maintenance: look.maintenance,
                cut_card: {
                    fade: look.sides,
                    top_length: look.top_length,
                    fringe: look.fringe,
                    styling: look.styling,
                    products: look.products,
                    texture: look.texture
                }
            }))
        };
        
        renderResults();
        
    } catch (e) {
        clearInterval(interval);
        document.getElementById('errorText').textContent = e.message;
        show('errorScreen');
    }
}

// =============================================================================
// RESULTS CAROUSEL
// =============================================================================

function renderResults() {
    const recs = results.recommendations || [];
    const nav = document.getElementById('resultsNav');
    const carousel = document.getElementById('carousel');
    
    // Navigation dots
    nav.innerHTML = recs.map((_, i) => 
        `<div class="nav-dot ${i === 0 ? 'active' : ''}" onclick="goSlide(${i})"></div>`
    ).join('');
    
    // Slides
    carousel.innerHTML = recs.map((look, i) => {
        const tier = (look.tier || 'TRENDING').toUpperCase();
        const tierClass = tier.toLowerCase();
        const scripts = ['not bad', 'pick one', 'this could be you'];
        const strokeColor = tier === 'BOLD' ? '#D4FF00' : '#0047FF';
        
        return `
        <div class="slide slide-${tierClass}">
            <div class="slide-tier">${tier}</div>
            <div class="slide-photo">
                ${look.preview_url 
                    ? `<img src="${look.preview_url}" alt="${look.name}">`
                    : '<div class="slide-photo-loading">Generating...</div>'
                }
            </div>
            <div class="stamp">
                <svg viewBox="0 0 100 100">
                    <path d="M50 2 C55 8, 62 5, 68 8 C74 11, 78 6, 85 12 C92 18, 97 15, 98 25 C99 35, 95 40, 98 50 C101 60, 96 65, 92 72 C88 79, 93 85, 85 90 C77 95, 72 92, 65 95 C58 98, 52 95, 45 98 C38 101, 32 97, 25 92 C18 87, 12 91, 8 82 C4 73, 8 67, 5 58 C2 49, 5 42, 3 33 C1 24, 6 18, 12 12 C18 6, 25 10, 32 5 C39 0, 45 4, 50 2 Z" 
                          fill="none" 
                          stroke="${strokeColor}" 
                          stroke-width="2"/>
                </svg>
                <div class="stamp-text">
                    <span class="stamp-pct">${look.match_percentage}%</span>
                    <span class="stamp-label">MATCH</span>
                </div>
            </div>
            <span class="slide-script">${scripts[i] || 'pick one'}</span>
            <div class="slide-actions">
                <button class="btn btn-black" onclick="viewCutCard(${i})">View Cut Card</button>
                <button class="btn btn-outline${tier === 'BOLD' ? '-white' : ''}" onclick="lockLook(${i})">Lock This Look</button>
            </div>
        </div>`;
    }).join('');
    
    show('resultsScreen');
}

function goSlide(i) {
    currentSlide = i;
    document.getElementById('carousel').style.transform = `translateX(-${i * 100}vw)`;
    document.querySelectorAll('.nav-dot').forEach((d, idx) => 
        d.classList.toggle('active', idx === i)
    );
}

// =============================================================================
// CUT CARD
// =============================================================================

function viewCutCard(i) {
    currentLookIdx = i;
    const look = results.recommendations[i];
    const cc = look.cut_card || {};
    
    document.getElementById('cutcardPhoto').src = look.preview_url || '';
    
    const badgeText = look.achievability === 'ready' ? 'READY' 
                    : look.achievability === 'grow' ? `${look.growth_weeks}W GROW` 
                    : 'DREAM';
    document.getElementById('cutcardBadge').textContent = badgeText;
    
    const sections = [
        { label: 'FADE', key: 'fade' },
        { label: 'TOP', key: 'top_length' },
        { label: 'FRINGE', key: 'fringe' },
        { label: 'STYLING', key: 'styling' },
        { label: 'PRODUCTS', key: 'products' }
    ];
    
    document.getElementById('cutcardContent').innerHTML = sections.map(s => `
        <div class="cutcard-section">
            <span class="cutcard-label">${s.label}</span>
            <div class="cutcard-value">${s.label}</div>
            <p class="cutcard-desc">${cc[s.key] || '—'}</p>
        </div>
    `).join('');
    
    document.getElementById('cutcardLockBtn').onclick = () => lockLook(i);
    show('cutcardScreen');
}

function backToResults() {
    show('resultsScreen');
}

// =============================================================================
// LOCKED LOOK
// =============================================================================

function lockLook(i) {
    currentLookIdx = i;
    const look = results.recommendations[i];
    document.getElementById('lockedPhoto').src = look.preview_url || '';
    show('lockedScreen');
}

function backToLocked() {
    show('lockedScreen');
}

// =============================================================================
// BARBER MODE
// =============================================================================

function showBarber() {
    const look = results.recommendations[currentLookIdx];
    const cc = look.cut_card || {};
    
    const sections = [
        { label: 'FADE / SIDES', key: 'fade' },
        { label: 'TOP LENGTH', key: 'top_length' },
        { label: 'FRINGE', key: 'fringe' },
        { label: 'STYLING', key: 'styling' },
        { label: 'PRODUCTS', key: 'products' }
    ];
    
    document.getElementById('barberContent').innerHTML = `
        <img class="barber-photo" src="${look.preview_url || ''}" alt="${look.name}">
        ${sections.map(s => `
            <div class="barber-section">
                <div class="barber-label">${s.label}</div>
                <div class="barber-value">${s.label.split(' ')[0]}</div>
                <div class="barber-desc">${cc[s.key] || '—'}</div>
            </div>
        `).join('')}
    `;
    
    show('barberScreen');
}

// =============================================================================
// SHARING
// =============================================================================

function saveToPhone() {
    const look = results.recommendations[currentLookIdx];
    if (look && look.preview_url) {
        const a = document.createElement('a');
        a.href = look.preview_url;
        a.download = 'stylelock-look.jpg';
        a.target = '_blank';
        a.click();
    }
}

function shareWhatsApp() {
    const look = results.recommendations[currentLookIdx];
    const url = look ? encodeURIComponent(look.preview_url || '') : '';
    window.open(`https://wa.me/?text=Check%20out%20my%20new%20look%20from%20StyleLock!%20${url}`, '_blank');
    closeModal();
}

function copyLink() {
    const look = results.recommendations[currentLookIdx];
    if (look && look.preview_url) {
        navigator.clipboard.writeText(look.preview_url)
            .then(() => alert('Link copied!'))
            .catch(() => alert('Failed to copy'));
    }
    closeModal();
}

function closeModal() {
    document.getElementById('shareModal').classList.remove('active');
}

// Close modal on background click
document.getElementById('shareModal').addEventListener('click', e => {
    if (e.target.id === 'shareModal') closeModal();
});

// =============================================================================
// SWIPE SUPPORT
// =============================================================================

let touchStartX = 0;

document.getElementById('resultsScreen').addEventListener('touchstart', e => {
    touchStartX = e.touches[0].clientX;
}, { passive: true });

document.getElementById('resultsScreen').addEventListener('touchend', e => {
    const diff = touchStartX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 50) {
        const recs = results?.recommendations || [];
        if (diff > 0 && currentSlide < recs.length - 1) {
            goSlide(currentSlide + 1);
        } else if (diff < 0 && currentSlide > 0) {
            goSlide(currentSlide - 1);
        }
    }
}, { passive: true });

// =============================================================================
// INITIALIZATION
// =============================================================================

console.log('🎨 StyleLock v52 Magazine Edition loaded');
