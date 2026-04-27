/* ============================================================
   STYLELOCK V54 - Frontend Interaction
   ============================================================ */

let imageBase64 = '';
let results = null;
let currentSlide = 0;
let currentLookIdx = 0;
let loadingProgressTimer = null;
let loadingTitleTimer = null;
let loadingCaptionTimer = null;
let isGenerating = false;
let pickerInFlight = false;
let pickerCooldownUntil = 0;
let touchStartX = 0;
let eventsBound = false;
let diagnosticsBound = false;
let currentScreen = 'homeScreen';
let lockedStampVisible = true;
const RESULTS_SESSION_KEY = 'stylelock_results_snapshot';
const LOOK_INDEX_SESSION_KEY = 'stylelock_current_look_idx';
const FREE_LOOK_SESSION_KEY = 'stylelock_free_look_snapshot';
const FREE_LOOK_CLAIM_KEY = 'stylelock_free_look_claim_token';
const FREE_LOOK_STAGE_KEY = 'stylelock_v1_stage';
const FREE_LOOK_BROWSER_LOCK_KEY = 'stylelock_free_look_used_ist_date';
const FREE_LOOK_RESET_KEYS = [FREE_LOOK_BROWSER_LOCK_KEY, FREE_LOOK_SESSION_KEY, FREE_LOOK_CLAIM_KEY, FREE_LOOK_STAGE_KEY];
const DIRECT_PAID_UPLOAD_KEY = 'stylelock_direct_paid_upload';
const META_VIEW_CONTENT_KEY = 'stylelock_meta_viewcontent_tracked';
const META_INITIATE_CHECKOUT_KEY = 'stylelock_meta_initiate_checkout_order';
const META_PURCHASE_KEY = 'stylelock_meta_purchase_payment';
const META_IN_APP_BROWSER_REGEX = /(Instagram|FBAN|FBAV|FB_IAB|Messenger)/i;
let freeLookResult = null;
let freeClaimToken = '';
let uploadMeta = {
    originalBytes: 0,
    compressedBytes: 0,
    longEdge: 1200
};

// ---------- Custom event tracking (Meta Pixel trackCustom) ----------
// Session ID is shared with landing.html via sessionStorage (key `sl_sid`), so a
// user's full journey Landing â†’ Upload â†’ Pay â†’ Cut Card joins up in Events Manager.
function slSessionId() {
    try {
        let sid = sessionStorage.getItem('sl_sid');
        if (!sid) {
            sid = (window.crypto && typeof window.crypto.randomUUID === 'function')
                ? window.crypto.randomUUID()
                : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                    const r = Math.random() * 16 | 0;
                    const v = c === 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            sessionStorage.setItem('sl_sid', sid);
        }
        return sid;
    } catch (_e) { return 'nosession'; }
}
function slTrack(event, extra) {
    try {
        const payload = Object.assign({ session_id: slSessionId() }, extra || {});
        if (window.fbq) window.fbq('trackCustom', event, payload);
        if (window.console && console.debug) console.debug('[sl-track]', event, payload);
    } catch (_err) {}
}
window.__slTrack = slTrack;

// Map look index to its canonical tier label for event attribution.
function slLookTier(idx) {
    try {
        const look = results && results.looks && results.looks[idx];
        if (!look) return 'unknown';
        const tier = String(look.tier || '').toUpperCase();
        if (tier === 'TRENDING' || tier === 'CLEAN' || tier === 'BOLD') return tier.toLowerCase();
        // Fallback: hero = 'hero', others = by position
        const heroIdx = typeof getMostAchievableIndex === 'function' ? getMostAchievableIndex(results.looks) : 0;
        return idx === heroIdx ? 'hero' : 'secondary';
    } catch (_e) { return 'unknown'; }
}

const TIER_ORDER = ['BOLD', 'CLEAN', 'TRENDING'];
const LOADING_TITLES = ['READING', 'SCANNING', 'MATCHING', 'LOADING'];
const FREE_LOOK_LOADING_CAPTIONS = [
    'Preparing image',
    'Checking texture and fall',
    'Building your best look',
    'Mapping your strongest option',
    'Finding your next self',
    'Looking for the clean win',
    'Scanning barber potential',
    'Measuring what’s workable',
    'Matching shape to style',
    'Seeing what your barber sees',
    'Looking for your easiest win',
    'Checking what works right now',
    'Spotting your strongest route',
    'Balancing fit and readiness',
    'Looking for the sharpest option',
    'Matching growth to possibility',
    'Finding the most achievable win'
];
const PAID_LOADING_CAPTIONS = [
    'Preparing image',
    'Checking texture and fall',
    'Building your 3 looks',
    'Mapping your strongest option',
    'Finding your next self',
    'Looking for the clean win',
    'Scanning barber potential',
    'Measuring what’s workable',
    'Matching shape to style',
    'Seeing what your barber sees',
    'Looking for your easiest win',
    'Checking what works right now',
    'Spotting your strongest route',
    'Balancing fit and readiness',
    'Looking for the sharpest option',
    'Matching growth to possibility',
    'Finding the most achievable win',
    'Shortlisting your next 3 looks',
    'Turning hair reality into direction'
];
const RESULTS_STATIC_BOARD = true;
const APP_VERSION = String(window.STYLELOCK_APP_VERSION || 'v54.3');
const FREE_LOOK_LONG_EDGE = 1200;
const FREE_LOOK_JPEG_QUALITY = 0.86;
const UI_VERSION_KEY = 'stylelock_ui_version';
const STALE_UI_KEYS = [
    'stylelock_screen',
    'stylelock_view',
    'stylelock_current_screen',
    'stylelock_selected_look',
    'stylelock_results_state'
];

function byId(id) {
    return document.getElementById(id);
}

function syncViewportHeight() {
    try {
        // Prefer visualViewport.height â€” this reflects the ACTUAL visible area
        // in iOS Safari (accounting for dynamic toolbar) and in Instagram's
        // in-app webview (where window.innerHeight is often inaccurate).
        const vv = typeof window !== 'undefined' ? window.visualViewport : null;
        const viewportHeight =
            (vv && vv.height) ||
            window.innerHeight ||
            document.documentElement?.clientHeight ||
            0;
        if (viewportHeight > 0) {
            document.documentElement.style.setProperty('--app-height', `${viewportHeight}px`);
        }
    } catch (_err) {
        // no-op: viewport syncing is best-effort only
    }
}

function isMetaInAppBrowser() {
    try {
        return META_IN_APP_BROWSER_REGEX.test(window.navigator?.userAgent || '');
    } catch (_err) {
        return false;
    }
}

function syncInAppBrowserHint() {
    const note = byId('inAppBrowserNote');
    if (!note) return;
    note.hidden = !isMetaInAppBrowser();
}

function trackMetaEvent(eventName, payload) {
    if (typeof window === 'undefined' || typeof window.fbq !== 'function') return false;
    try {
        if (payload && typeof payload === 'object') {
            window.fbq('track', eventName, payload);
        } else {
            window.fbq('track', eventName);
        }
        return true;
    } catch (err) {
        console.warn('[StyleLock meta] track failed:', eventName, err);
        return false;
    }
}

function trackViewContentOnce() {
    try {
        if (sessionStorage.getItem(META_VIEW_CONTENT_KEY) === '1') return;
        if (trackMetaEvent('ViewContent', { content_name: 'StyleLock App' })) {
            sessionStorage.setItem(META_VIEW_CONTENT_KEY, '1');
        }
    } catch (_err) {
        // no-op: analytics should never affect app flow
    }
}

function trackInitiateCheckout(orderId) {
    const normalizedOrderId = String(orderId || '').trim();
    try {
        if (!normalizedOrderId) return;
        if (sessionStorage.getItem(META_INITIATE_CHECKOUT_KEY) === normalizedOrderId) return;
        if (trackMetaEvent('InitiateCheckout', { value: 79, currency: 'INR' })) {
            sessionStorage.setItem(META_INITIATE_CHECKOUT_KEY, normalizedOrderId);
        }
    } catch (_err) {
        // no-op: analytics should never affect app flow
    }
}

function trackPurchase(paymentId) {
    const normalizedPaymentId = String(paymentId || '').trim();
    try {
        if (!normalizedPaymentId) return;
        if (sessionStorage.getItem(META_PURCHASE_KEY) === normalizedPaymentId) return;
        if (trackMetaEvent('Purchase', { value: 79, currency: 'INR' })) {
            sessionStorage.setItem(META_PURCHASE_KEY, normalizedPaymentId);
        }
    } catch (_err) {
        // no-op: analytics should never affect app flow
    }
}

function renderBootErrorPanel(message) {
    const text = String(message || 'BOOT ERROR: home screen not found');
    console.error('[StyleLock boot]', text);
    try {
        document.body.classList.remove('app-booting');
        document.body.innerHTML = `
            <div style="min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:24px;background:#10241f;color:#f3efe3;font-family:Inter,-apple-system,sans-serif;">
                <div style="max-width:420px;width:100%;border:1px solid rgba(243,239,227,0.28);border-radius:14px;padding:18px;background:rgba(7,16,13,0.62);">
                    <div style="font-size:14px;letter-spacing:0.04em;opacity:0.9;">BOOT ERROR: home screen not found</div>
                    <div style="margin-top:10px;font-size:12px;opacity:0.72;word-break:break-word;">${escapeHtml(text)}</div>
                </div>
            </div>
        `;
    } catch (_err) {
        // no-op: last-resort diagnostic path
    }
}

function show(id) {
    const requested = String(id || 'homeScreen');
    const needsLooks = ['resultsScreen', 'cutcardScreen', 'lockedScreen', 'barberScreen'].includes(requested);
    const needsLook = ['cutcardScreen', 'lockedScreen', 'barberScreen'].includes(requested);

    if (needsLooks && !hasValidResultsData()) {
        id = 'homeScreen';
    } else if (needsLook && !hasValidCurrentLook()) {
        id = 'homeScreen';
    }

    document.querySelectorAll('.screen').forEach((s) => {
        s.classList.remove('active');
        s.hidden = true;
    });
    const home = byId('homeScreen');
    const requestedNode = byId(id);
    if (!requestedNode && requested !== 'homeScreen') {
        console.error('[StyleLock boot]', APP_VERSION, `show() requested missing id: ${requested}`);
    }
    const target = requestedNode || home;
    if (!target) {
        renderBootErrorPanel(`show() target missing. requested=${requested}, fallback=homeScreen`);
        return;
    }
    target.classList.add('active');
    target.hidden = false;
    id = target.id;
    if (requested === 'homeScreen' || id === 'homeScreen') {
        console.log('[StyleLock boot]', APP_VERSION, 'show(homeScreen) called');
    }
    currentScreen = id;
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

function hasValidResultsData() {
    return Array.isArray(results?.looks) && results.looks.length > 0;
}

function hasValidCurrentLook() {
    return hasValidResultsData() && currentLookIdx >= 0 && currentLookIdx < results.looks.length;
}

function clearStaleUiState() {
    try {
        const previousVersion = localStorage.getItem(UI_VERSION_KEY);
        const foundKeys = STALE_UI_KEYS.filter((key) => localStorage.getItem(key) !== null || sessionStorage.getItem(key) !== null);
        STALE_UI_KEYS.forEach((key) => {
            localStorage.removeItem(key);
            sessionStorage.removeItem(key);
        });
        if (previousVersion !== APP_VERSION) {
            localStorage.setItem(UI_VERSION_KEY, APP_VERSION);
        }
        if (foundKeys.length) {
            console.log('[StyleLock boot]', APP_VERSION, 'ignored stale screen state:', foundKeys.join(', '));
        }
    } catch (err) {
        console.warn('Unable to reset stale UI state', err);
    }
}

function persistResultsState() {
    try {
        if (hasValidResultsData()) {
            sessionStorage.setItem(RESULTS_SESSION_KEY, JSON.stringify(results));
            sessionStorage.setItem(LOOK_INDEX_SESSION_KEY, String(currentLookIdx));
        }
    } catch (err) {
        console.warn('Unable to persist results state', err);
    }
}

function clearPersistedResultsState() {
    try {
        sessionStorage.removeItem(RESULTS_SESSION_KEY);
        sessionStorage.removeItem(LOOK_INDEX_SESSION_KEY);
    } catch (err) {
        console.warn('Unable to clear persisted results state', err);
    }
}

function persistFreeLookState() {
    try {
        if (freeLookResult) {
            sessionStorage.setItem(FREE_LOOK_SESSION_KEY, JSON.stringify(freeLookResult));
        } else {
            sessionStorage.removeItem(FREE_LOOK_SESSION_KEY);
        }
        if (freeClaimToken) {
            sessionStorage.setItem(FREE_LOOK_CLAIM_KEY, freeClaimToken);
        } else {
            sessionStorage.removeItem(FREE_LOOK_CLAIM_KEY);
        }
    } catch (err) {
        console.warn('Unable to persist free look state', err);
    }
}

function restoreFreeLookState() {
    try {
        const rawLook = sessionStorage.getItem(FREE_LOOK_SESSION_KEY);
        const rawClaim = sessionStorage.getItem(FREE_LOOK_CLAIM_KEY);
        freeLookResult = rawLook ? JSON.parse(rawLook) : null;
        freeClaimToken = rawClaim || '';
    } catch (err) {
        console.warn('Unable to restore free look state', err);
        freeLookResult = null;
        freeClaimToken = '';
    }
}

function clearFreeLookState() {
    freeLookResult = null;
    freeClaimToken = '';
    try {
        sessionStorage.removeItem(FREE_LOOK_SESSION_KEY);
        sessionStorage.removeItem(FREE_LOOK_CLAIM_KEY);
        sessionStorage.removeItem(FREE_LOOK_STAGE_KEY);
        sessionStorage.removeItem(DIRECT_PAID_UPLOAD_KEY);
    } catch (err) {
        console.warn('Unable to clear free look state', err);
    }
}

function setV1Stage(stage) {
    try {
        sessionStorage.setItem(FREE_LOOK_STAGE_KEY, String(stage || 'home'));
    } catch (_err) {
        // no-op
    }
}

function getIstDateKey() {
    try {
        const formatter = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'Asia/Kolkata',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
        const parts = formatter.formatToParts(new Date());
        const map = Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
        if (map.year && map.month && map.day) {
            return `${map.year}-${map.month}-${map.day}`;
        }
    } catch (_err) {
        // no-op
    }
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function readFreeLookBrowserLock() {
    try {
        const raw = localStorage.getItem(FREE_LOOK_BROWSER_LOCK_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return null;
        const today = getIstDateKey();
        if (parsed.date !== today) {
            localStorage.removeItem(FREE_LOOK_BROWSER_LOCK_KEY);
            return null;
        }
        return parsed;
    } catch (_err) {
        return null;
    }
}

function hasUsedFreeLookTodayLocally() {
    return !!readFreeLookBrowserLock();
}

function markFreeLookUsedToday(imageUrl = '') {
    try {
        localStorage.setItem(FREE_LOOK_BROWSER_LOCK_KEY, JSON.stringify({
            date: getIstDateKey(),
            used: true,
            image: String(imageUrl || ''),
            updated_at: new Date().toISOString()
        }));
    } catch (_err) {
        // no-op
    }
}

function clearStaleFreeLookBrowserLock() {
    readFreeLookBrowserLock();
}

function resetFreeLookDevStateIfRequested() {
    try {
        const params = new URLSearchParams(window.location.search || '');
        if (params.get('resetFreeLook') !== '1') return;
        FREE_LOOK_RESET_KEYS.forEach((key) => {
            localStorage.removeItem(key);
            sessionStorage.removeItem(key);
        });
        freeLookResult = null;
        freeClaimToken = '';
        console.log('[StyleLock dev] reset free-look local keys:', FREE_LOOK_RESET_KEYS.join(', '));
        params.delete('resetFreeLook');
        const nextQuery = params.toString();
        const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}${window.location.hash || ''}`;
        history.replaceState(null, '', nextUrl);
    } catch (err) {
        console.warn('[StyleLock dev] unable to reset free-look state', err);
    }
}

function isUsableImageUrl(value) {
    const url = String(value || '').trim();
    if (!url || url === 'null' || url === 'undefined') return false;
    return /^(https?:\/\/|data:image\/|\/static\/|\/)/i.test(url);
}

function waitForImageLoad(url) {
    return new Promise((resolve, reject) => {
        if (!isUsableImageUrl(url)) {
            reject(new Error('Missing generated image'));
            return;
        }
        const image = new Image();
        const timer = setTimeout(() => {
            image.onload = null;
            image.onerror = null;
            reject(new Error('Generated image did not load'));
        }, 9000);
        image.onload = () => {
            clearTimeout(timer);
            resolve(true);
        };
        image.onerror = () => {
            clearTimeout(timer);
            reject(new Error('Generated image did not load'));
        };
        image.src = url;
    });
}

function hasUsableFreeLook(look) {
    return !!look && typeof look === 'object' && isUsableImageUrl(look.image);
}

function showFreeGenerationRetry(message = 'Generation failed. Please try again.') {
    resetLoadingTimers();
    isGenerating = false;
    freeLookResult = null;
    freeClaimToken = '';
    try {
        sessionStorage.removeItem(FREE_LOOK_SESSION_KEY);
        sessionStorage.removeItem(FREE_LOOK_CLAIM_KEY);
    } catch (_err) {
        // no-op
    }
    const errorText = byId('errorText');
    const retryBtn = document.querySelector('#errorScreen .btn-retry');
    const backBtn = byId('errorBackBtn');
    if (errorText) errorText.textContent = message;
    if (retryBtn) {
        retryBtn.textContent = 'TRY AGAIN';
        retryBtn.onclick = async () => {
            try {
                const claim = await reserveFreeLookSlot();
                if (claim.success) {
                    show('uploadScreen');
                }
            } catch (err) {
                console.error(err);
                showUserError(err.message || 'Unable to retry your free look');
            }
        };
    }
    if (backBtn) backBtn.hidden = false;
    show('errorScreen');
}

function resetErrorActions() {
    const retryBtn = document.querySelector('#errorScreen .btn-retry');
    const backBtn = byId('errorBackBtn');
    if (retryBtn) {
        retryBtn.textContent = 'TRY AGAIN';
        retryBtn.onclick = goHome;
    }
    if (backBtn) backBtn.hidden = true;
}

function setDirectPaidAfterUpload(enabled) {
    try {
        if (enabled) {
            sessionStorage.setItem(DIRECT_PAID_UPLOAD_KEY, '1');
        } else {
            sessionStorage.removeItem(DIRECT_PAID_UPLOAD_KEY);
        }
    } catch (_err) {
        // no-op
    }
}

function isDirectPaidAfterUpload() {
    try {
        return sessionStorage.getItem(DIRECT_PAID_UPLOAD_KEY) === '1';
    } catch (_err) {
        return false;
    }
}

function showFreeLookBlockedState(type) {
    const title = byId('waitlistTitle');
    const subtitle = byId('waitlistSubtitle');
    const form = byId('waitlistForm');
    const submitBtn = byId('waitlistSubmitBtn');
    const status = byId('waitlistStatus');
    const email = byId('waitlistEmail');

    if (status) {
        status.hidden = true;
        status.textContent = '';
    }
    if (email) email.value = '';

    if (type === 'already-used') {
        if (title) title.textContent = 'You\u2019ve already used your free look today.';
        if (subtitle) {
            subtitle.hidden = true;
            subtitle.textContent = '';
        }
        if (form) form.hidden = true;
    } else {
        if (title) title.textContent = 'Today\u2019s free looks are full. Leave your email and we\u2019ll notify you when free looks open tomorrow.';
        if (subtitle) {
            subtitle.hidden = true;
            subtitle.textContent = '';
        }
        if (form) form.hidden = false;
        if (submitBtn) submitBtn.textContent = 'NOTIFY ME TOMORROW';
    }

    show('waitlistScreen');
}

function startPaidFromBlockedState() {
    setDirectPaidAfterUpload(true);
    setV1Stage('direct-paid-upload');
    show('uploadScreen');
}

function resetTransientUiData() {
    resetLoadingTimers();
    imageBase64 = '';
    results = null;
    freeLookResult = null;
    freeClaimToken = '';
    uploadMeta = {
        originalBytes: 0,
        compressedBytes: 0,
        longEdge: FREE_LOOK_LONG_EDGE
    };
    currentSlide = 0;
    currentLookIdx = 0;
    isGenerating = false;
    pickerInFlight = false;
    pickerCooldownUntil = 0;

    const uploadPreview = byId('uploadPreview');
    if (uploadPreview) {
        uploadPreview.classList.remove('visible');
        uploadPreview.src = '';
    }
    const uploadPlaceholder = byId('uploadPlaceholder');
    if (uploadPlaceholder) uploadPlaceholder.style.display = 'flex';

    const loadingSelfie = byId('loadingSelfie');
    if (loadingSelfie) loadingSelfie.src = '';
    const progressFill = byId('progressFill');
    if (progressFill) progressFill.style.width = '0%';
    const loadingText = byId('loadingText');
    if (loadingText) loadingText.textContent = 'Finding your next self';
    const loadingTitle = byId('loadingTitle');
    if (loadingTitle) loadingTitle.textContent = 'READING';

    const resultsCarousel = byId('resultsCarousel');
    if (resultsCarousel) resultsCarousel.innerHTML = '';
    const cutcardContent = byId('cutcardContent');
    if (cutcardContent) cutcardContent.innerHTML = '';
    const barberContent = byId('barberContent');
    if (barberContent) barberContent.innerHTML = '';
    const lockedPhoto = byId('lockedPhoto');
    if (lockedPhoto) lockedPhoto.src = '';
    const freeResultCard = byId('freeResultCard');
    if (freeResultCard) freeResultCard.innerHTML = '';
    const waitlistEmail = byId('waitlistEmail');
    if (waitlistEmail) waitlistEmail.value = '';
    const waitlistStatus = byId('waitlistStatus');
    if (waitlistStatus) {
        waitlistStatus.hidden = true;
        waitlistStatus.textContent = '';
    }

    clearPersistedResultsState();
    clearFreeLookState();
}

function bootToHome() {
    clearStaleUiState();
    resetTransientUiData();
    if (window.location.hash) {
        history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    }
    console.log('[StyleLock boot]', APP_VERSION, 'forcing home screen');
    show('homeScreen');
}

function bindStartupDiagnostics() {
    if (diagnosticsBound) return;
    diagnosticsBound = true;

    window.onerror = function (message, source, lineno, colno, error) {
        console.error('[StyleLock boot] window.onerror', { message, source, lineno, colno, error });
    };

    window.onunhandledrejection = function (event) {
        console.error('[StyleLock boot] onunhandledrejection', event?.reason || event);
    };
}

function normalizeActiveScreens() {
    const activeScreens = Array.from(document.querySelectorAll('.screen.active'));
    if (activeScreens.length <= 1) return;

    console.log(
        '[StyleLock boot]',
        APP_VERSION,
        'multiple active screens found, forcing home:',
        activeScreens.map((node) => node.id).join(', ')
    );

    document.querySelectorAll('.screen').forEach((node) => {
        node.classList.remove('active');
        node.hidden = true;
    });
    const home = byId('homeScreen');
    if (home) {
        home.classList.add('active');
        home.hidden = false;
    }
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
    if (loadingCaptionTimer) {
        clearInterval(loadingCaptionTimer);
        loadingCaptionTimer = null;
    }
}

function goHome() {
    bootToHome();
}

function startOver() {
    slTrack('start_over_clicked');
    bootToHome();
}
window.startOver = startOver;

function showUserError(message) {
    resetErrorActions();
    byId('errorText').textContent = message || 'Something went wrong';
    show('errorScreen');
}

function triggerInput(inputId) {
    if (pickerInFlight || isGenerating) return;
    pickerCooldownUntil = Date.now() + 900;
    pickerInFlight = true;
    const input = byId(inputId);
    input.value = '';
    requestAnimationFrame(() => {
        input.click();
        setTimeout(() => {
            pickerInFlight = false;
        }, 750);
    });
}

function triggerLibraryInputDirect() {
    if (pickerInFlight || isGenerating) return;
    pickerCooldownUntil = Date.now() + 1200;
    pickerInFlight = true;

    const input = byId('libraryInput');
    if (!input) {
        pickerInFlight = false;
        return;
    }

    input.value = '';
    input.removeAttribute('multiple');
    input.multiple = false;
    input.removeAttribute('capture');
    input.setAttribute('accept', '.jpg,.jpeg,.png,.heic,.heif,.webp');
    requestAnimationFrame(() => {
        if (typeof input.showPicker === 'function') {
            input.showPicker();
        } else {
            input.click();
        }
    });

    setTimeout(() => {
        pickerInFlight = false;
    }, 900);
}

async function fileToDataUrl(file) {
    return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (event) => resolve(event.target?.result || '');
        reader.onerror = () => reject(new Error('Unable to read selected photo'));
        reader.readAsDataURL(file);
    });
}

async function compressForFreeLook(file) {
    const sourceDataUrl = await fileToDataUrl(file);
    if (!sourceDataUrl || typeof sourceDataUrl !== 'string') {
        throw new Error('Unable to read selected photo');
    }

    const originalBytes = file.size || 0;

    const image = await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Unable to prepare selected photo'));
        img.src = sourceDataUrl;
    });

    const originalWidth = image.naturalWidth || image.width;
    const originalHeight = image.naturalHeight || image.height;
    const longEdge = Math.max(originalWidth, originalHeight);
    const scale = longEdge > FREE_LOOK_LONG_EDGE ? FREE_LOOK_LONG_EDGE / longEdge : 1;
    const targetWidth = Math.max(1, Math.round(originalWidth * scale));
    const targetHeight = Math.max(1, Math.round(originalHeight * scale));

    const canvas = document.createElement('canvas');
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const context = canvas.getContext('2d', { alpha: false });
    context.drawImage(image, 0, 0, targetWidth, targetHeight);

    const compressedDataUrl = canvas.toDataURL('image/jpeg', FREE_LOOK_JPEG_QUALITY);
    const compressedBase64 = compressedDataUrl.includes(',') ? compressedDataUrl.split(',')[1] : compressedDataUrl;
    const compressedBytes = Math.floor((compressedBase64.length * 3) / 4);

    return {
        dataUrl: compressedDataUrl,
        base64: compressedBase64,
        originalBytes,
        compressedBytes,
        longEdge: Math.max(targetWidth, targetHeight)
    };
}

async function reserveFreeLookSlot() {
    clearStaleFreeLookBrowserLock();
    if (hasUsedFreeLookTodayLocally()) {
        showFreeLookBlockedState('already-used');
        return { success: false, handled: true };
    }

    const sessionId = slSessionId();
    const response = await fetch('/api/free-look/claim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
    });
    const data = await response.json().catch(() => ({}));

    if (response.ok && data.success && data.claim_token) {
        freeClaimToken = data.claim_token;
        persistFreeLookState();
        setDirectPaidAfterUpload(false);
        return { success: true };
    }

    if (data.reason === 'already_claimed') {
        if (data.free_look_consumed === true) {
            markFreeLookUsedToday();
        }
        showFreeLookBlockedState('already-used');
        return { success: false, handled: true };
    }

    if (data.reason === 'quota_exhausted') {
        showFreeLookBlockedState('quota-full');
        return { success: false, handled: true };
    }

    if (data.reason === 'already_processing') {
        showFreeGenerationRetry('Generation failed. Please try again.');
        return { success: false, handled: true };
    }

    throw new Error(data.error || 'Unable to reserve a free look');
}

async function generateFreeLook() {
    if (isGenerating || !imageBase64 || !freeClaimToken) return;

    isGenerating = true;
    show('loadingScreen');
    startLoadingAnimation('free');
    setV1Stage('generating-free-look');

    try {
        const resp = await fetch('/api/generate-free-look', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: imageBase64,
                claim_token: freeClaimToken,
                session_id: slSessionId(),
                client_original_bytes: uploadMeta.originalBytes,
                client_compressed_bytes: uploadMeta.compressedBytes,
                client_long_edge: uploadMeta.longEdge
            })
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.success || !hasUsableFreeLook(data.look)) {
            const err = new Error(data.error || 'Generation failed. Please try again.');
            err.canRetry = data.can_retry !== false;
            throw err;
        }

        await waitForImageLoad(data.look.image);
        freeLookResult = data.look;
        markFreeLookUsedToday(data.look.image);
        persistFreeLookState();
        resetLoadingTimers();
        byId('progressFill').style.width = '100%';
        byId('loadingText').textContent = 'Your best look is ready';

        setTimeout(() => {
            renderFreeResult();
            isGenerating = false;
        }, 320);
    } catch (error) {
        console.error(error);
        showFreeGenerationRetry('Generation failed. Please try again.');
    }
}

async function startDirectPaidPayment() {
    if (!imageBase64) {
        showUserError('Upload your selfie first');
        return;
    }
    try {
        const orderRes = await fetch('/api/create-order', { method: 'POST' });
        const orderData = await orderRes.json().catch(() => ({}));

        if (!orderRes.ok || !orderData.success) {
            showUserError(orderData.error || 'Payment service is unavailable');
            return;
        }

        trackInitiateCheckout(orderData.order_id);

        const options = {
            key: orderData.key_id,
            amount: orderData.amount,
            currency: orderData.currency,
            name: 'StyleLock',
            description: 'Unlock Your Next Self',
            order_id: orderData.order_id,
            handler: async function (paymentResponse) {
                try {
                    const verifyRes = await fetch('/api/verify-payment', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            razorpay_order_id: paymentResponse.razorpay_order_id,
                            razorpay_payment_id: paymentResponse.razorpay_payment_id,
                            razorpay_signature: paymentResponse.razorpay_signature,
                        }),
                    });
                    const verifyData = await verifyRes.json().catch(() => ({}));

                    if (!verifyRes.ok || !verifyData.success || !verifyData.payment_token) {
                        showUserError(verifyData.error || 'Payment verification failed');
                        return;
                    }

                    trackPurchase(paymentResponse.razorpay_payment_id);
                    slTrack('payment_successful', { payment_id: paymentResponse.razorpay_payment_id });
                    await generatePaidLooksFromUpload(verifyData.payment_token);
                } catch (verifyErr) {
                    console.error('Payment verification error:', verifyErr);
                    showUserError('Payment verification failed');
                }
            },
            theme: {
                color: '#122b24'
            },
            modal: {
                ondismiss: function () {
                    showUserError('Payment cancelled');
                }
            }
        };

        const rzp = new Razorpay(options);
        rzp.on('payment.failed', function () {
            showUserError('Payment failed');
        });
        slTrack('payment_initiated');
        rzp.open();
    } catch (err) {
        console.error('Payment error:', err);
        showUserError('Server unavailable');
    }
}

async function generatePaidLooksFromUpload(paymentToken) {
    if (isGenerating || !imageBase64 || !paymentToken) return;

    isGenerating = true;
    show('loadingScreen');
    startLoadingAnimation('paid');
    setV1Stage('direct-paid-generating');

    try {
        const resp = await fetch('/api/generate-looks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image: imageBase64,
                payment_token: paymentToken
            })
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.success || !Array.isArray(data.looks)) {
            throw new Error(data.error || 'Unable to unlock your looks');
        }

        results = { looks: normalizeLooks(data.looks) };
        currentLookIdx = 0;
        persistResultsState();
        setDirectPaidAfterUpload(false);
        resetLoadingTimers();
        byId('progressFill').style.width = '100%';
        byId('loadingText').textContent = 'Your 3 looks are ready';

        setTimeout(() => {
            renderResults();
            isGenerating = false;
        }, 320);
    } catch (error) {
        console.error(error);
        resetLoadingTimers();
        isGenerating = false;
        showUserError(error.message || 'Unable to unlock your looks');
    }
}

async function startPayment() {
    if (!freeLookResult) {
        showUserError('Generate your free look first');
        return;
    }
    try {
        const orderRes = await fetch('/api/create-order', { method: 'POST' });
        const orderData = await orderRes.json().catch(() => ({}));

        if (!orderRes.ok || !orderData.success) {
            showUserError(orderData.error || 'Payment service is unavailable');
            return;
        }

        trackInitiateCheckout(orderData.order_id);

        const options = {
            key: orderData.key_id,
            amount: orderData.amount,
            currency: orderData.currency,
            name: 'StyleLock',
            description: 'Unlock Your Next Self',
            order_id: orderData.order_id,
            handler: async function (paymentResponse) {
                try {
                    const verifyRes = await fetch('/api/verify-payment', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            razorpay_order_id: paymentResponse.razorpay_order_id,
                            razorpay_payment_id: paymentResponse.razorpay_payment_id,
                            razorpay_signature: paymentResponse.razorpay_signature,
                        }),
                    });
                    const verifyData = await verifyRes.json().catch(() => ({}));

                    if (!verifyRes.ok || !verifyData.success || !verifyData.payment_token) {
                        showUserError(verifyData.error || 'Payment verification failed');
                        return;
                    }

                    trackPurchase(paymentResponse.razorpay_payment_id);
                    slTrack('payment_successful', { payment_id: paymentResponse.razorpay_payment_id });
                    unlockFullSet(verifyData.payment_token);
                } catch (verifyErr) {
                    console.error('Payment verification error:', verifyErr);
                    showUserError('Payment verification failed');
                }
            },
            theme: {
                color: '#122b24'
            },
            modal: {
                ondismiss: function () {
                    showUserError('Payment cancelled');
                }
            }
        };

        const rzp = new Razorpay(options);
        rzp.on('payment.failed', function () {
            showUserError('Payment failed');
        });
        slTrack('payment_initiated');
        rzp.open();
    } catch (err) {
        console.error('Payment error:', err);
        showUserError('Server unavailable');
    }
}

function startLoadingAnimation(mode = 'paid') {
    const progressFill = byId('progressFill');
    const loadingText = byId('loadingText');
    const loadingTitle = byId('loadingTitle');

    progressFill.style.width = '0%';
    loadingText.textContent = 'Finding your next self';
    loadingTitle.textContent = 'READING';

    const phases = [
        { progress: 18 },
        { progress: 33 },
        { progress: 52 },
        { progress: 73 },
        { progress: 91 }
    ];

    let phaseIdx = 0;
    loadingProgressTimer = setInterval(() => {
        if (phaseIdx >= phases.length) return;
        progressFill.style.width = phases[phaseIdx].progress + '%';
        phaseIdx += 1;
    }, 1700);

    let captionIdx = 0;
    const loadingCaptions = mode === 'free' ? FREE_LOOK_LOADING_CAPTIONS : PAID_LOADING_CAPTIONS;
    loadingText.textContent = loadingCaptions[captionIdx];
    loadingCaptionTimer = setInterval(() => {
        captionIdx = (captionIdx + 1) % loadingCaptions.length;
        loadingText.textContent = loadingCaptions[captionIdx];
    }, 1600);

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

function renderFreeResult() {
    if (!hasUsableFreeLook(freeLookResult)) {
        showFreeGenerationRetry('Generation failed. Please try again.');
        return;
    }

    const heroPct = Math.max(70, Math.min(99, Number(freeLookResult.match_percentage) || 80));
    const imageMarkup = `<img src="${escapeHtml(freeLookResult.image)}" alt="${escapeHtml(freeLookResult.name)}" onerror="showFreeGenerationRetry('Generation failed. Please try again.')">`;

    byId('freeResultCard').innerHTML = `
        <article class="free-result-hero ${tierClass(freeLookResult.tier)}">
            <div class="free-result-media">
                ${imageMarkup}
                <div class="free-result-badge">BEST LOOK</div>
                <div class="free-result-match">${heroPct}% MATCH</div>
            </div>
            <div class="free-result-meta">
                <div class="free-result-row">
                    <div class="free-result-tier">${safeText(freeLookResult.tier, 'LOOK')}</div>
                    <div class="readiness-tag">${safeText(freeLookResult.achievability === 'ready' ? 'Ready now' : 'Worth growing')}</div>
                </div>
                <div class="free-result-name">${safeText(freeLookResult.name)}</div>
            </div>
        </article>
    `;

    hideFreeSaveHint();
    setV1Stage('free-result');
    show('freeResultScreen');
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

async function unlockFullSet(paymentToken) {
    if (isGenerating || !freeLookResult || !paymentToken) return;

    isGenerating = true;
    show('loadingScreen');
    startLoadingAnimation('paid');
    setV1Stage('unlocking-paid');

    try {
        const resp = await fetch('/api/generate-paid-upgrade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                payment_token: paymentToken,
                session_id: slSessionId()
            })
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.detail || 'Generation failed');
        }

        results = {
            looks: normalizeLooks(data.looks)
        };
        currentLookIdx = getMostAchievableIndex(results.looks);
        persistResultsState();

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
    let bestAch = -1;
    let bestMatch = -1;
    looks.forEach((look, idx) => {
        const ach = achievabilityRank(look.achievability);
        const match = Number(look.match_percentage) || 0;
        if (ach > bestAch || (ach === bestAch && match > bestMatch)) {
            bestAch = ach;
            bestMatch = match;
            bestIdx = idx;
        }
    });
    return bestIdx;
}

function buildReadinessMap(looks, heroIdx) {
    const readinessByIdx = {};
    const labels = ['Ready now', 'Needs some growth', 'Future option'];

    const others = looks
        .map((look, idx) => ({ idx, match: Number(look.match_percentage) || 0 }))
        .filter((entry) => entry.idx !== heroIdx)
        .sort((a, b) => b.match - a.match)
        .map((entry) => entry.idx);

    const rankOrder = [heroIdx, ...others].slice(0, 3);
    rankOrder.forEach((idx, rank) => {
        readinessByIdx[idx] = labels[rank] || 'Future option';
    });

    return readinessByIdx;
}

function renderResults() {
    const looks = results?.looks || [];
    if (!looks.length) {
        bootToHome();
        return;
    }

    slTrack('looks_shown', { count: looks.length });

    const heroIdx = getMostAchievableIndex(looks);
    const heroLook = looks[heroIdx];
    const supportingLooks = looks
        .map((item, idx) => ({ item, idx }))
        .filter((entry) => entry.idx !== heroIdx)
        .sort((a, b) => (Number(b.item.match_percentage) || 0) - (Number(a.item.match_percentage) || 0))
        .slice(0, 2);
    const readinessMap = buildReadinessMap(looks, heroIdx);

    const heroPct = Math.max(70, Math.min(99, Number(heroLook.match_percentage) || 80));
    const heroImageMarkup = heroLook.image
        ? `<img class="slide-image" src="${escapeHtml(heroLook.image)}" alt="${escapeHtml(heroLook.name)}">`
        : `<div class="slide-image-placeholder">Look preview unavailable.<br>Use this cut card for your barber.</div>`;

    byId('resultsCarousel').innerHTML = `
        <div class="results-board">
            <article class="slide-card hero-card ${tierClass(heroLook.tier)}">
                <div class="slide-image-wrap">
                    ${heroImageMarkup}
                    <div class="achievable-badge">MOST ACHIEVABLE</div>
                    <div class="match-badge"><span class="pct">${heroPct}%</span><span class="copy">MATCH</span></div>
                    <div class="slide-note">${getTierNote(heroLook.tier)}</div>
                </div>
                <div class="slide-tier">
                    <div class="slide-tier-row">
                        <div class="slide-tier-name">${safeText(heroLook.tier, 'LOOK')}</div>
                        <div class="readiness-tag readiness-hero">${safeText(readinessMap[heroIdx], 'Ready now')}</div>
                    </div>
                </div>
                <button class="btn-select hero-cta" onclick="lockLook(${heroIdx})">LOCK THIS LOOK</button>
            </article>

            <div class="results-support-grid">
                ${supportingLooks.map((support) => {
                    const supportPct = Math.max(70, Math.min(99, Number(support.item.match_percentage) || 80));
                    const supportImage = support.item.image
                        ? `<img class="support-card-image" src="${escapeHtml(support.item.image)}" alt="${escapeHtml(support.item.name)}">`
                        : `<div class="slide-image-placeholder">Preview pending</div>`;
                    return `
                        <article class="support-card ${tierClass(support.item.tier)}">
                            <div class="support-card-image-wrap">
                                ${supportImage}
                                <div class="support-match">${supportPct}% MATCH</div>
                            </div>
                            <div class="support-card-meta">
                                <div class="support-card-row">
                                    <div class="support-tier">${safeText(support.item.tier, 'LOOK')}</div>
                                    <div class="readiness-tag support-readiness">${safeText(readinessMap[support.idx], 'Future option')}</div>
                                </div>
                                <button class="support-cta" onclick="selectLook(${support.idx})">VIEW CUT CARD</button>
                            </div>
                        </article>
                    `;
                }).join('')}
            </div>
        </div>
    `;

    setV1Stage('results');
    show('resultsScreen');
}

function goSlide(nextIdx, skipCueUpdate = false) {
    if (RESULTS_STATIC_BOARD) return;
    const looks = results?.looks || [];
    if (!looks.length) return;

    currentSlide = Math.max(0, Math.min(nextIdx, looks.length - 1));
    byId('resultsCarousel').style.transform = `translateX(-${currentSlide * 100}%)`;

    document.querySelectorAll('.dot').forEach((dot, idx) => {
        dot.classList.toggle('active', idx === currentSlide);
    });

}

function selectLook(idx) {
    const look = results?.looks?.[idx];
    if (!look) {
        bootToHome();
        return;
    }
    openLockedPreview(idx, false);
}

function backToResults() {
    if (!hasValidResultsData()) {
        bootToHome();
        return;
    }
    persistResultsState();
    show('resultsScreen');
}

function lockLook(idx) {
    const look = results?.looks?.[idx];
    if (!look) {
        bootToHome();
        return;
    }
    openLockedPreview(idx, true);
}

function renderCutcard(idx) {
    const look = results?.looks?.[idx];
    if (!look) {
        bootToHome();
        return;
    }

    currentLookIdx = idx;
    slTrack('look_expanded', { look: slLookTier(idx), idx: idx });
    slTrack('cut_card_viewed', { look: slLookTier(idx), idx: idx });
    persistResultsState();
    byId('cutcardContent').innerHTML = `
        <article class="cutcard-main ${tierClass(look.tier)}">
            <div class="cutcard-media">
                ${look.image ? `<img class="cutcard-photo" src="${escapeHtml(look.image)}" alt="${escapeHtml(look.name)}">` : `<div class="slide-image-placeholder">Preview unavailable</div>`}
                <div class="cutcard-look-tag">SECONDARY LOOK</div>
                <div class="cutcard-tier">${safeText(look.tier, 'LOOK')}</div>
            </div>
            <div class="cutcard-meta">
                <div class="cut-meta">
                    <div class="cut-meta-label">MATCH</div>
                    <div class="cut-meta-value">${Math.max(70, Math.min(99, Number(look.match_percentage) || 80))}%</div>
                </div>
                <div class="cut-meta">
                    <div class="cut-meta-label">READINESS</div>
                    <div class="cut-meta-value">${safeText(look.achievability, 'Ready')}</div>
                </div>
                <div class="cut-meta">
                    <div class="cut-meta-label">VIBE</div>
                    <div class="cut-meta-value">${safeText(look.vibe)}</div>
                </div>
            </div>
            <div class="cutcard-sections">
                <section class="cutcard-section">
                    <div class="cutcard-label">BARBER BRIEF</div>
                    <div class="cutcard-value">${safeText(look.name, safeText(look.tier, 'Look'))}</div>
                    <div class="cutcard-desc">Balanced for your current face shape, hair density, and what is actually reachable now.</div>
                </section>
                <section class="cutcard-section">
                    <div class="cutcard-label">TOP</div>
                    <div class="cutcard-value">${safeText(look.top_length)}</div>
                    <div class="cutcard-desc">Keep the top length intentional so the overall silhouette stays clean instead of overgrowing into bulk.</div>
                </section>
                <section class="cutcard-section">
                    <div class="cutcard-label">SIDES</div>
                    <div class="cutcard-value">${safeText(look.sides)}</div>
                    <div class="cutcard-desc">The sides should taper neatly to support the face and make the shape read sharper from the front.</div>
                </section>
                <section class="cutcard-section">
                    <div class="cutcard-label">TEXTURE + STYLING</div>
                    <div class="cutcard-value">${safeText(look.texture)}</div>
                    <div class="cutcard-desc">${safeText(look.styling)} Use ${safeText(look.products).toLowerCase()} for hold and finish.</div>
                </section>
                <section class="cutcard-section">
                    <div class="cutcard-label">FRINGE</div>
                    <div class="cutcard-value">${safeText(look.fringe)}</div>
                    <div class="cutcard-desc">Ask your barber to keep the front balanced so it frames the face without collapsing into the eyes.</div>
                </section>
            </div>
        </article>
    `;

    const selectBtn = byId('selectLookBtn');
    if (selectBtn) {
        selectBtn.textContent = 'SELECT THIS LOOK';
        selectBtn.onclick = () => openLockedPreview(idx, true);
    }

    show('cutcardScreen');
}

function openLockedPreview(idx, showStamp) {
    const look = results?.looks?.[idx];
    if (!look) {
        bootToHome();
        return;
    }

    currentLookIdx = idx;
    // The LOCKED badge should only appear on the hero look (MOST ACHIEVABLE / TRENDING).
    // On secondary expanded views (CLEAN / BOLD), the badge is visually redundant â€”
    // all three looks are already paid for at this point in the flow.
    const heroIdx = Array.isArray(results?.looks) ? getMostAchievableIndex(results.looks) : 0;
    const isHero = idx === heroIdx;
    lockedStampVisible = !!showStamp && isHero;
    byId('lockedPhoto').src = look.image || '';
    persistResultsState();

    const lockedBadge = document.querySelector('.locked-badge');
    if (lockedBadge) {
        lockedBadge.classList.toggle('hidden', !lockedStampVisible);
    }
    show('lockedScreen');
}

function backToLocked() {
    backToResults();
}

function showBarber() {
    const look = results?.looks?.[currentLookIdx];
    if (!look) {
        bootToHome();
        return;
    }

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

    persistResultsState();
    show('barberScreen');
}

async function fetchImageForSave(imageUrl) {
    const response = await fetch(imageUrl, { mode: 'cors' });
    if (!response.ok) {
        throw new Error(`Unable to fetch image (${response.status})`);
    }
    const blob = await response.blob();
    if (!blob || !blob.size || !String(blob.type || '').startsWith('image/')) {
        throw new Error('Downloaded image is invalid');
    }
    return blob;
}

function showFreeSaveHint(message = 'Long press the image to save') {
    const hint = byId('freeSaveHint');
    if (!hint) return;
    hint.textContent = message;
    hint.hidden = false;
}

function hideFreeSaveHint() {
    const hint = byId('freeSaveHint');
    if (!hint) return;
    hint.hidden = true;
    hint.textContent = 'Long press the image to save';
}

function openImageSaveFallback(imageUrl) {
    if (!imageUrl) return;
    showFreeSaveHint('Long press the image to save');
    window.open(imageUrl, '_blank', 'noopener');
}

function triggerImageDownload(imageUrl, fileName) {
    const a = document.createElement('a');
    a.href = imageUrl;
    a.download = fileName;
    a.target = '_blank';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
}

async function saveImageAsset(imageUrl, fileName, options = {}) {
    if (!imageUrl) return;

    const isLikelyIos = /iP(hone|ad|od)/i.test(window.navigator?.userAgent || '');
    const preferOpenFallback = options.preferOpenFallback === true;

    try {
        const blob = await fetchImageForSave(imageUrl);
        const extension = (blob.type && blob.type.split('/')[1]) ? blob.type.split('/')[1].replace('jpeg', 'jpg') : 'jpg';
        const finalName = fileName || `stylelock-look.${extension}`;

        if (navigator.share && navigator.canShare) {
            const file = new File([blob], finalName, { type: blob.type || 'image/jpeg' });
            if (navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({
                        files: [file],
                        title: 'StyleLock look',
                        text: 'Your StyleLock look'
                    });
                    return;
                } catch (shareError) {
                    if (shareError?.name === 'AbortError') {
                        return;
                    }
                    console.warn('[StyleLock save] share failed, falling back', shareError);
                }
            }
        }

        const objectUrl = URL.createObjectURL(blob);
        try {
            if (preferOpenFallback && isLikelyIos) {
                openImageSaveFallback(objectUrl);
            } else {
                triggerImageDownload(objectUrl, finalName);
            }
        } finally {
            setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
        }
    } catch (error) {
        console.warn('[StyleLock save] fallback path:', error);
        openImageSaveFallback(imageUrl);
    }
}

async function saveFreeLookToPhone() {
    const look = freeLookResult;
    if (!look || !look.image) return;

    hideFreeSaveHint();
    await saveImageAsset(look.image, 'stylelock-free-look.jpg', { preferOpenFallback: true });
}

async function saveToPhone() {
    const look = results?.looks?.[currentLookIdx];
    if (!look || !look.image) return;

    await saveImageAsset(look.image, 'stylelock-look.jpg');
}

async function handleImage(event) {
    const file = event.target.files?.[0];
    pickerInFlight = false;
    if (!file || isGenerating) return;

    try {
        const prepared = await compressForFreeLook(file);
        imageBase64 = prepared.base64;
        uploadMeta = {
            originalBytes: prepared.originalBytes,
            compressedBytes: prepared.compressedBytes,
            longEdge: prepared.longEdge
        };

        console.log('[StyleLock free-look] upload prepared', uploadMeta);
        const preview = byId('uploadPreview');
        preview.src = prepared.dataUrl;
        preview.classList.add('visible');
        byId('uploadPlaceholder').style.display = 'none';
        byId('loadingSelfie').src = prepared.dataUrl;

        slTrack('selfie_uploaded');
        const directPaid = isDirectPaidAfterUpload();
        setTimeout(() => {
            if (directPaid) {
                startDirectPaidPayment();
            } else {
                generateFreeLook();
            }
        }, 260);
    } catch (error) {
        console.error(error);
        byId('errorText').textContent = error.message || 'Unable to read selected photo';
        show('errorScreen');
    }
}

function bindEvents() {
    if (eventsBound) return;
    eventsBound = true;

    byId('unlockBtn').addEventListener('click', () => {
        setV1Stage('screen-two');
        show('screenTwoScreen');
    });
    byId('freeLookBtn').addEventListener('click', async () => {
        try {
            const claim = await reserveFreeLookSlot();
            if (claim.success) {
                setV1Stage('upload');
                show('uploadScreen');
            }
        } catch (error) {
            console.error(error);
            showUserError(error.message || 'Unable to start your free look');
        }
    });
    byId('unlockAllBtn').addEventListener('click', startPayment);
    byId('waitlistPaidBtn').addEventListener('click', startPaidFromBlockedState);
    byId('saveFreeLookBtn').addEventListener('click', () => {
        saveFreeLookToPhone().catch((error) => {
            console.error(error);
            showFreeSaveHint('Long press the image to save');
        });
    });

    byId('takePhotoBtn').addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        triggerInput('cameraInput');
    });
    byId('uploadPhotoBtn').addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        triggerLibraryInputDirect();
    });

    byId('cameraInput').addEventListener('change', handleImage);
    byId('libraryInput').addEventListener('change', handleImage);
    byId('waitlistForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const email = byId('waitlistEmail')?.value?.trim();
        const status = byId('waitlistStatus');
        if (!email) return;
        try {
            const resp = await fetch('/api/free-look/waitlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    session_id: slSessionId()
                })
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data.success) {
                throw new Error(data.error || 'Unable to join waitlist');
            }
            status.hidden = false;
            status.textContent = 'Youâ€™re on the list. Weâ€™ll email you tomorrow.';
        } catch (error) {
            status.hidden = false;
            status.textContent = error.message || 'Unable to save your email right now.';
        }
    });
    byId('resultsScreen').addEventListener('touchstart', (event) => {
        if (RESULTS_STATIC_BOARD) return;
        touchStartX = event.touches[0].clientX;
    }, { passive: true });

    byId('resultsScreen').addEventListener('touchend', (event) => {
        if (RESULTS_STATIC_BOARD) return;
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

function bootApp() {
    bindStartupDiagnostics();
    syncViewportHeight();
    console.log('[StyleLock boot]', APP_VERSION, 'boot started');

    const homeNode = byId('homeScreen');
    console.log('[StyleLock boot]', APP_VERSION, 'homeScreen found:', !!homeNode);
    if (!homeNode) {
        renderBootErrorPanel('homeScreen id is missing in app.html');
        return;
    }

    syncInAppBrowserHint();
    resetFreeLookDevStateIfRequested();
    clearStaleFreeLookBrowserLock();
    trackViewContentOnce();

    const activeNodes = Array.from(document.querySelectorAll('.screen.active'));
    const initialActive = activeNodes[0]?.id || 'none';
    const activeList = activeNodes.map((node) => node.id);
    console.log('[StyleLock boot]', APP_VERSION, 'active screens found:', activeList);
    console.log('[StyleLock boot]', APP_VERSION, 'initial active screen:', initialActive);
    if (activeNodes.length > 1) {
        console.log('[StyleLock boot]', APP_VERSION, 'multiple active screens in DOM:', activeNodes.map((node) => node.id).join(', '));
    }

    try {
        normalizeActiveScreens();
        bindEvents();
        bootToHome();
    } catch (err) {
        console.error('[StyleLock boot] boot error', err);
        console.log('[StyleLock boot]', APP_VERSION, 'boot fallback triggered -> home');
        try {
            show('homeScreen');
        } catch (_showErr) {
            const home = byId('homeScreen');
            if (home) {
                document.querySelectorAll('.screen').forEach((node) => {
                    node.classList.remove('active');
                    node.hidden = true;
                });
                home.classList.add('active');
                home.hidden = false;
                currentScreen = 'homeScreen';
            } else {
                renderBootErrorPanel('boot fallback failed: homeScreen missing');
            }
        }
    } finally {
        if (document.body) document.body.classList.remove('app-booting');
        console.log('[StyleLock] removed app-booting class');
        const finalActive = document.querySelector('.screen.active')?.id || currentScreen || 'homeScreen';
        console.log('[StyleLock boot]', APP_VERSION, 'active screen now:', finalActive);
        console.log('[StyleLock boot]', APP_VERSION, 'final visible screen:', finalActive);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootApp, { once: true });
} else {
    bootApp();
}

window.addEventListener('resize', syncViewportHeight, { passive: true });
window.addEventListener('orientationchange', () => {
    setTimeout(syncViewportHeight, 120);
});

// visualViewport fires for iOS Safari toolbar show/hide and for Instagram
// webview keyboard/chrome transitions â€” window.resize does NOT fire for these.
if (typeof window !== 'undefined' && window.visualViewport) {
    window.visualViewport.addEventListener('resize', syncViewportHeight, { passive: true });
}

window.addEventListener('pageshow', (event) => {
    syncViewportHeight();
    if (event.persisted) {
        bootToHome();
    }
});





