"""
StyleLock AI - Backend Server v54
=================================
FIXES from V51:
- Correct VMODEL API endpoint (task-based async)
- Full 16 Hero Looks database with reference URLs
- Claude analysis for face/hair matching
- Parallel remove.bg + Claude analysis
- Proper scoring engine to pick best 3 looks

Based on working prototype v4.5
"""

import os
import json
import re
import base64
import asyncio
import time
import secrets
import hmac
import hashlib
import sys
from typing import Optional, Tuple, Dict
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
VMODEL_API_KEY = os.getenv("VMODEL_API_KEY", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
FREEIMAGE_API_KEY = os.getenv("FREEIMAGE_API_KEY", "6d207e02198a847aa98d0a2a901485a5")
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "true").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "v54.4")
PAYMENT_TOKEN_TTL_SECONDS = int(os.getenv("PAYMENT_TOKEN_TTL_SECONDS", "900"))

# MVP payment auth store. Replace with Redis/database when multi-instance persistence is needed.
PAYMENT_TOKENS: Dict[str, dict] = {}

# VMODEL API - CORRECT endpoints (task-based async)
VMODEL_API_URL = "https://api.vmodel.ai/api/tasks/v1/create"
VMODEL_TASK_URL = "https://api.vmodel.ai/api/tasks/v1/get"
VMODEL_HAIRSTYLE_VERSION = "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e"

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# =============================================================================
# 16 HERO LOOKS DATABASE (with hosted reference images)
# =============================================================================

HAIRSTYLE_REFERENCES = {
    "bleached_color_crop": {"name": "Bleached / Color Crop", "tier": "BOLD", "source": "https://iili.io/qRqYenV.png"},
    "burst_fade": {"name": "The Burst Fade", "tier": "TRENDING", "source": "https://iili.io/qRqafK7.png"},
    "buzz_lineup": {"name": "Buzz Cut + Sharp Line-up", "tier": "BOLD", "source": "https://iili.io/qRqaORs.png"},
    "classic_scissor_taper": {"name": "Classic Scissor Taper", "tier": "CLEAN", "source": "https://iili.io/qRqcd5g.png"},
    "curls_waves_shaping": {"name": "Curls / Waves Shaping", "tier": "TRENDING", "source": "https://iili.io/qRqc7Ll.png"},
    "disconnected_undercut": {"name": "Disconnected Undercut", "tier": "BOLD", "source": "https://iili.io/qRqcpjf.png"},
    "executive_contour": {"name": "Executive Contour", "tier": "CLEAN", "source": "https://iili.io/qRqlbcP.png"},
    "low_fade_side_part": {"name": "Low Fade + Side Part", "tier": "CLEAN", "source": "https://iili.io/qRq0O5F.png"},
    "messy_flow_layered": {"name": "Messy Flow / Layered", "tier": "TRENDING", "source": "https://iili.io/qRq1aBR.png"},
    "modern_shag_soft_mullet": {"name": "Modern Shag / Soft Mullet", "tier": "TRENDING", "source": "https://iili.io/qRqEzG4.png"},
    "natural_wave_tidy": {"name": "Natural Wave Tidy", "tier": "CLEAN", "source": "https://iili.io/qRqEh91.png"},
    "neat_short_crop": {"name": "Neat Short Crop", "tier": "CLEAN", "source": "https://iili.io/qRqG2ob.png"},
    "quiff_skin_fade": {"name": "Modern Quiff + Skin Fade", "tier": "BOLD", "source": "https://iili.io/qRqGNJS.png"},
    "taper_textured_top": {"name": "Low/Mid Taper + Textured Top", "tier": "TRENDING", "source": "https://iili.io/qRqMz22.png"},
    "textured_french_crop": {"name": "Textured French Crop", "tier": "TRENDING", "source": "https://iili.io/qRqMvYN.png"},
    "two_block_cut": {"name": "The Two-Block Cut", "tier": "TRENDING", "source": "https://iili.io/qRqV33Q.png"},
}

HERO_LOOKS = [
    {
        "id": "classic_scissor_taper",
        "name": "Classic Scissor Taper",
        "tier": "CLEAN",
        "vibe": "Corporate Polish",
        "maintenance": "Low",
        "daily_time": "2-3 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 4, "heart": 4, "diamond": 3},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 4, "fine": 4, "thick": 5},
        "min_length_cm": 3,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "No fade - scissor graduated taper",
            "top_length": "5-7 cm",
            "texture": "Point cutting for natural texture",
            "fringe": "Side-swept, above eyebrows",
            "styling": "Blow dry with round brush, light pomade finish",
            "products": "Matte pomade, sea salt spray"
        }
    },
    {
        "id": "low_fade_side_part",
        "name": "Low Fade + Side Part",
        "tier": "CLEAN",
        "vibe": "Timeless Class",
        "maintenance": "Medium",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 5, "oblong": 4, "heart": 4, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 3, "fine": 5, "thick": 4},
        "min_length_cm": 5,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Low skin fade, guard 0.5 to 2",
            "top_length": "7-10 cm",
            "texture": "Scissor cut with clean lines",
            "fringe": "Hard side part, swept back",
            "styling": "Comb while damp, high-hold pomade",
            "products": "Classic pomade, finishing spray"
        }
    },
    {
        "id": "executive_contour",
        "name": "Executive Contour",
        "tier": "CLEAN",
        "vibe": "Traditional Grooming",
        "maintenance": "High",
        "daily_time": "5-7 min",
        "face_shapes": {"oval": 5, "round": 5, "square": 4, "oblong": 3, "heart": 4, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 2, "coarse": 3, "fine": 5, "thick": 4},
        "min_length_cm": 6,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "No fade - scissor tapered",
            "top_length": "6-9 cm",
            "texture": "Layered for volume control",
            "fringe": "Side-swept with slight lift",
            "styling": "Blow dry with volume, pomade finish",
            "products": "Volumizing mousse, medium-hold pomade"
        }
    },
    {
        "id": "natural_wave_tidy",
        "name": "Natural Wave Tidy",
        "tier": "CLEAN",
        "vibe": "Relaxed Professional",
        "maintenance": "Low",
        "daily_time": "2-3 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 5, "heart": 4, "diamond": 4},
        "textures": {"straight": 3, "wavy": 5, "curly": 4, "coarse": 4, "fine": 4, "thick": 4},
        "min_length_cm": 4,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Low taper, no skin",
            "top_length": "5-8 cm",
            "texture": "Light texturizing to enhance natural wave",
            "fringe": "Natural fall, soft shape",
            "styling": "Air dry or light diffuse, sea salt spray",
            "products": "Sea salt spray, light cream"
        }
    },
    {
        "id": "neat_short_crop",
        "name": "Neat Short Crop",
        "tier": "CLEAN",
        "vibe": "Clean Minimal",
        "maintenance": "Low",
        "daily_time": "1-2 min",
        "face_shapes": {"oval": 4, "round": 5, "square": 5, "oblong": 3, "heart": 4, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 4, "coarse": 5, "fine": 4, "thick": 5},
        "min_length_cm": 2,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Mid taper, guard 1 to 3",
            "top_length": "2-4 cm",
            "texture": "Clipper blend with scissors on top",
            "fringe": "Short, textured forward",
            "styling": "Towel dry, light clay",
            "products": "Matte clay or paste"
        }
    },
    {
        "id": "taper_textured_top",
        "name": "Low/Mid Taper + Textured Top",
        "tier": "TRENDING",
        "vibe": "Everyday Sharp",
        "maintenance": "Medium",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 4, "heart": 4, "diamond": 4},
        "textures": {"straight": 4, "wavy": 5, "curly": 4, "coarse": 5, "fine": 3, "thick": 5},
        "min_length_cm": 4,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Low-mid taper, guard 1 to 3",
            "top_length": "5-8 cm",
            "texture": "Choppy point cutting, texturizing shears",
            "fringe": "Textured, swept to side or forward",
            "styling": "Blow dry for volume, matte clay finish",
            "products": "Texture powder, matte clay"
        }
    },
    {
        "id": "textured_french_crop",
        "name": "Textured French Crop",
        "tier": "TRENDING",
        "vibe": "Effortless Cool",
        "maintenance": "Low",
        "daily_time": "2-3 min",
        "face_shapes": {"oval": 5, "round": 5, "square": 4, "oblong": 3, "heart": 4, "diamond": 4},
        "textures": {"straight": 4, "wavy": 5, "curly": 4, "coarse": 5, "fine": 3, "thick": 5},
        "min_length_cm": 2,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Mid-high fade, guard 0.5 to 2",
            "top_length": "3-5 cm",
            "texture": "Choppy, piecey texture throughout",
            "fringe": "Forward falling, textured, on forehead",
            "styling": "Towel dry, work in clay, done",
            "products": "Matte clay, texture powder"
        }
    },
    {
        "id": "messy_flow_layered",
        "name": "Messy Flow / Layered",
        "tier": "TRENDING",
        "vibe": "Actor Aesthetic",
        "maintenance": "High",
        "daily_time": "5-8 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 3, "wavy": 5, "curly": 4, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 10,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "No fade - grown out sides",
            "top_length": "10-15 cm",
            "texture": "Heavy layers throughout",
            "fringe": "Curtain bangs or side-swept",
            "styling": "Air dry or diffuse, texturizing spray",
            "products": "Texturizing spray, light cream"
        }
    },
    {
        "id": "burst_fade",
        "name": "The Burst Fade",
        "tier": "TRENDING",
        "vibe": "Athletic Edge",
        "maintenance": "Medium",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 4, "round": 5, "square": 5, "oblong": 3, "heart": 4, "diamond": 4},
        "textures": {"straight": 4, "wavy": 5, "curly": 5, "coarse": 5, "fine": 3, "thick": 5},
        "min_length_cm": 3,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Burst fade around ear, skin to 2",
            "top_length": "4-7 cm",
            "texture": "Textured, curly or wavy enhanced",
            "fringe": "Forward or up, depends on texture",
            "styling": "Curl cream or matte paste",
            "products": "Curl enhancer, matte paste"
        }
    },
    {
        "id": "curls_waves_shaping",
        "name": "Curls / Waves Shaping",
        "tier": "TRENDING",
        "vibe": "Natural Enhancement",
        "maintenance": "Low",
        "daily_time": "2-4 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 4, "heart": 5, "diamond": 4},
        "textures": {"straight": 1, "wavy": 4, "curly": 5, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 4,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Low-mid taper, guard 1 to 2",
            "top_length": "5-10 cm (stretched)",
            "texture": "Curl-cutting technique, no thinning",
            "fringe": "Natural curl pattern",
            "styling": "Curl cream on wet hair, air dry",
            "products": "Curl cream, leave-in conditioner"
        }
    },
    {
        "id": "modern_shag_soft_mullet",
        "name": "Modern Shag / Soft Mullet",
        "tier": "TRENDING",
        "vibe": "Retro Revival",
        "maintenance": "Medium",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 5, "heart": 4, "diamond": 5},
        "textures": {"straight": 4, "wavy": 5, "curly": 4, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "No fade - soft graduation",
            "top_length": "8-12 cm",
            "texture": "Heavy layers, razored ends",
            "fringe": "Curtain bangs, cheekbone length",
            "styling": "Air dry, scrunch with texturizer",
            "products": "Texture spray, matte paste"
        }
    },
    {
        "id": "two_block_cut",
        "name": "The Two-Block Cut",
        "tier": "TRENDING",
        "vibe": "K-Pop Influence",
        "maintenance": "High",
        "daily_time": "5-8 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 3, "oblong": 5, "heart": 5, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 2, "coarse": 3, "fine": 5, "thick": 4},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Disconnected - clipper sides, no blend",
            "top_length": "10-15 cm",
            "texture": "Layered for movement",
            "fringe": "Curtain or side-swept, eye-level",
            "styling": "Blow dry for volume and shape",
            "products": "Volumizing spray, light wax"
        }
    },
    {
        "id": "quiff_skin_fade",
        "name": "Modern Quiff + Skin Fade",
        "tier": "BOLD",
        "vibe": "Statement Maker",
        "maintenance": "High",
        "daily_time": "7-10 min",
        "face_shapes": {"oval": 5, "round": 5, "square": 4, "oblong": 3, "heart": 4, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 4, "fine": 4, "thick": 5},
        "min_length_cm": 7,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "High skin fade, guard 0 to 2",
            "top_length": "8-12 cm",
            "texture": "Layered for lift, texturized ends",
            "fringe": "Swept up and back in quiff shape",
            "styling": "Blow dry up and back, strong hold",
            "products": "Volume powder, strong pomade"
        }
    },
    {
        "id": "disconnected_undercut",
        "name": "Disconnected Undercut",
        "tier": "BOLD",
        "vibe": "Edgy Professional",
        "maintenance": "High",
        "daily_time": "5-8 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 4, "fine": 4, "thick": 5},
        "min_length_cm": 6,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Disconnected - guard 0.5-1, no blend",
            "top_length": "10-15 cm",
            "texture": "Point cutting for movement",
            "fringe": "Slicked back or side-swept",
            "styling": "Blow dry back, high-shine pomade",
            "products": "Strong pomade, finishing spray"
        }
    },
    {
        "id": "buzz_lineup",
        "name": "Buzz Cut + Sharp Line-up",
        "tier": "BOLD",
        "vibe": "Confident Minimalist",
        "maintenance": "Low",
        "daily_time": "1 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 3, "heart": 4, "diamond": 5},
        "textures": {"straight": 5, "wavy": 5, "curly": 5, "coarse": 5, "fine": 5, "thick": 5},
        "min_length_cm": 0,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Even buzz (guard 1-2) or skin fade",
            "top_length": "3-6 mm",
            "texture": "Clipper all over",
            "fringe": "Sharp line-up at hairline",
            "styling": "None needed",
            "products": "Scalp moisturizer"
        }
    },
    {
        "id": "bleached_color_crop",
        "name": "Bleached / Color Crop",
        "tier": "BOLD",
        "vibe": "Fashion Forward",
        "maintenance": "High",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 4, "wavy": 5, "curly": 4, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 2,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Mid-high fade, guard 0.5 to 2",
            "top_length": "3-6 cm",
            "texture": "Textured crop base, then color",
            "fringe": "Textured, forward falling",
            "styling": "Towel dry, clay for texture",
            "products": "Purple shampoo, matte clay"
        }
    },
]

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(title="StyleLock AI", version="54")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def cleanup_payment_tokens():
    """Drop expired in-memory payment tokens. Replace with Redis TTL for production scale."""
    now = time.time()
    expired = [token for token, meta in PAYMENT_TOKENS.items() if meta.get("expires_at", 0) <= now]
    for token in expired:
        PAYMENT_TOKENS.pop(token, None)


def create_payment_token(order_id: str, payment_id: str) -> tuple[str, int]:
    cleanup_payment_tokens()
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time() + PAYMENT_TOKEN_TTL_SECONDS)
    PAYMENT_TOKENS[token] = {
        "order_id": order_id,
        "payment_id": payment_id,
        "expires_at": expires_at,
        "used": False,
    }
    return token, PAYMENT_TOKEN_TTL_SECONDS


def consume_payment_token(token: str) -> tuple[bool, str]:
    """Validate and consume a one-time payment token before expensive generation starts."""
    cleanup_payment_tokens()
    token_data = PAYMENT_TOKENS.get(token)
    if not token_data:
        return False, "Payment token is missing or invalid"
    if token_data.get("used"):
        return False, "Payment token has already been used"
    if token_data.get("expires_at", 0) <= time.time():
        PAYMENT_TOKENS.pop(token, None)
        return False, "Payment token has expired"

    token_data["used"] = True
    return True, ""


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not RAZORPAY_KEY_SECRET:
        return False
    payload = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def clean_env_value(value: str) -> str:
    return (value or "").strip()


def mask_key_prefix(value: str) -> str:
    cleaned = clean_env_value(value)
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return f"{cleaned[:3]}***"
    return f"{cleaned[:8]}***"

# =============================================================================
# HELPER FUNCTIONS - Image Upload
# =============================================================================

async def upload_image_to_host(image_base64: str) -> str:
    """Upload image to freeimage.host and return URL"""
    print("  📤 Uploading image to host...")
    
    # Strip data URL prefix if present
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": FREEIMAGE_API_KEY,
                    "action": "upload",
                    "source": image_base64,
                    "format": "json"
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status_code") == 200:
                    url = data["image"]["url"]
                    print(f"  ✅ Uploaded: {url[:50]}...")
                    return url
        except Exception as e:
            print(f"  ⚠️ Upload failed: {e}")
    raise Exception("Failed to upload image")

# =============================================================================
# HELPER FUNCTIONS - Remove.bg
# =============================================================================

async def remove_background(image_base64: str) -> Optional[str]:
    """Remove background using remove.bg API"""
    if not REMOVEBG_API_KEY:
        print("  ⚠️ REMOVEBG_API_KEY not set, skipping")
        return None
    
    print("  🎨 Removing background...")
    
    # Strip data URL prefix if present
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://api.remove.bg/v1.0/removebg",
                headers={"X-Api-Key": REMOVEBG_API_KEY},
                data={
                    "image_file_b64": image_base64,
                    "size": "auto",
                    "format": "png",
                    "bg_color": "1a2f2a"  # Match app theme green
                }
            )
            if resp.status_code == 200:
                clean_b64 = base64.b64encode(resp.content).decode('utf-8')
                print("  ✅ Background removed!")
                return clean_b64
            else:
                print(f"  ⚠️ Remove.bg error: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  ⚠️ Background removal failed: {e}")
            return None

# =============================================================================
# HELPER FUNCTIONS - Claude Analysis
# =============================================================================

async def analyze_with_claude(image_base64: str) -> dict:
    """Analyze face and hair using Claude Vision"""
    print("  🧠 Analyzing with Claude Vision...")
    
    if not ANTHROPIC_API_KEY:
        print("  ⚠️ No Anthropic key, using defaults")
        return {
            "face_shape": "oval",
            "hair_texture": "wavy",
            "hair_density": "medium",
            "estimated_top_length_cm": 5,
            "hairline_state": "full"
        }
    
    # Strip data URL prefix if present
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]
    
    prompt = """Analyze this person's face and hair for hairstyle recommendations. Return ONLY valid JSON:
{
    "face_shape": "oval|round|square|oblong|heart|diamond",
    "hair_texture": "straight|wavy|curly|coarse|fine|thick",
    "hair_density": "thick|medium|thin",
    "estimated_top_length_cm": <number>,
    "hairline_state": "full|slightly_receding|receding|thinning_crown"
}
Be accurate. Estimate hair length in centimeters carefully."""

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 500,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
                            {"type": "text", "text": prompt}
                        ]
                    }]
                }
            )
            if resp.status_code != 200:
                raise Exception(f"Claude API error: {resp.status_code}")
            
            data = resp.json()
            text = data["content"][0]["text"]
            
            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            analysis = json.loads(text.strip())
            print(f"  ✅ Analysis: {analysis.get('face_shape')} face, {analysis.get('hair_texture')} hair")
            return analysis
            
        except Exception as e:
            print(f"  ⚠️ Claude analysis failed: {e}")
            return {
                "face_shape": "oval",
                "hair_texture": "wavy",
                "hair_density": "medium",
                "estimated_top_length_cm": 5,
                "hairline_state": "full"
            }

# =============================================================================
# HELPER FUNCTIONS - Scoring & Recommendations
# =============================================================================

def score_and_recommend(analysis: dict, vibe: str = "balanced") -> list:
    """Score all looks and pick best 3 (one per tier)"""
    print("  📊 Scoring looks...")
    
    face = analysis.get("face_shape", "oval").lower()
    texture = analysis.get("hair_texture", "wavy").lower()
    length_cm = analysis.get("estimated_top_length_cm", 5)
    hairline = analysis.get("hairline_state", "full").lower()
    
    scored = []
    for look in HERO_LOOKS:
        # Face shape score (0-40)
        face_score = look["face_shapes"].get(face, 3) * 8
        
        # Texture score (0-35)
        texture_score = look["textures"].get(texture, 3) * 7
        
        # Thinning bonus
        thinning_bonus = 10 if ("thinning" in hairline or "receding" in hairline) and look["thinning_friendly"] else 0
        
        # Vibe preference
        vibe_score = 15 if (
            (vibe == "safe" and look["tier"] == "CLEAN") or
            (vibe == "bold" and look["tier"] == "BOLD") or
            (vibe == "balanced" and look["tier"] == "TRENDING")
        ) else 10
        
        raw = face_score + texture_score + thinning_bonus + vibe_score
        pct = max(70, min(95, int(70 + (raw - 50) * 25 / 50)))
        
        # Achievability
        min_len = look["min_length_cm"]
        if length_cm >= min_len:
            ach, weeks = "ready", 0
        else:
            weeks = int((min_len - length_cm) / 0.3)
            ach = "grow" if weeks <= 12 else "dream"
        
        ref = HAIRSTYLE_REFERENCES.get(look["id"], {})
        scored.append({
            **look,
            "total_score": raw,
            "match_percentage": pct,
            "achievability": ach,
            "growth_weeks": weeks,
            "reference_url": ref.get("source", "")
        })
    
    # Sort by score
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    
    # Pick one from each tier
    result, tiers = [], set()
    for tier in ["TRENDING", "CLEAN", "BOLD"]:
        for look in scored:
            if look["tier"] == tier and tier not in tiers:
                tiers.add(tier)
                result.append(look)
                break
    
    # Fill to 3 if needed
    while len(result) < 3:
        for look in scored:
            if look not in result:
                result.append(look)
                break
    
    print(f"  ✅ Top 3: {[l['name'] for l in result[:3]]}")
    return result[:3]

# =============================================================================
# HELPER FUNCTIONS - VMODEL Generation (CORRECT API)
# =============================================================================

async def generate_hairstyle_vmodel(target_url: str, look: dict) -> Optional[str]:
    """Generate hairstyle using VMODEL async task API"""
    name = look.get("name", "Unknown")
    source = look.get("reference_url", "")
    
    if not source:
        print(f"    [{name}] ❌ No reference URL")
        return None
    
    if not VMODEL_API_KEY:
        print(f"    [{name}] ❌ No VMODEL key")
        return None
    
    print(f"    [{name}] Calling VModel...")
    
    headers = {
        "Authorization": f"Bearer {VMODEL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "version": VMODEL_HAIRSTYLE_VERSION,
        "input": {
            "source": source,      # Hairstyle reference image
            "target": target_url,  # User's selfie
            "disable_safety_checker": False
        }
    }
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            # Create task
            resp = await client.post(VMODEL_API_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                print(f"    [{name}] ❌ Create failed: {resp.status_code}")
                return None
            
            data = resp.json()
            
            # Check if immediately succeeded
            if data.get("status") == "succeeded" and data.get("output"):
                output = data["output"]
                url = output[0] if isinstance(output, list) else output
                print(f"    [{name}] ✅ Done (immediate)!")
                return url
            
            # Get task ID for polling
            task_id = (
                data.get("result", {}).get("task_id") or
                data.get("task_id") or
                data.get("id")
            )
            
            if not task_id:
                print(f"    [{name}] ❌ No task ID")
                return None
            
            # Poll for completion (up to 2 minutes)
            for _ in range(40):
                await asyncio.sleep(3)
                
                poll = await client.get(f"{VMODEL_TASK_URL}/{task_id}", headers=headers)
                if poll.status_code != 200:
                    continue
                
                pdata = poll.json()
                rd = pdata.get("result", pdata)
                status = rd.get("status") or pdata.get("status", "")
                
                if status in ["succeeded", "completed", "success", "done"]:
                    out = (
                        rd.get("output") or
                        rd.get("output_url") or
                        rd.get("image_url") or
                        pdata.get("output")
                    )
                    if out:
                        url = out[0] if isinstance(out, list) else out
                        print(f"    [{name}] ✅ Done!")
                        return url
                    return None
                
                if status in ["failed", "error", "cancelled"]:
                    print(f"    [{name}] ❌ Task failed: {status}")
                    return None
            
            print(f"    [{name}] ⚠️ Timeout")
            return None
            
        except Exception as e:
            print(f"    [{name}] ❌ Exception: {e}")
            return None

async def generate_all_previews(target_url: str, looks: list) -> list:
    """Generate all previews in parallel"""
    print("  🎨 Generating 3 previews (parallel)...")
    
    tasks = [generate_hairstyle_vmodel(target_url, l) for l in looks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, (look, res) in enumerate(zip(looks, results)):
        if res and not isinstance(res, Exception):
            looks[i]["preview_url"] = res
        else:
            looks[i]["preview_url"] = None
    
    success_count = sum(1 for r in results if r and not isinstance(r, Exception))
    print(f"  ✅ Generated {success_count}/3")
    
    return looks

# =============================================================================
# PARALLEL PREPROCESSING
# =============================================================================

async def parallel_preprocess(image_base64: str) -> Tuple[dict, str]:
    """Run Claude analysis and BG removal in parallel"""
    print("\n🔄 Starting parallel preprocessing...")
    start = time.time()
    
    # Strip data URL prefix for API calls
    clean_b64 = image_base64
    if "base64," in clean_b64:
        clean_b64 = clean_b64.split("base64,")[1]
    
    # Run in parallel
    tasks = [
        analyze_with_claude(clean_b64),
        remove_background(clean_b64) if ENABLE_BG_REMOVAL else asyncio.sleep(0),
        upload_image_to_host(clean_b64),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Extract results
    analysis = results[0] if not isinstance(results[0], Exception) else {
        "face_shape": "oval",
        "hair_texture": "wavy",
        "hair_density": "medium",
        "estimated_top_length_cm": 5,
        "hairline_state": "full"
    }
    
    clean_image_b64 = results[1] if (ENABLE_BG_REMOVAL and not isinstance(results[1], Exception) and results[1]) else None
    original_url = results[2] if not isinstance(results[2], Exception) else None
    
    # If we got a clean image, upload it
    target_url = original_url
    if clean_image_b64:
        try:
            target_url = await upload_image_to_host(clean_image_b64)
            print(f"  ✅ Clean image uploaded")
        except:
            pass
    
    elapsed = time.time() - start
    print(f"✅ Preprocessing done in {elapsed:.1f}s")
    
    return analysis, target_url

# =============================================================================
# API ROUTES
# =============================================================================

# Matches Instagram and Facebook in-app webviews. Kept at module scope so it
# compiles once and stays in sync with the UA detection used in landing.html.
IN_APP_BROWSER_UA_RE = re.compile(r"Instagram|FBAN|FBAV|FB_IAB", re.IGNORECASE)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    """Root entrypoint.

    - Instagram / Facebook in-app webviews get a lightweight bridge page
      (landing.html) that's safe to render inside those chokes-prone webviews
      and explicitly prompts users to "Open in browser".
    - All other user agents (Safari, Chrome, etc.) are redirected straight to
      /app for the fastest possible path into the PWA.

    Razorpay, /app, and every /api/* route are untouched.
    """
    ua = request.headers.get("user-agent", "")
    if IN_APP_BROWSER_UA_RE.search(ua):
        response = templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"app_version": APP_VERSION},
        )
        # Short cache so repeat ad clicks inside IG/FB stay snappy, but we can
        # still ship quick updates during launch week.
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    # Normal browsers: skip the bridge and go straight to the real app.
    return RedirectResponse(url="/app", status_code=307)


@app.get("/apple-app-site-association", include_in_schema=False)
@app.get("/.well-known/apple-app-site-association", include_in_schema=False)
async def apple_app_site_association_probe():
    """Return no-content for Apple Universal Links probes; this app does not publish a native association file."""
    return Response(status_code=204)


@app.get("/api/health", response_class=JSONResponse)
async def health_check():
    """Health check"""
    return {
        "app": "StyleLock AI",
        "version": "54",
        "status": "running",
        "apis": {
            "anthropic": "configured" if ANTHROPIC_API_KEY else "not configured",
            "vmodel": "configured" if VMODEL_API_KEY else "not configured",
            "razorpay": "configured" if RAZORPAY_KEY_ID else "demo mode",
            "removebg": "configured" if REMOVEBG_API_KEY else "not configured",
            "bg_removal_enabled": ENABLE_BG_REMOVAL
        },
        "hero_looks_count": len(HERO_LOOKS)
    }

@app.get("/api/debug")
async def debug():
    """Debug endpoint to test API connections"""
    results = {"tests": {}, "config": {"bg_removal": ENABLE_BG_REMOVAL}}
    
    # Test Anthropic
    if ANTHROPIC_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": CLAUDE_MODEL, "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}
                )
                results["tests"]["anthropic"] = "✅" if r.status_code == 200 else f"❌ {r.status_code}"
        except Exception as e:
            results["tests"]["anthropic"] = f"❌ {e}"
    else:
        results["tests"]["anthropic"] = "⚠️ Key not set"
    
    # Test VModel
    if VMODEL_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.vmodel.ai/api/user/v1/me", headers={"Authorization": f"Bearer {VMODEL_API_KEY}"})
                results["tests"]["vmodel"] = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
        except Exception as e:
            results["tests"]["vmodel"] = f"❌ {e}"
    else:
        results["tests"]["vmodel"] = "⚠️ Key not set"
    
    # Test Remove.bg
    if REMOVEBG_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.remove.bg/v1.0/account", headers={"X-Api-Key": REMOVEBG_API_KEY})
                if r.status_code == 200:
                    data = r.json()
                    credits = data.get("data", {}).get("attributes", {}).get("credits", {}).get("total", 0)
                    results["tests"]["removebg"] = f"✅ ({credits} credits)"
                else:
                    results["tests"]["removebg"] = f"⚠️ {r.status_code}"
        except Exception as e:
            results["tests"]["removebg"] = f"❌ {e}"
    else:
        results["tests"]["removebg"] = "⚠️ Key not set"
    
    return results

@app.get("/app", response_class=HTMLResponse)
async def serve_app(request: Request):
    """Serve main app"""
    response = templates.TemplateResponse(
        request=request,
        name="app.html",
        context={"app_version": APP_VERSION}
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.post("/api/create-order")
async def create_razorpay_order():
    """Create Razorpay order"""
    key_id = clean_env_value(RAZORPAY_KEY_ID)
    key_secret = clean_env_value(RAZORPAY_KEY_SECRET)

    print("[payment-debug] /api/create-order called")
    print(f"[payment-debug] has_key_id={bool(key_id)}")
    print(f"[payment-debug] has_key_secret={bool(key_secret)}")
    print(f"[payment-debug] key_prefix={mask_key_prefix(key_id)}")

    if not key_id or not key_secret:
        return JSONResponse(
            {
                "success": False,
                "error": "Razorpay keys are not configured",
                "debug_code": "MISSING_RAZORPAY_KEYS",
            },
            status_code=500,
        )

    try:
        import razorpay
        print("[payment-debug] razorpay import ok=True")
    except Exception as import_error:
        print("[payment-debug] razorpay import ok=False")
        print(f"[payment-debug] import_error_class={import_error.__class__.__name__}")
        print(f"[payment-debug] import_error_message={import_error}")
        return JSONResponse(
            {
                "success": False,
                "error": "Razorpay package is unavailable",
                "debug_code": "RAZORPAY_IMPORT_ERROR",
            },
            status_code=500,
        )

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        order = client.order.create(
            {
                "amount": 7900,
                "currency": "INR",
                "payment_capture": 1,
                "notes": {"product": "StyleLock", "flow": "mvp_consultation"},
            }
        )
        return {
            "success": True,
            "order_id": order["id"],
            "amount": 7900,
            "currency": "INR",
            "key_id": key_id,
        }
    except Exception as e:
        message = str(e)
        lowered = message.lower()
        status_code = getattr(e, "status_code", None)
        debug_code = "RAZORPAY_ORDER_CREATE_FAILED"
        response_status = 502

        if status_code in (400, 401, 403) or "auth" in lowered or "key" in lowered or "signature" in lowered:
            debug_code = "RAZORPAY_AUTH_FAILED"
            response_status = 502

        print("[payment-debug] razorpay order create failed")
        print(f"[payment-debug] exception_class={e.__class__.__name__}")
        print(f"[payment-debug] exception_message={message}")
        print(f"[payment-debug] mapped_debug_code={debug_code}")

        return JSONResponse(
            {
                "success": False,
                "error": "Unable to create payment order",
                "debug_code": debug_code,
            },
            status_code=response_status,
        )


@app.post("/api/verify-payment")
async def verify_payment(request: Request):
    """Verify Razorpay signature and issue a short-lived generation token."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid request body"}, status_code=400)

    order_id = str(data.get("razorpay_order_id", "")).strip()
    payment_id = str(data.get("razorpay_payment_id", "")).strip()
    signature = str(data.get("razorpay_signature", "")).strip()

    if not order_id or not payment_id or not signature:
        return JSONResponse(
            {"success": False, "error": "Missing payment verification fields"},
            status_code=400,
        )

    if not verify_razorpay_signature(order_id, payment_id, signature):
        return JSONResponse(
            {"success": False, "error": "Payment verification failed"},
            status_code=400,
        )

    payment_token, expires_in = create_payment_token(order_id, payment_id)
    return {
        "success": True,
        "payment_token": payment_token,
        "expires_in": expires_in,
    }


@app.get("/api/debug/payment")
async def debug_payment():
    """Temporary payment diagnostics endpoint. Remove before launch."""
    key_id = clean_env_value(RAZORPAY_KEY_ID)
    key_secret = clean_env_value(RAZORPAY_KEY_SECRET)

    try:
        import razorpay  # noqa: F401
        razorpay_import_ok = True
    except Exception:
        razorpay_import_ok = False

    return {
        "success": True,
        "has_key_id": bool(key_id),
        "has_key_secret": bool(key_secret),
        "key_prefix": mask_key_prefix(key_id),
        "python_runtime": sys.version,
        "razorpay_import_ok": razorpay_import_ok,
    }

@app.post("/api/generate-looks")
async def generate_looks(request: Request):
    """Main endpoint - generate 3 hairstyle looks"""
    print("\n" + "="*60)
    print("NEW CONSULTATION (v54)")
    print("="*60)
    
    start_time = time.time()
    
    try:
        data = await request.json()
        image_base64 = data.get("image", "")
        payment_token = str(data.get("payment_token", "")).strip()

        valid_token, token_error = consume_payment_token(payment_token)
        if not valid_token:
            return JSONResponse({"error": token_error, "success": False}, status_code=403)
        
        if not image_base64:
            return JSONResponse({"error": "No image provided", "success": False}, status_code=400)
        
        # Step 1+2: Parallel preprocessing (Claude + BG removal + upload)
        analysis, target_url = await parallel_preprocess(image_base64)
        
        if not target_url:
            return JSONResponse({"error": "Failed to process image", "success": False}, status_code=500)
        
        # Step 3: Score and recommend
        recs = score_and_recommend(analysis)
        
        # Step 4: Generate previews with VModel
        recs = await generate_all_previews(target_url, recs)
        
        elapsed = time.time() - start_time
        print(f"\n✅ DONE in {elapsed:.1f}s")
        print("="*60)
        
        # Format response for frontend
        looks = []
        for rec in recs:
            tier = str(rec.get("tier", "")).upper()
            if tier not in {"BOLD", "CLEAN", "TRENDING"}:
                tier = "TRENDING"

            full_name = rec.get("name") or rec.get("id", "Identity Look").replace("_", " ").title()
            looks.append({
                "tier": tier,
                "name": full_name,
                "full_name": full_name,
                "image": rec.get("preview_url") or f"/static/images/hairstyle_{tier.lower()}.jpg",
                "match_percentage": rec.get("match_percentage", 80),
                "achievability": rec.get("achievability", "ready"),
                "vibe": rec.get("vibe", ""),
                "maintenance": rec.get("maintenance", ""),
                "top_length": rec.get("cut_card", {}).get("top_length", ""),
                "sides": rec.get("cut_card", {}).get("fade", ""),
                "texture": rec.get("cut_card", {}).get("texture", ""),
                "products": rec.get("cut_card", {}).get("products", ""),
                "styling": rec.get("cut_card", {}).get("styling", ""),
                "fringe": rec.get("cut_card", {}).get("fringe", "")
            })
        
        return {
            "success": True,
            "looks": looks,
            "analysis": analysis,
            "processing_time": round(elapsed, 1)
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e), "success": False}, status_code=500)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock AI v54 starting on port {port}")
    print(f"   VMODEL API: {VMODEL_API_URL}")
    print(f"   BG Removal: {'ENABLED' if ENABLE_BG_REMOVAL else 'DISABLED'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
