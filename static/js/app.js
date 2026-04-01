/* ============================================================
   STYLELOCK V54 - Frontend Interaction
   ============================================================ */

let imageBase64 = '';
let results = null;
let currentSlide = 0;
let currentLookIdx = 0;
let loadingProgressTimer = null;
let loadingTitleTimer = null;
let isGenerating = false;
let pickerInFlight = false;
let actionSheetOpen = false;
let touchStartX = 0;
let eventsBound = false;

const TIER_ORDER = ['BOLD', 'CLEAN', 'TRENDING'];
const LOADING_TITLES = ['READING', 'SCANNING', 'MATCHING', 'LOADING'];

function byId(id) {
    return document.getElementById(id);
}

function show(id) {
    document.querySelectorAll('.screen').forEach((s) => s.classList.remove('active'));
    byId(id).classList.add('active');
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function safeText(value, fallback = '--') {
    if (!value || !String(value).trim()) return fallback;
    return escapeHtml(String(value).trim());
}

function resetLoadingTimers() {
    if (loadingProgressTimer) {
        clearInterval(loadingProgressTimer);
        loadingProgressTimer = null;
    }
    if (loadingTitleTimer) {
        clearInterval(loadingTitleTimer);
        loadingTitleTimer = null;
    }
}

function goHome() {
    resetLoadingTimers();
    imageBase64 = '';
    results = null;
    currentSlide = 0;
    currentLookIdx = 0;
    isGenerating = false;
    pickerInFlight = false;

    const uploadPreview = byId('uploadPreview');
    uploadPreview.classList.remove('visible');
    uploadPreview.src = '';
    byId('uploadPlaceholder').style.display = 'flex';

    byId('loadingSelfie').src = '';
    byId('progressFill').style.width = '0%';
    byId('loadingText').textContent = 'Finding your next self';
    byId('loadingTitle').textContent = 'READING';

    hideActionSheet();
    show('homeScreen');
}

function openActionSheet() {
    if (pickerInFlight || isGenerating) return;
    if (actionSheetOpen) return;
    actionSheetOpen = true;
    byId('actionSheet').classList.add('active');
}

function hideActionSheet() {
    actionSheetOpen = false;
    byId('actionSheet').classList.remove('active');
}

function triggerInput(inputId) {
    if (pickerInFlight || isGenerating) return;
    pickerInFlight = true;
    actionSheetOpen = false;
    hideActionSheet();
    const input = byId(inputId);
    input.value = '';
    setTimeout(() => {
        input.click();
        setTimeout(() => {
            pickerInFlight = false;
        }, 700);
    }, 120);
}

async function startPayment() {
    try {
        const orderRes = await fetch('/api/create-order', { method: 'POST' });
        const orderData = await orderRes.json();

        if (orderData.demo) {
            generate();
            return;
        }

        const options = {
            key: orderData.key_id,
            amount: orderData.amount,
            currency: orderData.currency,
            name: 'StyleLock',
            description: 'Unlock Your Next Self',
            order_id: orderData.order_id,
            handler: function () {
                generate();
            },
            theme: {
                color: '#122b24'
            }
        };

        const rzp = new Razorpay(options);
        rzp.open();
    } catch (err) {
        console.error('Payment error:', err);
        generate();
    }
}

function startLoadingAnimation() {
    const progressFill = byId('progressFill');
    const loadingText = byId('loadingText');
    const loadingTitle = byId('loadingTitle');

    progressFill.style.width = '0%';
    loadingText.textContent = 'Finding your next self';
    loadingTitle.textContent = 'READING';

    const phases = [
        { progress: 18, text: 'Reading facial structure' },
        { progress: 33, text: 'Analyzing hair density and texture' },
        { progress: 52, text: 'Matching identity directions' },
        { progress: 73, text: 'Generating visual futures' },
        { progress: 91, text: 'Finalizing your 3 looks' }
    ];

    let phaseIdx = 0;
    loadingProgressTimer = setInterval(() => {
        if (phaseIdx >= phases.length) return;
        progressFill.style.width = phases[phaseIdx].progress + '%';
        loadingText.textContent = phases[phaseIdx].text;
        phaseIdx += 1;
    }, 1700);

    let titleIdx = 0;
    loadingTitleTimer = setInterval(() => {
        titleIdx = (titleIdx + 1) % LOADING_TITLES.length;
        loadingTitle.style.opacity = '0.2';
        setTimeout(() => {
            loadingTitle.textContent = LOADING_TITLES[titleIdx];
            loadingTitle.style.opacity = '1';
        }, 110);
    }, 2300);
}

function normalizeLooks(rawLooks) {
    const list = Array.isArray(rawLooks) ? rawLooks : [];
    const looksByTier = {};

    list.forEach((look) => {
        const tier = String(look?.tier || look?.name || '').toUpperCase();
        if (!looksByTier[tier]) {
            looksByTier[tier] = {
                name: look.full_name || look.name || tier || 'Look',
                tier,
                image: look.image || '',
                match_percentage: Number(look.match_percentage) || 80,
                achievability: look.achievability || 'ready',
                vibe: look.vibe || '--',
                maintenance: look.maintenance || '--',
                top_length: look.top_length || '--',
                sides: look.sides || '--',
                texture: look.texture || '--',
                products: look.products || '--',
                styling: look.styling || '--',
                fringe: look.fringe || '--'
            };
        }
    });

    const ordered = [];
    TIER_ORDER.forEach((tier) => {
        if (looksByTier[tier]) ordered.push(looksByTier[tier]);
    });

    list.forEach((look) => {
        if (ordered.length >= 3) return;
        const tier = String(look?.tier || look?.name || '').toUpperCase();
        const exists = ordered.some((x) => x.tier === tier);
        if (!exists) {
            ordered.push({
                name: look.full_name || look.name || tier,
                tier,
                image: look.image || '',
                match_percentage: Number(look.match_percentage) || 80,
                achievability: look.achievability || 'ready',
                vibe: look.vibe || '--',
                maintenance: look.maintenance || '--',
                top_length: look.top_length || '--',
                sides: look.sides || '--',
                texture: look.texture || '--',
                products: look.products || '--',
                styling: look.styling || '--',
                fringe: look.fringe || '--'
            });
        }
    });

    return ordered.slice(0, 3);
}

async function generate() {
    if (isGenerating || !imageBase64) return;

    isGenerating = true;
    show('loadingScreen');
    startLoadingAnimation();

    try {
        const resp = await fetch('/api/generate-looks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageBase64 })
        });

        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.detail || 'Generation failed');
        }

        results = {
            looks: normalizeLooks(data.looks)
        };

        resetLoadingTimers();
        byId('progressFill').style.width = '100%';
        byId('loadingText').textContent = 'Your identity board is ready';

        setTimeout(() => {
            renderResults();
            isGenerating = false;
        }, 420);
    } catch (error) {
        console.error(error);
        resetLoadingTimers();
        isGenerating = false;
        byId('errorText').textContent = error.message || 'Something went wrong';
        show('errorScreen');
    }
}

function getTierNote(tier) {
    if (tier === 'BOLD') return 'bold call';
    if (tier === 'CLEAN') return 'clean cut';
    return 'trend move';
}

function tierClass(tier) {
    if (tier === 'BOLD') return 'tier-bold';
    if (tier === 'CLEAN') return 'tier-clean';
    return 'tier-trending';
}

function achievabilityRank(value) {
    const ach = String(value || '').toLowerCase();
    if (ach === 'ready') return 3;
    if (ach === 'grow') return 2;
    if (ach === 'dream') return 1;
    return 0;
}

function getMostAchievableIndex(looks) {
    let bestIdx = 0;
    let bestScore = -1;
    looks.forEach((look, idx) => {
        const score = (achievabilityRank(look.achievability) * 100) + (Number(look.match_percentage) || 0);
        if (score > bestScore) {
            bestScore = score;
            bestIdx = idx;
        }
    });
    return bestIdx;
}

function renderResults() {
    const looks = results?.looks || [];
    if (!looks.length) {
        byId('errorText').textContent = 'No looks available right now';
        show('errorScreen');
        return;
    }

    currentSlide = 0;
    const mostAchievableIdx = getMostAchievableIndex(looks);
    const carousel = byId('resultsCarousel');
    const dots = byId('resultsDots');
    const swipeCue = byId('swipeCue');

    dots.innerHTML = looks
        .map((_, idx) => `<button class="dot ${idx === 0 ? 'active' : ''}" onclick="goSlide(${idx})" aria-label="Go to look ${idx + 1}"></button>`)
        .join('');

    carousel.innerHTML = looks
        .map((look, idx) => {
            const pct = Math.max(70, Math.min(99, Number(look.match_percentage) || 80));
            const supportingLooks = looks
                .map((item, itemIdx) => ({ item, itemIdx }))
                .filter((entry) => entry.itemIdx !== idx)
                .slice(0, 2);
            const imageMarkup = look.image
                ? `<img class="slide-image" src="${escapeHtml(look.image)}" alt="${escapeHtml(look.name)}">`
                : `<div class="slide-image-placeholder">Look preview unavailable.<br>Use this cut card for your barber.</div>`;

            return `
                <div class="results-slide" data-idx="${idx}">
                    <article class="slide-card hero-card ${tierClass(look.tier)}">
                        <div class="slide-image-wrap">
                            ${imageMarkup}
                            ${idx === mostAchievableIdx ? '<div class="achievable-badge">MOST ACHIEVABLE</div>' : ''}
                            <div class="match-badge"><span class="pct">${pct}%</span><span class="copy">MATCH</span></div>
                            <div class="slide-note">${getTierNote(look.tier)}</div>
                        </div>
                        <div class="slide-tier">
                            <div class="slide-tier-name">${safeText(look.tier, 'LOOK')}</div>
                            <div class="slide-tier-sub">${safeText(look.name, 'Identity Direction')}</div>
                        </div>
                    </article>

                    <div class="results-support-grid">
                        ${supportingLooks.map((support) => {
                            const supportImage = support.item.image
                                ? `<img class="support-card-image" src="${escapeHtml(support.item.image)}" alt="${escapeHtml(support.item.name)}">`
                                : `<div class="slide-image-placeholder">Preview pending</div>`;
                            return `
                                <button class="support-card ${tierClass(support.item.tier)}" onclick="goSlide(${support.itemIdx})" aria-label="Show ${escapeHtml(support.item.tier)} look">
                                    <div class="support-card-image-wrap">
                                        ${supportImage}
                                        ${support.itemIdx === mostAchievableIdx ? '<div class="achievable-badge">MOST ACHIEVABLE</div>' : ''}
                                    </div>
                                    <div class="support-card-meta">
                                        <div class="support-tier">${safeText(support.item.tier, 'LOOK')}</div>
                                        <div class="support-name">${safeText(support.item.name, 'Identity Direction')}</div>
                                    </div>
                                </button>
                            `;
                        }).join('')}
                    </div>

                    <div class="slide-info">
                        <div class="info-item"><div class="info-label">TOP</div><div class="info-value">${safeText(String(look.top_length).split(',')[0])}</div></div>
                        <div class="info-item"><div class="info-label">SIDES</div><div class="info-value">${safeText(String(look.sides).split(',')[0])}</div></div>
                        <div class="info-item"><div class="info-label">TEXTURE</div><div class="info-value">${safeText(String(look.texture).split(',')[0])}</div></div>
                        <div class="info-item"><div class="info-label">PRODUCT</div><div class="info-value">${safeText(String(look.products).split(',')[0])}</div></div>
                    </div>

                    <button class="btn-select" onclick="selectLook(${idx})">OPEN CUT CARD</button>
                </div>
            `;
        })
        .join('');

    swipeCue.classList.toggle('hidden', looks.length <= 1);
    swipeCue.textContent = 'SWIPE RIGHT ->';
    goSlide(0, true);
    show('resultsScreen');
}

function goSlide(nextIdx, skipCueUpdate = false) {
    const looks = results?.looks || [];
    if (!looks.length) return;

    currentSlide = Math.max(0, Math.min(nextIdx, looks.length - 1));
    byId('resultsCarousel').style.transform = `translateX(-${currentSlide * 100}%)`;

    document.querySelectorAll('.dot').forEach((dot, idx) => {
        dot.classList.toggle('active', idx === currentSlide);
    });

    if (!skipCueUpdate || currentSlide > 0) {
        byId('swipeCue').classList.add('hidden');
    }
}

function selectLook(idx) {
    const look = results?.looks?.[idx];
    if (!look) return;

    currentLookIdx = idx;

    byId('cutcardContent').innerHTML = `
        <article class="cutcard-main">
            <div class="cutcard-media">
                ${look.image ? `<img class="cutcard-photo" src="${escapeHtml(look.image)}" alt="${escapeHtml(look.name)}">` : `<div class="slide-image-placeholder">Preview unavailable</div>`}
                <div class="cutcard-look-tag">YOUR LOOK</div>
                <div class="cutcard-tier">${safeText(look.tier, 'LOOK')}</div>
            </div>

            <div class="cutcard-meta">
                <div class="cut-meta"><div class="cut-meta-label">MATCH</div><div class="cut-meta-value">${Math.max(70, Math.min(99, Number(look.match_percentage) || 80))}%</div></div>
                <div class="cut-meta"><div class="cut-meta-label">VIBE</div><div class="cut-meta-value">${safeText(look.vibe)}</div></div>
                <div class="cut-meta"><div class="cut-meta-label">UPKEEP</div><div class="cut-meta-value">${safeText(look.maintenance)}</div></div>
            </div>

            <div class="cutcard-sections">
                <section class="cutcard-section"><div class="cutcard-label">FADE / SIDES</div><div class="cutcard-value">SIDES</div><div class="cutcard-desc">${safeText(look.sides)}</div></section>
                <section class="cutcard-section"><div class="cutcard-label">TOP LENGTH</div><div class="cutcard-value">TOP</div><div class="cutcard-desc">${safeText(look.top_length)}</div></section>
                <section class="cutcard-section"><div class="cutcard-label">TEXTURE</div><div class="cutcard-value">TEXTURE</div><div class="cutcard-desc">${safeText(look.texture)}</div></section>
                <section class="cutcard-section"><div class="cutcard-label">STYLING</div><div class="cutcard-value">STYLING</div><div class="cutcard-desc">${safeText(look.styling)}</div></section>
                <section class="cutcard-section"><div class="cutcard-label">PRODUCTS</div><div class="cutcard-value">PRODUCTS</div><div class="cutcard-desc">${safeText(look.products)}</div></section>
            </div>
        </article>
    `;

    byId('selectLookBtn').onclick = () => {
        currentLookIdx = idx;
        byId('lockedPhoto').src = look.image || '';
        showBarber();
    };
    show('cutcardScreen');
}

function backToResults() {
    show('resultsScreen');
}

function lockLook(idx) {
    const look = results?.looks?.[idx];
    if (!look) return;

    currentLookIdx = idx;
    byId('lockedPhoto').src = look.image || '';
    show('lockedScreen');
}

function backToLocked() {
    show('lockedScreen');
}

function showBarber() {
    const look = results?.looks?.[currentLookIdx];
    if (!look) return;

    byId('barberContent').innerHTML = `
        <article class="barber-sheet">
            ${look.image ? `<img class="barber-photo" src="${escapeHtml(look.image)}" alt="${escapeHtml(look.name)}">` : `<div class="slide-image-placeholder">Preview unavailable</div>`}
            <div class="barber-rows">
                <div class="barber-row"><div class="barber-label">SIDES</div><div class="barber-value">${safeText(look.sides)}</div></div>
                <div class="barber-row"><div class="barber-label">TOP</div><div class="barber-value">${safeText(look.top_length)}</div></div>
                <div class="barber-row"><div class="barber-label">TEXTURE</div><div class="barber-value">${safeText(look.texture)}</div></div>
                <div class="barber-row"><div class="barber-label">FRINGE</div><div class="barber-value">${safeText(look.fringe)}</div></div>
                <div class="barber-row"><div class="barber-label">STYLING</div><div class="barber-value">${safeText(look.styling)}</div></div>
                <div class="barber-row"><div class="barber-label">PRODUCTS</div><div class="barber-value">${safeText(look.products)}</div></div>
            </div>

            <div class="barber-brand-strip">
                <div class="brand-lockup">
                    <img class="brand-mark" src="/static/images/sl-monogram-white.png" alt="StyleLock monogram">
                    <div class="brand-word">STYLELOCK</div>
                </div>
                <div class="brand-sub">IDENTITY // EXECUTION CARD</div>
            </div>
        </article>
    `;

    show('barberScreen');
}

function saveToPhone() {
    const look = results?.looks?.[currentLookIdx];
    if (!look || !look.image) return;

    const a = document.createElement('a');
    a.href = look.image;
    a.download = 'stylelock-look.jpg';
    a.target = '_blank';
    a.click();
}

function handleImage(event) {
    const file = event.target.files?.[0];
    pickerInFlight = false;
    if (!file || isGenerating) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
        const dataUrl = ev.target?.result;
        if (!dataUrl || typeof dataUrl !== 'string') {
            byId('errorText').textContent = 'Unable to read selected photo';
            show('errorScreen');
            return;
        }

        imageBase64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;

        const preview = byId('uploadPreview');
        preview.src = dataUrl;
        preview.classList.add('visible');
        byId('uploadPlaceholder').style.display = 'none';
        byId('loadingSelfie').src = dataUrl;

        setTimeout(() => startPayment(), 260);
    };

    reader.readAsDataURL(file);
}

function bindEvents() {
    if (eventsBound) return;
    eventsBound = true;

    byId('unlockBtn').addEventListener('click', () => show('uploadScreen'));

    byId('takePhotoBtn').addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        openActionSheet();
    });
    byId('uploadPhotoBtn').addEventListener('click', () => triggerInput('fileInput'));

    byId('photoLibraryBtn').addEventListener('click', () => triggerInput('libraryInput'));
    byId('takePhotoCameraBtn').addEventListener('click', () => triggerInput('cameraInput'));
    byId('chooseFileBtn').addEventListener('click', () => triggerInput('fileInput'));

    byId('cancelSheetBtn').addEventListener('click', hideActionSheet);
    byId('actionSheet').addEventListener('click', (event) => {
        if (event.target.id === 'actionSheet') hideActionSheet();
    });

    byId('cameraInput').addEventListener('change', handleImage);
    byId('libraryInput').addEventListener('change', handleImage);
    byId('fileInput').addEventListener('change', handleImage);

    byId('resultsScreen').addEventListener('touchstart', (event) => {
        touchStartX = event.touches[0].clientX;
    }, { passive: true });

    byId('resultsScreen').addEventListener('touchend', (event) => {
        const looks = results?.looks || [];
        if (!looks.length) return;
        const diff = touchStartX - event.changedTouches[0].clientX;
        if (Math.abs(diff) < 46) return;

        if (diff > 0 && currentSlide < looks.length - 1) {
            goSlide(currentSlide + 1);
        } else if (diff < 0 && currentSlide > 0) {
            goSlide(currentSlide - 1);
        }
    }, { passive: true });
}

bindEvents();
console.log('StyleLock V54 loaded');
