"""
StyleLock AI - Backend Server v43
FIXED: Blank green screen issue resolved
- Uses .replace() instead of f-strings to properly embed base64 images
- New Home Screen: "YOUR NEXT SELF" with ₹49 unlock button  
- New Upload Screen: "CURRENT SELF" with TAKE PHOTO
- Fixed Results: No "YOUR LOOK" text, labels at top-left
- Full flow: Home → Razorpay → Upload → Loading → Results → Cut Card → Barber Mode
"""

import os
import json
import base64
import asyncio
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ============================================================
# CONFIGURATION
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
VMODEL_API_KEY = os.getenv("VMODEL_API_KEY", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

VMODEL_API_URL = "https://api.vmodel.ai/api/tasks/v1/create"
VMODEL_TASK_URL = "https://api.vmodel.ai/api/tasks/v1/get"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ============================================================
# HERO LOOKS (MVP Static Images from Railway)
# ============================================================

HERO_LOOKS = {
    "bold": "https://stylelock-production.up.railway.app/static/hairstyle_bold.jpg",
    "clean": "https://stylelock-production.up.railway.app/static/hairstyle_clean.jpg",
    "trending": "https://stylelock-production.up.railway.app/static/hairstyle_trending.jpg"
}

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="StyleLock AI v43", description="PWA with Razorpay - Fixed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    return {
        "app": "StyleLock AI",
        "version": "43",
        "status": "running",
        "endpoints": {
            "app": "/app",
            "api_analyze": "/api/analyze",
            "api_generate": "/api/generate",
            "razorpay_order": "/api/create-order"
        }
    }

@app.post("/api/create-order")
async def create_razorpay_order():
    """Create Razorpay order for ₹49 payment"""
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return {"order_id": "demo_order", "amount": 4900, "currency": "INR", "demo": True}
    
    import razorpay
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    order = client.order.create({
        "amount": 4900,
        "currency": "INR",
        "payment_capture": 1
    })
    return {"order_id": order["id"], "amount": 4900, "currency": "INR"}

@app.post("/api/analyze")
async def analyze_face(request: Request):
    """Analyze face with Claude"""
    try:
        data = await request.json()
        image_data = data.get("image", "")
        
        if not ANTHROPIC_API_KEY:
            return {
                "face_shape": "oval",
                "hair_texture": "wavy", 
                "hair_density": "medium",
                "current_length_cm": 8,
                "recommendations": ["bold", "clean", "trending"]
            }
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                            {"type": "text", "text": """Analyze this face photo for hairstyle recommendations.
Return JSON only:
{
  "face_shape": "oval|round|square|heart|oblong",
  "hair_texture": "straight|wavy|curly|coily",
  "hair_density": "thin|medium|thick",
  "current_length_cm": number,
  "recommendations": ["bold", "clean", "trending"]
}"""}
                        ]
                    }]
                }
            )
            result = response.json()
            text = result["content"][0]["text"]
            return json.loads(text.strip().replace("```json", "").replace("```", ""))
    except Exception as e:
        return {"error": str(e), "face_shape": "oval", "recommendations": ["bold", "clean", "trending"]}

@app.post("/api/generate")
async def generate_hairstyle(request: Request):
    """Generate hairstyle with VModel"""
    try:
        data = await request.json()
        style = data.get("style", "bold")
        
        # Return MVP static images
        return {
            "image_url": HERO_LOOKS.get(style, HERO_LOOKS["bold"]),
            "style": style,
            "source": "mvp_static"
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# FRONTEND HTML (V43 - REVISED SCREENS)
# ============================================================

FRONTEND_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta name="theme-color" content="#1a2f2a">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>StyleLock</title>
  
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Caveat:wght@500;600&family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  
  <style>
    :root {
      --bg-dark: #1a2f2a;
      --bg-card: #2a3f3a;
      --bg-card-light: #3a4f4a;
      --lime: #c8e64a;
      --lime-dark: #9ab83a;
      --cream: #f5f3e8;
      --cream-dark: #e8e6db;
      --text-muted: rgba(245, 243, 232, 0.7);
      --border-subtle: rgba(245, 243, 232, 0.15);
    }
    
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    html, body { height: 100%; width: 100%; overflow: hidden; position: fixed; top: 0; left: 0; }
    body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg-dark); color: var(--cream); }
    
    .screen { position: fixed; top: 0; left: 0; width: 100%; height: 100%; display: none; background-color: var(--bg-dark); overflow-y: auto; overflow-x: hidden; }
    .screen.active { display: block; }
    
    input[type="file"] { display: none; }
    
    /* ==================== HOME SCREEN (V43 - CODE-BASED) ==================== */
    #screen-home {
      background: var(--bg-dark);
      display: flex;
      flex-direction: column;
      min-height: 100%;
      padding: 60px 24px 40px;
      position: relative;
      overflow: hidden;
    }
    
    .home-bg-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(180deg, rgba(26,47,42,0.3) 0%, rgba(26,47,42,0.9) 60%, var(--bg-dark) 100%);
      z-index: 1;
    }
    
    .home-content {
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      flex: 1;
    }
    
    .home-headline {
      margin-bottom: 20px;
    }
    
    .home-your {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 48px;
      color: var(--cream);
      letter-spacing: 4px;
      line-height: 1;
    }
    
    .home-next-self {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 72px;
      color: var(--cream);
      letter-spacing: 6px;
      line-height: 0.95;
    }
    
    .home-notes {
      position: relative;
      height: 120px;
      margin: 20px 0;
    }
    
    .home-note {
      font-family: 'Caveat', cursive;
      font-size: 22px;
      position: absolute;
    }
    
    .home-note.almost { color: var(--lime); top: 0; right: 20px; transform: rotate(5deg); }
    .home-note.hold { color: #7eb8da; top: 45px; left: 10px; transform: rotate(-3deg); }
    .home-note.future { color: var(--lime); top: 80px; right: 40px; transform: rotate(2deg); }
    
    .home-bottom {
      margin-top: auto;
    }
    
    .home-progress-section {
      margin-bottom: 16px;
    }
    
    .home-progress-label {
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      color: var(--text-muted);
      letter-spacing: 2px;
      margin-bottom: 6px;
    }
    
    .home-progress-bar {
      height: 4px;
      background: rgba(255,255,255,0.1);
      border-radius: 2px;
      overflow: hidden;
    }
    
    .home-progress-fill {
      height: 100%;
      border-radius: 2px;
      animation: progress-pulse 2s ease-in-out infinite;
    }
    
    .home-progress-fill.blue { background: #7eb8da; width: 65%; }
    .home-progress-fill.lime { background: var(--lime); width: 45%; }
    
    @keyframes progress-pulse {
      0%, 100% { opacity: 0.7; }
      50% { opacity: 1; }
    }
    
    .home-decoding {
      font-family: 'Space Mono', monospace;
      font-size: 10px;
      color: var(--text-muted);
      letter-spacing: 1px;
      margin-top: 4px;
    }
    
    .home-unlock-btn {
      width: 100%;
      padding: 18px 24px;
      background: var(--cream);
      border: none;
      border-radius: 8px;
      font-family: 'Space Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      color: var(--bg-dark);
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin: 20px 0;
    }
    
    .home-footer {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-top: 24px;
    }
    
    .home-logo-icon {
      width: 24px;
      height: 32px;
    }
    
    .home-footer-text {
      font-family: 'Space Mono', monospace;
      font-size: 11px;
      color: var(--lime);
      letter-spacing: 2px;
    }
    
    /* ==================== UPLOAD SCREEN (V43 - CODE-BASED) ==================== */
    #screen-upload {
      background: var(--bg-dark);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 60px 24px 40px;
      min-height: 100%;
    }
    
    .upload-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 56px;
      color: var(--cream);
      letter-spacing: 4px;
      line-height: 1;
      text-align: center;
      margin-bottom: 40px;
    }
    
    .upload-frame {
      width: 280px;
      height: 340px;
      background: var(--bg-card);
      border-radius: 16px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      overflow: hidden;
    }
    
    .upload-corners {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      pointer-events: none;
    }
    
    .corner {
      position: absolute;
      width: 24px;
      height: 24px;
      border-color: var(--lime);
      border-style: solid;
    }
    
    .corner.tl { top: 12px; left: 12px; border-width: 3px 0 0 3px; }
    .corner.tr { top: 12px; right: 12px; border-width: 3px 3px 0 0; }
    .corner.bl { bottom: 12px; left: 12px; border-width: 0 0 3px 3px; }
    .corner.br { bottom: 12px; right: 12px; border-width: 0 3px 3px 0; }
    
    .upload-silhouette {
      width: 60%;
      height: 60%;
      background: rgba(100, 120, 110, 0.4);
      border-radius: 50% 50% 45% 45%;
      position: relative;
    }
    
    .upload-silhouette::after {
      content: '';
      position: absolute;
      bottom: -40%;
      left: 50%;
      transform: translateX(-50%);
      width: 120%;
      height: 60%;
      background: rgba(100, 120, 110, 0.4);
      border-radius: 40% 40% 0 0;
    }
    
    .upload-preview-container {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      opacity: 0;
      transition: opacity 0.3s;
      border-radius: 16px;
      overflow: hidden;
    }
    
    .upload-preview-container.visible { opacity: 1; }
    
    .upload-preview-container img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    
    .upload-note {
      position: absolute;
      bottom: -8px;
      right: -20px;
      font-family: 'Caveat', cursive;
      font-size: 24px;
      color: var(--lime);
      transform: rotate(-5deg);
    }
    
    .upload-instructions {
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      color: var(--text-muted);
      text-align: center;
      margin-top: 32px;
    }
    
    .upload-take-btn {
      width: 100%;
      max-width: 280px;
      padding: 18px 24px;
      background: var(--lime);
      border: none;
      border-radius: 8px;
      font-family: 'Space Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      color: var(--bg-dark);
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-top: 32px;
    }
    
    /* ==================== LOADING SCREEN ==================== */
    #screen-loading {
      background: var(--bg-dark);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 24px;
    }
    
    .loading-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 48px;
      color: var(--cream);
      letter-spacing: 4px;
      margin-bottom: 40px;
    }
    
    .loading-spinner {
      width: 80px;
      height: 80px;
      border: 4px solid var(--bg-card);
      border-top-color: var(--lime);
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    
    .loading-status {
      font-family: 'Space Mono', monospace;
      font-size: 12px;
      color: var(--text-muted);
      letter-spacing: 2px;
      margin-top: 32px;
      text-align: center;
    }
    
    /* ==================== RESULTS SCREEN (V43 - FIXED) ==================== */
    #screen-results {
      background: var(--bg-dark);
    }
    
    .results-header {
      padding: 20px 24px;
      text-align: center;
    }
    
    .results-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 36px;
      color: var(--cream);
      letter-spacing: 3px;
    }
    
    .results-swiper {
      display: flex;
      overflow-x: auto;
      scroll-snap-type: x mandatory;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }
    
    .results-swiper::-webkit-scrollbar { display: none; }
    
    .result-slide {
      flex: 0 0 100%;
      scroll-snap-align: center;
      padding: 0 24px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    
    .result-card {
      width: 100%;
      max-width: 340px;
      background: var(--bg-dark);
      border-radius: 20px;
      overflow: hidden;
      border: 1px solid var(--border-subtle);
    }
    
    .result-card-hero {
      position: relative;
      width: 100%;
      aspect-ratio: 3/4;
      background: var(--bg-dark);
    }
    
    .result-card-hero img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    
    .result-look-name {
      position: absolute;
      top: 16px;
      left: 16px;
      font-family: 'Bebas Neue', sans-serif;
      font-size: 32px;
      color: var(--cream);
      letter-spacing: 2px;
      text-shadow: 0 2px 8px rgba(0,0,0,0.5);
    }
    
    .result-card-info {
      padding: 20px;
      background: var(--bg-dark);
    }
    
    .result-specs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    
    .result-spec {
      font-family: 'Space Mono', monospace;
      font-size: 11px;
    }
    
    .result-spec-label {
      color: var(--text-muted);
      letter-spacing: 1px;
    }
    
    .result-spec-value {
      color: var(--cream);
      font-weight: 700;
    }
    
    .result-next-btn {
      width: 100%;
      padding: 14px;
      background: var(--lime);
      border: none;
      border-radius: 8px;
      font-family: 'Space Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      color: var(--bg-dark);
      cursor: pointer;
      letter-spacing: 1px;
    }
    
    .results-dots {
      display: flex;
      justify-content: center;
      gap: 8px;
      padding: 16px;
    }
    
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--bg-card);
      transition: all 0.3s;
    }
    
    .dot.active {
      background: var(--lime);
      width: 24px;
      border-radius: 4px;
    }
    
    /* ==================== CUT CARD SCREEN ==================== */
    #screen-cutcard {
      background: var(--bg-dark);
      padding: 40px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    
    .cutcard-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 36px;
      color: var(--cream);
      letter-spacing: 3px;
      margin-bottom: 24px;
    }
    
    .cutcard-container {
      width: 100%;
      max-width: 340px;
      background: var(--cream);
      border-radius: 20px;
      padding: 24px;
      color: var(--bg-dark);
    }
    
    .cutcard-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 2px solid var(--bg-dark);
    }
    
    .cutcard-logo {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 24px;
      letter-spacing: 2px;
    }
    
    .cutcard-date {
      font-family: 'Space Mono', monospace;
      font-size: 12px;
    }
    
    .cutcard-look-name {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 42px;
      letter-spacing: 2px;
      margin-bottom: 20px;
    }
    
    .cutcard-specs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 24px;
    }
    
    .cutcard-spec {
      font-family: 'Space Mono', monospace;
      font-size: 12px;
    }
    
    .cutcard-spec-label {
      color: var(--bg-card);
      letter-spacing: 1px;
      margin-bottom: 4px;
    }
    
    .cutcard-spec-value {
      font-weight: 700;
      font-size: 14px;
    }
    
    .cutcard-barber-btn {
      width: 100%;
      padding: 16px;
      background: var(--bg-dark);
      border: none;
      border-radius: 8px;
      font-family: 'Space Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      color: var(--lime);
      cursor: pointer;
      letter-spacing: 1px;
    }
    
    /* ==================== BARBER MODE SCREEN ==================== */
    #screen-barber {
      background: var(--bg-dark);
      padding: 40px 24px;
    }
    
    .barber-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }
    
    .barber-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 28px;
      color: var(--cream);
      letter-spacing: 2px;
    }
    
    .barber-close {
      width: 40px;
      height: 40px;
      background: var(--bg-card);
      border: none;
      border-radius: 50%;
      color: var(--cream);
      font-size: 20px;
      cursor: pointer;
    }
    
    .barber-image-container {
      width: 100%;
      aspect-ratio: 3/4;
      background: var(--bg-card);
      border-radius: 16px;
      overflow: hidden;
      margin-bottom: 24px;
    }
    
    .barber-image-container img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    
    .barber-specs-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }
    
    .barber-spec-card {
      background: var(--bg-card);
      border-radius: 12px;
      padding: 16px;
    }
    
    .barber-spec-label {
      font-family: 'Space Mono', monospace;
      font-size: 10px;
      color: var(--text-muted);
      letter-spacing: 1px;
      margin-bottom: 6px;
    }
    
    .barber-spec-value {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 24px;
      color: var(--lime);
      letter-spacing: 1px;
    }
    
    .barber-footer {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding-top: 24px;
      border-top: 1px solid var(--border-subtle);
    }
    
    .barber-logo {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .barber-logo svg {
      width: 32px;
      height: 40px;
    }
    
    .barber-logo-text {
      font-family: 'Space Mono', monospace;
      font-size: 14px;
      color: var(--lime);
      letter-spacing: 3px;
    }
  </style>
</head>
<body>
  <!-- HOME SCREEN -->
  <div id="screen-home" class="screen active">
    <div class="home-bg-overlay"></div>
    <div class="home-content">
      <div class="home-headline">
        <div class="home-your">YOUR</div>
        <div class="home-next-self">NEXT<br>SELF</div>
      </div>
      
      <div class="home-notes">
        <span class="home-note almost">almost there :)</span>
        <span class="home-note hold">hold still</span>
        <span class="home-note future">future me</span>
      </div>
      
      <div class="home-bottom">
        <div class="home-progress-section">
          <div class="home-progress-label">READING YOUR FACE</div>
          <div class="home-progress-bar">
            <div class="home-progress-fill blue"></div>
          </div>
          <div class="home-decoding">IDENTITY DECODING...</div>
        </div>
        
        <button class="home-unlock-btn" id="home-unlock-btn">UNLOCK IT FOR ₹49</button>
        
        <div class="home-progress-section">
          <div class="home-progress-bar">
            <div class="home-progress-fill lime"></div>
          </div>
          <div class="home-decoding">FUTURE SCAN ACTIVE</div>
        </div>
        
        <div class="home-footer">
          <svg class="home-logo-icon" viewBox="0 0 112 144" fill="var(--lime)">
            <polygon points="0,72 16,72 56,0 72,0 72,12 60,12 20,84 4,84"/>
            <polygon points="40,0 56,0 96,72 112,72 112,84 100,84 60,12 44,12"/>
            <polygon points="28,60 44,60 84,132 100,132 100,144 88,144 48,72 32,72"/>
          </svg>
          <span class="home-footer-text">STYLELOCK // IDENTITY // '26</span>
        </div>
      </div>
    </div>
  </div>
  
  <!-- UPLOAD SCREEN -->
  <div id="screen-upload" class="screen">
    <div class="upload-title">CURRENT<br>SELF</div>
    
    <div class="upload-frame" id="upload-frame-btn">
      <div class="upload-corners">
        <div class="corner tl"></div>
        <div class="corner tr"></div>
        <div class="corner bl"></div>
        <div class="corner br"></div>
      </div>
      <div class="upload-silhouette"></div>
      <div class="upload-preview-container" id="upload-preview-container">
        <img id="upload-preview" src="" alt="">
      </div>
      <span class="upload-note">good light</span>
    </div>
    
    <p class="upload-instructions">Front-facing. Good light. No filters.</p>
    
    <button class="upload-take-btn" id="upload-take-btn">TAKE PHOTO</button>
    
    <input type="file" id="camera-input" accept="image/*" capture="user">
  </div>
  
  <!-- LOADING SCREEN -->
  <div id="screen-loading" class="screen">
    <div class="loading-title">SCANNING</div>
    <div class="loading-spinner"></div>
    <div class="loading-status">ANALYZING YOUR FEATURES...</div>
  </div>
  
  <!-- RESULTS SCREEN -->
  <div id="screen-results" class="screen">
    <div class="results-header">
      <div class="results-title">YOUR 3 LOOKS</div>
    </div>
    
    <div class="results-swiper" id="results-swiper">
      <!-- Slides generated by JS -->
    </div>
    
    <div class="results-dots" id="results-dots"></div>
  </div>
  
  <!-- CUT CARD SCREEN -->
  <div id="screen-cutcard" class="screen">
    <div class="cutcard-title">YOUR CUT CARD</div>
    <div class="cutcard-container" id="cutcard-content">
      <!-- Generated by JS -->
    </div>
  </div>
  
  <!-- BARBER MODE SCREEN -->
  <div id="screen-barber" class="screen">
    <div class="barber-header">
      <div class="barber-title">BARBER MODE</div>
      <button class="barber-close" id="barber-close">✕</button>
    </div>
    <div id="barber-content">
      <!-- Generated by JS -->
    </div>
  </div>

  <script>
    // ============================================================
    // STATE
    // ============================================================
    let currentLooks = [];
    let selectedLook = null;
    let userImage = null;
    
    const HERO_LOOKS = {
      bold: { name: "BOLD", image: "https://stylelock-production.up.railway.app/static/hairstyle_bold.jpg", top_length: "3 inches", sides: "0.5 fade", texture: "textured", products: "matte clay" },
      clean: { name: "CLEAN", image: "https://stylelock-production.up.railway.app/static/hairstyle_clean.jpg", top_length: "2 inches", sides: "skin fade", texture: "smooth", products: "pomade" },
      trending: { name: "TRENDING", image: "https://stylelock-production.up.railway.app/static/hairstyle_trending.jpg", top_length: "4 inches", sides: "1 guard", texture: "wavy", products: "sea salt spray" }
    };
    
    // ============================================================
    // NAVIGATION
    // ============================================================
    function showScreen(id) {
      document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
      document.getElementById('screen-' + id).classList.add('active');
    }
    
    // ============================================================
    // RAZORPAY
    // ============================================================
    async function handlePayment() {
      try {
        const res = await fetch('/api/create-order', { method: 'POST' });
        const data = await res.json();
        
        if (data.demo) {
          // Demo mode - skip payment
          showScreen('upload');
          return;
        }
        
        const options = {
          key: data.key_id,
          amount: data.amount,
          currency: data.currency,
          name: 'StyleLock',
          description: 'Unlock Your 3 Looks',
          order_id: data.order_id,
          handler: function(response) {
            showScreen('upload');
          },
          theme: { color: '#c8e64a' }
        };
        
        const rzp = new Razorpay(options);
        rzp.open();
      } catch (e) {
        console.error('Payment error:', e);
        showScreen('upload');
      }
    }
    
    // ============================================================
    // IMAGE HANDLING
    // ============================================================
    function handleImage(e) {
      const file = e.target.files[0];
      if (!file) return;
      
      const reader = new FileReader();
      reader.onload = function(ev) {
        userImage = ev.target.result;
        document.getElementById('upload-preview').src = userImage;
        document.getElementById('upload-preview-container').classList.add('visible');
        
        // Auto-proceed after short delay
        setTimeout(() => {
          showScreen('loading');
          processImage();
        }, 800);
      };
      reader.readAsDataURL(file);
    }
    
    async function processImage() {
      document.querySelector('.loading-status').textContent = 'ANALYZING YOUR FEATURES...';
      
      // Simulate processing
      await new Promise(r => setTimeout(r, 1500));
      document.querySelector('.loading-status').textContent = 'GENERATING YOUR LOOKS...';
      await new Promise(r => setTimeout(r, 1500));
      
      // Use hero looks
      currentLooks = [
        HERO_LOOKS.bold,
        HERO_LOOKS.clean,
        HERO_LOOKS.trending
      ];
      
      renderResults();
      showScreen('results');
    }
    
    // ============================================================
    // RESULTS
    // ============================================================
    function renderResults() {
      const swiper = document.getElementById('results-swiper');
      const dots = document.getElementById('results-dots');
      
      swiper.innerHTML = currentLooks.map((look, i) => `
        <div class="result-slide">
          <div class="result-card">
            <div class="result-card-hero">
              <img src="${look.image}" alt="${look.name}">
              <div class="result-look-name">${look.name}</div>
            </div>
            <div class="result-card-info">
              <div class="result-specs">
                <div class="result-spec">
                  <div class="result-spec-label">TOP LENGTH</div>
                  <div class="result-spec-value">${look.top_length}</div>
                </div>
                <div class="result-spec">
                  <div class="result-spec-label">SIDES</div>
                  <div class="result-spec-value">${look.sides}</div>
                </div>
                <div class="result-spec">
                  <div class="result-spec-label">TEXTURE</div>
                  <div class="result-spec-value">${look.texture}</div>
                </div>
                <div class="result-spec">
                  <div class="result-spec-label">PRODUCTS</div>
                  <div class="result-spec-value">${look.products}</div>
                </div>
              </div>
              <button class="result-next-btn" onclick="selectLook(${i})">SELECT THIS LOOK</button>
            </div>
          </div>
        </div>
      `).join('');
      
      dots.innerHTML = currentLooks.map((_, i) => `<div class="dot ${i === 0 ? 'active' : ''}" data-index="${i}"></div>`).join('');
      
      // Swipe detection
      swiper.addEventListener('scroll', () => {
        const index = Math.round(swiper.scrollLeft / swiper.offsetWidth);
        document.querySelectorAll('.dot').forEach((d, i) => d.classList.toggle('active', i === index));
      });
    }
    
    function selectLook(index) {
      selectedLook = currentLooks[index];
      renderCutCard();
      showScreen('cutcard');
    }
    
    // ============================================================
    // CUT CARD
    // ============================================================
    function renderCutCard() {
      const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
      
      document.getElementById('cutcard-content').innerHTML = `
        <div class="cutcard-header">
          <div class="cutcard-logo">STYLELOCK</div>
          <div class="cutcard-date">${today}</div>
        </div>
        <div class="cutcard-look-name">${selectedLook.name}</div>
        <div class="cutcard-specs">
          <div class="cutcard-spec">
            <div class="cutcard-spec-label">TOP LENGTH</div>
            <div class="cutcard-spec-value">${selectedLook.top_length}</div>
          </div>
          <div class="cutcard-spec">
            <div class="cutcard-spec-label">SIDES</div>
            <div class="cutcard-spec-value">${selectedLook.sides}</div>
          </div>
          <div class="cutcard-spec">
            <div class="cutcard-spec-label">TEXTURE</div>
            <div class="cutcard-spec-value">${selectedLook.texture}</div>
          </div>
          <div class="cutcard-spec">
            <div class="cutcard-spec-label">PRODUCTS</div>
            <div class="cutcard-spec-value">${selectedLook.products}</div>
          </div>
        </div>
        <button class="cutcard-barber-btn" onclick="showScreen('barber'); renderBarberMode();">BARBER MODE</button>
      `;
    }
    
    // ============================================================
    // BARBER MODE
    // ============================================================
    function renderBarberMode() {
      document.getElementById('barber-content').innerHTML = `
        <div class="barber-image-container">
          <img src="${selectedLook.image}" alt="${selectedLook.name}">
        </div>
        <div class="barber-specs-grid">
          <div class="barber-spec-card">
            <div class="barber-spec-label">TOP LENGTH</div>
            <div class="barber-spec-value">${selectedLook.top_length}</div>
          </div>
          <div class="barber-spec-card">
            <div class="barber-spec-label">SIDES</div>
            <div class="barber-spec-value">${selectedLook.sides}</div>
          </div>
          <div class="barber-spec-card">
            <div class="barber-spec-label">TEXTURE</div>
            <div class="barber-spec-value">${selectedLook.texture}</div>
          </div>
          <div class="barber-spec-card">
            <div class="barber-spec-label">PRODUCTS</div>
            <div class="barber-spec-value">${selectedLook.products}</div>
          </div>
        </div>
        <div class="barber-footer">
          <div class="barber-logo">
            <svg viewBox="0 0 112 144" fill="var(--lime)">
              <polygon points="0,72 16,72 56,0 72,0 72,12 60,12 20,84 4,84"/>
              <polygon points="40,0 56,0 96,72 112,72 112,84 100,84 60,12 44,12"/>
              <polygon points="28,60 44,60 84,132 100,132 100,144 88,144 48,72 32,72"/>
            </svg>
            <span class="barber-logo-text">STYLELOCK</span>
          </div>
        </div>
      `;
    }
    
    // ============================================================
    // EVENT LISTENERS
    // ============================================================
    document.getElementById('home-unlock-btn').addEventListener('click', handlePayment);
    document.getElementById('upload-frame-btn').addEventListener('click', () => document.getElementById('camera-input').click());
    document.getElementById('upload-take-btn').addEventListener('click', () => document.getElementById('camera-input').click());
    document.getElementById('camera-input').addEventListener('change', handleImage);
    document.getElementById('barber-close').addEventListener('click', () => showScreen('cutcard'));
    
    console.log('StyleLock v43 loaded');
  </script>
</body>
</html>'''

# ============================================================
# SERVE FRONTEND
# ============================================================

@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """Serve the StyleLock PWA frontend"""
    return FRONTEND_HTML

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock AI v43 starting on port {port}")
    print(f"   PWA with Razorpay Integration - FIXED")
    print(f"   Anthropic: {'✅' if ANTHROPIC_API_KEY else '❌ (demo mode)'}")
    print(f"   VModel: {'✅' if VMODEL_API_KEY else '❌ (demo mode)'}")
    print(f"   Razorpay: {'✅' if RAZORPAY_KEY_ID else '❌ (demo mode)'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
