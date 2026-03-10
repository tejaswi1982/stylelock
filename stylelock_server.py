"""
StyleLock AI - Complete Backend Server v3.0
Features:
- Share/Save functionality
- Lock This Look flow
- Cut Card detail view (tap to expand)
- Vibe preference selector (Safe / Balanced / Bold)
- Calibrated match percentages (70-92% realistic range)
- Performance optimizations
"""

import os
import json
import base64
import asyncio
import time
from datetime import datetime
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
VMODEL_API_KEY = os.getenv("VMODEL_API_KEY", "TnFvIrhRQMtRyLmhNNo1OC1ft2gGgRb5ayAtIpt5emC7SZljePfUNu08hDwZbKty8HjtFMWh34g5LoeLUc0jOA==")

VMODEL_API_URL = "https://api.vmodel.ai/api/tasks/v1/create"
VMODEL_TASK_URL = "https://api.vmodel.ai/api/tasks/v1/get"
VMODEL_HAIRSTYLE_VERSION = "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e"

CLAUDE_MODEL = "claude-opus-4-20250514"

# ============================================================
# YOUR 16 HERO LOOKS - WITH REAL IMAGE URLs
# ============================================================

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

# ============================================================
# COMPLETE HERO LOOKS DATABASE WITH CUT CARD SPECS
# ============================================================

HERO_LOOKS = [
    # ===== TIER 1: CLEAN & CORPORATE =====
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
            "texture_method": "Point cutting for natural texture",
            "fringe": "Side-swept, above eyebrows",
            "styling": "Blow dry with round brush, light pomade finish",
            "products": "Matte pomade, sea salt spray",
            "beard_pairing": "Clean shaven or light stubble",
            "avoid": "Heavy product buildup, slicked back looks"
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
            "fade": "Low skin fade, guard 0.5 → 2",
            "top_length": "7-10 cm",
            "texture_method": "Scissor cut with clean lines",
            "fringe": "Hard side part, swept back",
            "styling": "Comb while damp, high-hold pomade",
            "products": "Classic pomade, finishing spray",
            "beard_pairing": "Clean shaven or short boxed beard",
            "avoid": "Messy texture, excessive volume"
        }
    },
    {
        "id": "neat_short_crop",
        "name": "Neat Short Crop",
        "tier": "CLEAN",
        "vibe": "Boardroom Ready",
        "maintenance": "Low",
        "daily_time": "1-2 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 5, "oblong": 4, "heart": 3, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 4, "fine": 5, "thick": 5},
        "min_length_cm": 2,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Tapered sides, guard 2 → 4",
            "top_length": "3-5 cm",
            "texture_method": "Clipper over comb, blended",
            "fringe": "Short, brushed forward or slightly up",
            "styling": "Towel dry, small amount of clay",
            "products": "Matte clay, light hold",
            "beard_pairing": "Any - versatile",
            "avoid": "Over-styling, too much shine"
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
            "texture_method": "Layered for volume control",
            "fringe": "Side-swept with slight lift",
            "styling": "Blow dry with volume, pomade finish",
            "products": "Volumizing mousse, medium-hold pomade",
            "beard_pairing": "Clean shaven preferred",
            "avoid": "Flat styling, heavy products"
        }
    },
    {
        "id": "natural_wave_tidy",
        "name": "Natural Wave Tidy",
        "tier": "CLEAN",
        "vibe": "Effortless Professional",
        "maintenance": "Medium",
        "daily_time": "3-4 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 3, "heart": 5, "diamond": 5},
        "textures": {"straight": 2, "wavy": 5, "curly": 5, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 4,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Low taper, guard 1.5 → 3",
            "top_length": "5-8 cm",
            "texture_method": "Point cutting to enhance waves",
            "fringe": "Natural wave falling on forehead",
            "styling": "Scrunch with curl cream, air dry",
            "products": "Curl cream, light oil",
            "beard_pairing": "Stubble or short beard",
            "avoid": "Brushing when dry, heavy gels"
        }
    },
    
    # ===== TIER 2: FASHION-FORWARD / TRENDING =====
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
            "fade": "Low-mid taper, guard 1 → 3",
            "top_length": "5-8 cm",
            "texture_method": "Choppy point cutting, texturizing shears",
            "fringe": "Textured, swept to side or forward",
            "styling": "Blow dry for volume, matte clay finish",
            "products": "Texture powder, matte clay",
            "beard_pairing": "Stubble or fade into beard",
            "avoid": "Flat, limp styling"
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
            "fade": "Mid-high fade, guard 0.5 → 2",
            "top_length": "3-5 cm",
            "texture_method": "Choppy, piecey texture throughout",
            "fringe": "Forward falling, textured, on forehead",
            "styling": "Towel dry, work in clay, done",
            "products": "Matte clay, texture powder",
            "beard_pairing": "Stubble or short beard",
            "avoid": "Over-styling, heavy product"
        }
    },
    {
        "id": "two_block_cut",
        "name": "The Two-Block Cut",
        "tier": "TRENDING",
        "vibe": "K-Pop Influence",
        "maintenance": "Medium",
        "daily_time": "5-7 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 5, "heart": 5, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 2, "coarse": 3, "fine": 4, "thick": 5},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Disconnected - shaved sides/back, guard 1",
            "top_length": "10-15 cm",
            "texture_method": "Layered, piecey ends",
            "fringe": "Long, center-parted or side-swept",
            "styling": "Blow dry with volume, flat iron optional",
            "products": "Volumizing mousse, light wax, shine spray",
            "beard_pairing": "Clean shaven only",
            "avoid": "Heavy stubble, thick beard"
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
            "top_length": "12-18 cm",
            "texture_method": "Long layers, movement throughout",
            "fringe": "Curtain bangs or swept back",
            "styling": "Blow dry with fingers, sea salt spray",
            "products": "Sea salt spray, light cream, texturizing spray",
            "beard_pairing": "Stubble or light beard",
            "avoid": "Heavy products, stiff hold"
        }
    },
    {
        "id": "curls_waves_shaping",
        "name": "Curls / Waves Shaping",
        "tier": "TRENDING",
        "vibe": "Natural Texture",
        "maintenance": "Medium",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 1, "wavy": 4, "curly": 5, "coarse": 5, "fine": 2, "thick": 5},
        "min_length_cm": 5,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Temp fade or taper, guard 0.5 → 2",
            "top_length": "6-10 cm (stretched)",
            "texture_method": "Curl-specific cutting, shape the curl pattern",
            "fringe": "Curls fall naturally",
            "styling": "Apply curl cream to wet hair, diffuse or air dry",
            "products": "Curl cream, leave-in conditioner, light oil",
            "beard_pairing": "Stubble or shaped beard",
            "avoid": "Brushing dry, heavy silicones"
        }
    },
    {
        "id": "modern_shag_soft_mullet",
        "name": "Modern Shag / Soft Mullet",
        "tier": "TRENDING",
        "vibe": "Weekend Casual",
        "maintenance": "High",
        "daily_time": "5-7 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 5, "oblong": 4, "heart": 4, "diamond": 4},
        "textures": {"straight": 4, "wavy": 5, "curly": 3, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "No fade - tapered, longer at back",
            "top_length": "8-12 cm, back 10-15 cm",
            "texture_method": "Heavy layers, razored ends",
            "fringe": "Choppy curtain bangs",
            "styling": "Blow dry with texture, scrunch for movement",
            "products": "Texture spray, light clay",
            "beard_pairing": "Stubble or mustache",
            "avoid": "Flat ironing, heavy pomades"
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
        "textures": {"straight": 3, "wavy": 5, "curly": 5, "coarse": 5, "fine": 3, "thick": 5},
        "min_length_cm": 4,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Burst fade around ears, guard 0 → 2",
            "top_length": "5-8 cm",
            "texture_method": "Enhance natural curl/wave pattern",
            "fringe": "Curls or waves fall naturally",
            "styling": "Curl cream while wet, air dry or diffuse",
            "products": "Curl cream, light oil, diffuser",
            "beard_pairing": "Stubble or shaped beard",
            "avoid": "Brushing when dry, heavy products"
        }
    },
    
    # ===== TIER 3: BOLD & EDITORIAL =====
    {
        "id": "quiff_skin_fade",
        "name": "Modern Quiff + Skin Fade",
        "tier": "BOLD",
        "vibe": "Statement Style",
        "maintenance": "High",
        "daily_time": "7-10 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 3, "oblong": 3, "heart": 4, "diamond": 5},
        "textures": {"straight": 5, "wavy": 5, "curly": 3, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 10,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "High skin fade, razor clean sides",
            "top_length": "10-15 cm",
            "texture_method": "Layered for lift, weight removed at crown",
            "fringe": "Swept up and back, volume at front",
            "styling": "Blow dry upward with round brush, strong hold",
            "products": "Pre-styler, strong clay, finishing spray",
            "beard_pairing": "Clean or full shaped beard",
            "avoid": "Low maintenance days, humidity"
        }
    },
    {
        "id": "buzz_lineup",
        "name": "Buzz Cut + Sharp Line-up",
        "tier": "BOLD",
        "vibe": "Bold Minimal",
        "maintenance": "Very Low",
        "daily_time": "1 min",
        "face_shapes": {"oval": 4, "round": 3, "square": 5, "oblong": 3, "heart": 3, "diamond": 4},
        "textures": {"straight": 5, "wavy": 5, "curly": 5, "coarse": 5, "fine": 5, "thick": 5},
        "min_length_cm": 0,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Uniform buzz, guard 1-2 all over",
            "top_length": "0.5-1 cm",
            "texture_method": "None - clean buzz",
            "fringe": "None - sharp hairline with razor edge-up",
            "styling": "None needed",
            "products": "Scalp moisturizer, SPF for sun protection",
            "beard_pairing": "Full beard strongly recommended",
            "avoid": "Nothing - ultimate low maintenance"
        }
    },
    {
        "id": "disconnected_undercut",
        "name": "Disconnected Undercut",
        "tier": "BOLD",
        "vibe": "High Contrast",
        "maintenance": "High",
        "daily_time": "5-8 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 4, "heart": 5, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 3, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 12,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Hard disconnect, sides shaved guard 0-1",
            "top_length": "12-18 cm",
            "texture_method": "Long layers, weight at ends",
            "fringe": "Swept back or to side, dramatic",
            "styling": "Blow dry back, pre-styler + clay + spray",
            "products": "Pre-styler, matte clay, strong hold spray",
            "beard_pairing": "Clean or stubble only",
            "avoid": "Humid days without product, full beard"
        }
    },
    {
        "id": "bleached_color_crop",
        "name": "Bleached / Color Crop",
        "tier": "BOLD",
        "vibe": "Editorial Commitment",
        "maintenance": "Very High",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 5, "wavy": 5, "curly": 4, "coarse": 4, "fine": 4, "thick": 5},
        "min_length_cm": 3,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Mid-high fade, guard 0.5 → 2",
            "top_length": "4-6 cm",
            "texture_method": "Textured crop base",
            "fringe": "Forward, textured, bleached",
            "styling": "Purple shampoo weekly, toner maintenance",
            "products": "Purple shampoo, bond repair, matte clay",
            "beard_pairing": "Clean shaven or stubble",
            "avoid": "Chlorine, excessive sun without protection"
        }
    },
]

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="StyleLock AI", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConsultRequest(BaseModel):
    image_base64: str
    vibe_preference: str = "balanced"  # safe, balanced, bold

# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def upload_image_to_host(image_base64: str) -> str:
    """Upload base64 image to free image host, return URL"""
    print("  📤 Uploading user image to host...")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": "6d207e02198a847aa98d0a2a901485a5",
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
            print(f"  ⚠️ Upload error: {resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ Upload failed: {e}")
    
    raise Exception("Failed to upload image")


async def analyze_with_claude(image_base64: str) -> dict:
    """Analyze face/hair with Claude Vision (Opus 4.5)"""
    print("Step 1: Analyzing with Claude Vision (Opus 4.5)...")
    
    prompt = """Analyze this person's face and hair for hairstyle recommendations. Return ONLY valid JSON:

{
    "face_shape": "oval|round|square|oblong|heart|diamond",
    "hair_texture": "straight|wavy|curly|coarse|fine|thick",
    "hair_density": "thick|medium|thin",
    "estimated_top_length_cm": <number>,
    "hairline_state": "full|slightly_receding|receding|thinning_crown",
    "forehead_size": "small|medium|large",
    "jaw_definition": "strong|medium|soft",
    "current_style": "<brief description>",
    "grey_percentage": <number 0-100>,
    "analysis_notes": "<key observations for hairstyle recommendations>"
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
                    "max_tokens": 1000,
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
                print(f"  ❌ Claude API error: {resp.status_code}")
                raise Exception(f"Claude API error: {resp.status_code}")
            
            data = resp.json()
            text = data["content"][0]["text"]
            
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            analysis = json.loads(text.strip())
            print(f"  ✅ Analysis: {analysis['face_shape']} face, {analysis['hair_texture']} hair, ~{analysis['estimated_top_length_cm']}cm")
            return analysis
            
        except json.JSONDecodeError:
            print("  ⚠️ JSON parse error, using fallback")
            return {
                "face_shape": "oval", "hair_texture": "wavy", "hair_density": "medium",
                "estimated_top_length_cm": 5, "hairline_state": "full",
                "forehead_size": "medium", "jaw_definition": "medium",
                "current_style": "short natural", "grey_percentage": 0,
                "analysis_notes": "Fallback values used"
            }


def score_and_recommend(analysis: dict, vibe: str) -> list:
    """Score all 16 looks against user's attributes, return top 3"""
    print(f"Step 2: Scoring 16 looks (vibe: {vibe})...")
    
    face = analysis.get("face_shape", "oval").lower()
    texture = analysis.get("hair_texture", "wavy").lower()
    length_cm = analysis.get("estimated_top_length_cm", 5)
    density = analysis.get("hair_density", "medium").lower()
    hairline = analysis.get("hairline_state", "full").lower()
    
    scored_looks = []
    
    for look in HERO_LOOKS:
        # Face shape score (0-40)
        face_score = look["face_shapes"].get(face, 3) * 8
        
        # Texture score (0-35)
        texture_score = look["textures"].get(texture, 3) * 7
        
        # Thinning bonus (0-10)
        thinning_bonus = 0
        if "thinning" in hairline or "receding" in hairline:
            thinning_bonus = 10 if look["thinning_friendly"] else -5
        
        # Vibe alignment (0-15)
        vibe_score = 10
        if vibe == "safe" and look["tier"] == "CLEAN":
            vibe_score = 15
        elif vibe == "bold" and look["tier"] == "BOLD":
            vibe_score = 15
        elif vibe == "balanced" and look["tier"] == "TRENDING":
            vibe_score = 15
        
        raw_score = face_score + texture_score + thinning_bonus + vibe_score
        
        # CALIBRATED MATCH PERCENTAGE: Map raw score to realistic 70-92% range
        # Raw scores typically range from 50-100
        # We want to output 70-92%
        min_raw, max_raw = 50, 100
        min_pct, max_pct = 70, 92
        calibrated_pct = min_pct + (raw_score - min_raw) * (max_pct - min_pct) / (max_raw - min_raw)
        calibrated_pct = max(min_pct, min(max_pct, int(calibrated_pct)))
        
        # Achievability
        min_length = look["min_length_cm"]
        if length_cm >= min_length:
            achievability = "ready"
            growth_weeks = 0
        else:
            growth_needed = min_length - length_cm
            growth_weeks = int(growth_needed / 0.3)  # ~0.3cm per week
            achievability = "grow" if growth_weeks <= 12 else "dream"
        
        # Get reference image URL
        ref = HAIRSTYLE_REFERENCES.get(look["id"], {})
        
        scored_looks.append({
            **look,
            "total_score": raw_score,
            "match_percentage": calibrated_pct,
            "achievability": achievability,
            "growth_weeks": growth_weeks,
            "reference_url": ref.get("source", "")
        })
    
    scored_looks.sort(key=lambda x: x["total_score"], reverse=True)
    
    # Pick best from each tier based on vibe preference
    result = []
    tiers_found = set()
    
    # Prioritize tiers based on vibe
    if vibe == "safe":
        tier_order = ["CLEAN", "TRENDING", "BOLD"]
    elif vibe == "bold":
        tier_order = ["BOLD", "TRENDING", "CLEAN"]
    else:  # balanced
        tier_order = ["TRENDING", "CLEAN", "BOLD"]
    
    for tier in tier_order:
        for look in scored_looks:
            if look["tier"] == tier and tier not in tiers_found:
                tiers_found.add(tier)
                result.append(look)
                break
    
    # Fill remaining slots
    while len(result) < 3:
        for look in scored_looks:
            if look not in result:
                result.append(look)
                break
    
    print(f"  ✅ Top 3: {[l['name'] for l in result[:3]]}")
    return result[:3]


async def generate_hairstyle_vmodel(target_url: str, look: dict) -> Optional[str]:
    """Generate hairstyle preview using VModel API"""
    look_name = look.get("name", "Unknown")
    source_url = look.get("reference_url", "")
    
    if not source_url:
        print(f"    [{look_name}] ❌ No reference URL")
        return None
    
    print(f"    [{look_name}] Calling VModel...")
    
    headers = {
        "Authorization": f"Bearer {VMODEL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "version": VMODEL_HAIRSTYLE_VERSION,
        "input": {
            "source": source_url,
            "target": target_url,
            "disable_safety_checker": False
        }
    }
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(VMODEL_API_URL, headers=headers, json=payload)
            
            if resp.status_code != 200:
                print(f"    [{look_name}] ❌ API error: {resp.status_code}")
                return None
            
            data = resp.json()
            
            # Check immediate result
            if data.get("status") == "succeeded" and data.get("output"):
                output = data["output"]
                if isinstance(output, list) and output:
                    print(f"    [{look_name}] ✅ Instant result!")
                    return output[0]
                elif isinstance(output, str):
                    print(f"    [{look_name}] ✅ Instant result (string)!")
                    return output
            
            # Poll for result - task_id is inside 'result' object
            result_obj = data.get("result", {})
            task_id = result_obj.get("task_id") or data.get("task_id") or data.get("id")
            if not task_id:
                print(f"    [{look_name}] ❌ No task_id")
                return None
            
            print(f"    [{look_name}] Polling task {task_id}...")
            
            for attempt in range(40):
                await asyncio.sleep(3)
                
                poll_url = f"{VMODEL_TASK_URL}/{task_id}"
                poll_resp = await client.get(poll_url, headers=headers)
                
                if poll_resp.status_code != 200:
                    continue
                
                poll_data = poll_resp.json()
                
                # Handle nested result structure
                result_data = poll_data.get("result", poll_data)
                status = result_data.get("status") or poll_data.get("status", "unknown")
                
                if status in ["succeeded", "completed", "success", "done"]:
                    # Try multiple possible output locations
                    output = (
                        result_data.get("output") or 
                        result_data.get("output_url") or 
                        result_data.get("image_url") or
                        result_data.get("result_url") or
                        poll_data.get("output")
                    )
                    if output:
                        url = output[0] if isinstance(output, list) else output
                        print(f"    [{look_name}] ✅ Done!")
                        return url
                    return None
                
                if status in ["failed", "error", "cancelled"]:
                    print(f"    [{look_name}] ❌ Failed")
                    return None
            
            print(f"    [{look_name}] ❌ Timeout")
            return None
            
        except Exception as e:
            print(f"    [{look_name}] ❌ Error: {e}")
            return None


async def generate_all_previews(target_url: str, looks: list) -> list:
    """Generate all 3 previews in parallel"""
    print("Step 4: Generating 3 previews with VModel...")
    
    tasks = [generate_hairstyle_vmodel(target_url, look) for look in looks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, (look, result) in enumerate(zip(looks, results)):
        if isinstance(result, Exception):
            looks[i]["preview_url"] = None
            looks[i]["preview_error"] = str(result)
        elif result:
            looks[i]["preview_url"] = result
        else:
            looks[i]["preview_url"] = None
    
    success = sum(1 for r in results if r and not isinstance(r, Exception))
    print(f"  ✅ Generated {success}/3 previews")
    
    return looks


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "StyleLock AI",
        "version": "3.0",
        "features": ["vibe_selector", "lock_look", "share", "cut_card_detail"],
        "looks_count": len(HERO_LOOKS),
        "anthropic_key": bool(ANTHROPIC_API_KEY),
        "vmodel_key": bool(VMODEL_API_KEY)
    }


@app.get("/api/debug")
async def debug():
    results = {"config": {"model": CLAUDE_MODEL, "looks": len(HERO_LOOKS)}, "tests": {}}
    
    # Test Anthropic
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": CLAUDE_MODEL, "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}
            )
            results["tests"]["anthropic"] = "✅ Working" if resp.status_code == 200 else f"❌ {resp.status_code}"
    except Exception as e:
        results["tests"]["anthropic"] = f"❌ {e}"
    
    # Test VModel
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.vmodel.ai/api/user/v1/me", headers={"Authorization": f"Bearer {VMODEL_API_KEY}"})
            results["tests"]["vmodel"] = "✅ Working" if resp.status_code == 200 else f"⚠️ {resp.status_code}"
    except Exception as e:
        results["tests"]["vmodel"] = f"❌ {e}"
    
    return results


@app.post("/api/consult")
async def consult(request: ConsultRequest):
    """Main consultation - full pipeline"""
    print("\n" + "="*60 + "\nNEW CONSULTATION\n" + "="*60)
    print(f"Vibe preference: {request.vibe_preference}")
    
    try:
        analysis = await analyze_with_claude(request.image_base64)
        recommendations = score_and_recommend(analysis, request.vibe_preference)
        
        print("Step 3: Uploading user image...")
        target_url = await upload_image_to_host(request.image_base64)
        
        recommendations = await generate_all_previews(target_url, recommendations)
        
        print("\n✅ CONSULTATION COMPLETE\n" + "="*60)
        
        return {"success": True, "analysis": analysis, "recommendations": recommendations}
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """Serve the frontend"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>StyleLock — Lock Your Next Self</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; overflow-x: hidden; }
        .container { max-width: 420px; margin: 0 auto; padding: 16px; min-height: 100vh; }
        
        /* Header */
        .header { text-align: center; padding: 32px 0 24px; }
        .logo { font-size: 32px; font-weight: 900; letter-spacing: -1px; background: linear-gradient(135deg, #fff 0%, #888 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .tagline { font-size: 11px; color: #666; margin-top: 6px; letter-spacing: 3px; text-transform: uppercase; }
        
        /* Vibe Selector */
        .vibe-section { margin: 20px 0; }
        .vibe-label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }
        .vibe-selector { display: flex; gap: 8px; }
        .vibe-btn { flex: 1; padding: 14px 8px; border: 2px solid #333; background: transparent; border-radius: 12px; color: #888; font-size: 12px; font-weight: 700; cursor: pointer; transition: all 0.2s; text-transform: uppercase; letter-spacing: 1px; }
        .vibe-btn.active { border-color: #fff; color: #fff; background: #1a1a1a; }
        .vibe-btn:hover { border-color: #555; }
        .vibe-btn.safe.active { border-color: #00c9a7; color: #00c9a7; }
        .vibe-btn.balanced.active { border-color: #D4FF00; color: #D4FF00; }
        .vibe-btn.bold.active { border-color: #0047FF; color: #0047FF; }
        
        /* Camera Section */
        .camera-section { background: #111; border: 2px dashed #333; border-radius: 20px; padding: 40px 20px; margin: 20px 0; text-align: center; }
        .camera-icon { font-size: 48px; margin-bottom: 16px; filter: grayscale(1); }
        .camera-title { font-size: 18px; font-weight: 700; margin-bottom: 8px; }
        .camera-desc { font-size: 12px; color: #666; margin-bottom: 24px; line-height: 1.5; }
        .upload-btns { display: flex; flex-direction: column; gap: 12px; }
        .btn { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px 24px; border: none; border-radius: 12px; font-size: 13px; font-weight: 700; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; transition: all 0.2s; }
        .btn-primary { background: #fff; color: #000; }
        .btn-primary:hover { background: #eee; transform: scale(0.98); }
        .btn-secondary { background: #1a1a1a; color: #fff; border: 1px solid #333; }
        .btn-secondary:hover { background: #222; }
        input[type="file"] { display: none; }
        
        /* Preview Section */
        .preview-section { display: none; margin: 20px 0; }
        .preview-container { position: relative; border-radius: 16px; overflow: hidden; background: #111; }
        .preview-image { width: 100%; max-height: 400px; object-fit: contain; display: block; }
        .preview-badge { position: absolute; top: 12px; left: 12px; background: #000; padding: 6px 12px; border-radius: 20px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
        .preview-actions { display: flex; gap: 12px; margin-top: 16px; }
        .preview-actions .btn { flex: 1; }
        .btn-generate { background: #D4FF00; color: #000; }
        .btn-generate:hover { background: #c4ef00; }
        
        /* Loading Section */
        .loading-section { display: none; padding: 60px 20px; text-align: center; }
        .loading-visual { position: relative; width: 120px; height: 120px; margin: 0 auto 32px; }
        .loading-ring { position: absolute; inset: 0; border: 3px solid #222; border-top-color: #D4FF00; border-radius: 50%; animation: spin 1s linear infinite; }
        .loading-ring:nth-child(2) { inset: 10px; border-top-color: #0047FF; animation-duration: 1.5s; animation-direction: reverse; }
        .loading-ring:nth-child(3) { inset: 20px; border-top-color: #fff; animation-duration: 2s; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 3px; }
        .loading-step { display: block; color: #fff; font-size: 14px; font-weight: 600; margin-top: 8px; letter-spacing: 0; text-transform: none; }
        
        /* Error Section */
        .error-section { display: none; text-align: center; padding: 60px 20px; }
        .error-icon { font-size: 48px; margin-bottom: 16px; }
        .error-text { color: #ff6b6b; margin-bottom: 24px; font-size: 14px; }
        
        /* Results Section */
        .results-section { display: none; }
        .results-header { text-align: center; margin-bottom: 24px; }
        .results-title { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 8px; }
        .results-headline { font-size: 28px; font-weight: 900; letter-spacing: -1px; }
        
        /* Analysis Card */
        .analysis-card { background: #111; border-radius: 16px; padding: 20px; margin-bottom: 24px; }
        .analysis-title { font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }
        .analysis-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
        .analysis-item { background: #1a1a1a; padding: 10px 12px; border-radius: 8px; }
        .analysis-label { font-size: 9px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .analysis-value { font-size: 13px; font-weight: 600; margin-top: 2px; }
        
        /* Look Cards */
        .look-card { background: #111; border-radius: 20px; overflow: hidden; margin-bottom: 20px; border: 1px solid #222; }
        .look-card.featured { border: 2px solid #D4FF00; }
        .look-card.locked { border: 2px solid #0047FF; }
        .best-match-banner { background: #D4FF00; color: #000; text-align: center; padding: 8px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
        .locked-banner { background: #0047FF; color: #fff; text-align: center; padding: 8px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
        .look-image-container { position: relative; }
        .look-preview { width: 100%; aspect-ratio: 3/4; object-fit: cover; display: block; }
        .look-preview-placeholder { width: 100%; aspect-ratio: 3/4; background: #1a1a1a; display: flex; align-items: center; justify-content: center; color: #444; font-size: 12px; }
        .look-badge { position: absolute; top: 12px; right: 12px; background: rgba(0,0,0,0.85); backdrop-filter: blur(10px); padding: 8px 14px; border-radius: 20px; }
        .look-badge-pct { font-size: 18px; font-weight: 800; }
        .look-badge-label { font-size: 9px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        
        .look-info { padding: 20px; }
        .look-tier { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .tier-clean { background: #00c9a7; color: #000; }
        .tier-trending { background: #D4FF00; color: #000; }
        .tier-bold { background: #0047FF; color: #fff; }
        
        .look-name { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 4px; }
        .look-vibe { font-size: 13px; color: #888; margin-bottom: 16px; }
        
        .look-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: #666; margin-bottom: 16px; }
        .look-meta span { display: flex; align-items: center; gap: 4px; }
        
        .achievability { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; }
        .achievability-ready { background: rgba(0,201,167,0.15); color: #00c9a7; }
        .achievability-grow { background: rgba(212,255,0,0.15); color: #D4FF00; }
        .achievability-dream { background: rgba(0,71,255,0.15); color: #0047FF; }
        .achievability-tip { font-size: 11px; color: #666; margin-top: 8px; }
        
        /* Cut Card */
        .cut-card-toggle { width: 100%; padding: 12px; background: #1a1a1a; border: none; border-radius: 8px; color: #888; font-size: 11px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: space-between; margin-top: 16px; text-transform: uppercase; letter-spacing: 1px; }
        .cut-card-toggle:hover { background: #222; color: #fff; }
        .cut-card-toggle .arrow { transition: transform 0.2s; }
        .cut-card-toggle.open .arrow { transform: rotate(180deg); }
        
        .cut-card { display: none; background: #0a0a0a; border-radius: 12px; padding: 16px; margin-top: 12px; }
        .cut-card.open { display: block; animation: slideDown 0.2s ease; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .cut-card-row { display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid #1a1a1a; }
        .cut-card-row:last-child { border-bottom: none; }
        .cut-card-label { font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 1px; flex-shrink: 0; }
        .cut-card-value { font-size: 12px; color: #fff; text-align: right; max-width: 60%; line-height: 1.4; }
        
        /* Action Buttons */
        .look-actions { display: flex; gap: 8px; margin-top: 16px; }
        .look-actions .btn { flex: 1; padding: 14px 12px; font-size: 11px; }
        .btn-lock { background: #0047FF; color: #fff; }
        .btn-lock:hover { background: #0038cc; }
        .btn-share { background: #1a1a1a; color: #fff; border: 1px solid #333; }
        
        /* Locked State */
        .locked-overlay { position: absolute; inset: 0; background: rgba(0,71,255,0.1); display: flex; align-items: center; justify-content: center; }
        .locked-stamp { background: #0047FF; color: #fff; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; transform: rotate(-5deg); }
        
        /* Modal */
        .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
        .modal-overlay.active { display: flex; }
        .modal { background: #111; border-radius: 20px; max-width: 400px; width: 100%; max-height: 90vh; overflow-y: auto; }
        .modal-header { padding: 20px; border-bottom: 1px solid #222; display: flex; align-items: center; justify-content: space-between; }
        .modal-title { font-size: 16px; font-weight: 700; }
        .modal-close { background: none; border: none; color: #666; font-size: 24px; cursor: pointer; padding: 0; line-height: 1; }
        .modal-body { padding: 20px; }
        
        /* Share Modal */
        .share-options { display: flex; flex-direction: column; gap: 12px; }
        .share-btn { display: flex; align-items: center; gap: 12px; padding: 16px; background: #1a1a1a; border: none; border-radius: 12px; color: #fff; font-size: 14px; font-weight: 500; cursor: pointer; text-align: left; }
        .share-btn:hover { background: #222; }
        .share-icon { font-size: 20px; }
        
        /* Footer */
        .footer { text-align: center; padding: 32px 0; }
        .footer-text { font-size: 10px; color: #444; text-transform: uppercase; letter-spacing: 2px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">STYLELOCK</div>
            <div class="tagline">Lock Your Next Self</div>
        </div>
        
        <!-- Vibe Selector -->
        <div class="vibe-section" id="vibeSection">
            <div class="vibe-label">Choose Your Vibe</div>
            <div class="vibe-selector">
                <button class="vibe-btn safe" data-vibe="safe" onclick="selectVibe('safe')">🎯 Safe</button>
                <button class="vibe-btn balanced active" data-vibe="balanced" onclick="selectVibe('balanced')">⚡ Balanced</button>
                <button class="vibe-btn bold" data-vibe="bold" onclick="selectVibe('bold')">🔥 Bold</button>
            </div>
        </div>
        
        <!-- Camera Section -->
        <div class="camera-section" id="cameraSection">
            <div class="camera-icon">📸</div>
            <div class="camera-title">Upload Your Photo</div>
            <div class="camera-desc">Front-facing, good lighting<br>Face and current hair clearly visible</div>
            <div class="upload-btns">
                <label class="btn btn-primary">
                    📷 Take Selfie
                    <input type="file" accept="image/*" capture="user" id="cameraInput">
                </label>
                <label class="btn btn-secondary">
                    🖼️ Choose from Gallery
                    <input type="file" accept="image/*" id="galleryInput">
                </label>
            </div>
        </div>
        
        <!-- Preview Section -->
        <div class="preview-section" id="previewSection">
            <div class="preview-container">
                <img id="previewImage" class="preview-image" src="" alt="Your photo">
                <div class="preview-badge">Self ID Ready</div>
            </div>
            <div class="preview-actions">
                <button class="btn btn-secondary" onclick="reset()">← Retake</button>
                <button class="btn btn-generate" onclick="generate()">Generate 3 Futures →</button>
            </div>
        </div>
        
        <!-- Loading Section -->
        <div class="loading-section" id="loadingSection">
            <div class="loading-visual">
                <div class="loading-ring"></div>
                <div class="loading-ring"></div>
                <div class="loading-ring"></div>
            </div>
            <div class="loading-text">
                Reading Your Face
                <span class="loading-step" id="loadingStep">Analyzing features...</span>
            </div>
        </div>
        
        <!-- Error Section -->
        <div class="error-section" id="errorSection">
            <div class="error-icon">⚠️</div>
            <div class="error-text" id="errorText">Something went wrong</div>
            <button class="btn btn-primary" onclick="reset()">Try Again</button>
        </div>
        
        <!-- Results Section -->
        <div class="results-section" id="resultsSection">
            <div class="results-header">
                <div class="results-title">Your Transformation</div>
                <div class="results-headline">3 Futures</div>
            </div>
            
            <div class="analysis-card" id="analysisCard">
                <div class="analysis-title">AI Face Reading</div>
                <div class="analysis-grid" id="analysisGrid"></div>
            </div>
            
            <div id="lookCards"></div>
            
            <button class="btn btn-secondary" style="width:100%;margin-top:20px" onclick="reset()">← Start Over</button>
        </div>
        
        <div class="footer">
            <div class="footer-text">StyleLock AI • Beta</div>
        </div>
    </div>
    
    <!-- Share Modal -->
    <div class="modal-overlay" id="shareModal">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-title">Share This Look</div>
                <button class="modal-close" onclick="closeShareModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="share-options">
                    <button class="share-btn" onclick="shareToWhatsApp()">
                        <span class="share-icon">💬</span>
                        Share to WhatsApp
                    </button>
                    <button class="share-btn" onclick="downloadImage()">
                        <span class="share-icon">💾</span>
                        Save to Phone
                    </button>
                    <button class="share-btn" onclick="copyLink()">
                        <span class="share-icon">🔗</span>
                        Copy Link
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let imageBase64 = '';
        let selectedVibe = 'balanced';
        let currentResults = null;
        let lockedLookId = null;
        let shareImageUrl = null;
        
        function selectVibe(vibe) {
            selectedVibe = vibe;
            document.querySelectorAll('.vibe-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.vibe === vibe);
            });
        }
        
        function handleImageSelect(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(ev) {
                imageBase64 = ev.target.result.split(',')[1];
                document.getElementById('previewImage').src = ev.target.result;
                document.getElementById('cameraSection').style.display = 'none';
                document.getElementById('vibeSection').style.display = 'none';
                document.getElementById('previewSection').style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
        
        document.getElementById('cameraInput').addEventListener('change', handleImageSelect);
        document.getElementById('galleryInput').addEventListener('change', handleImageSelect);
        
        function reset() {
            imageBase64 = '';
            lockedLookId = null;
            currentResults = null;
            document.getElementById('cameraInput').value = '';
            document.getElementById('galleryInput').value = '';
            document.getElementById('cameraSection').style.display = 'block';
            document.getElementById('vibeSection').style.display = 'block';
            document.getElementById('previewSection').style.display = 'none';
            document.getElementById('loadingSection').style.display = 'none';
            document.getElementById('errorSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'none';
        }
        
        async function generate() {
            document.getElementById('previewSection').style.display = 'none';
            document.getElementById('loadingSection').style.display = 'block';
            
            const steps = [
                'Analyzing face shape...',
                'Reading hair texture...',
                'Calculating matches...',
                'Generating previews...',
                'Almost there...'
            ];
            let i = 0;
            const interval = setInterval(() => {
                i = (i + 1) % steps.length;
                document.getElementById('loadingStep').textContent = steps[i];
            }, 2500);
            
            try {
                const resp = await fetch('/api/consult', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        image_base64: imageBase64,
                        vibe_preference: selectedVibe
                    })
                });
                
                clearInterval(interval);
                
                const text = await resp.text();
                let data;
                try {
                    data = JSON.parse(text);
                } catch(e) {
                    throw new Error('Invalid server response');
                }
                
                if (!resp.ok || !data.success) {
                    throw new Error(data.detail || data.error || 'Generation failed');
                }
                
                currentResults = data;
                showResults(data);
                
            } catch(e) {
                clearInterval(interval);
                document.getElementById('loadingSection').style.display = 'none';
                document.getElementById('errorSection').style.display = 'block';
                document.getElementById('errorText').textContent = e.message || 'Something went wrong';
            }
        }
        
        function showResults(data) {
            document.getElementById('loadingSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'block';
            
            const a = data.analysis || {};
            document.getElementById('analysisGrid').innerHTML = `
                <div class="analysis-item">
                    <div class="analysis-label">Face Shape</div>
                    <div class="analysis-value">${a.face_shape || 'Unknown'}</div>
                </div>
                <div class="analysis-item">
                    <div class="analysis-label">Hair Texture</div>
                    <div class="analysis-value">${a.hair_texture || 'Unknown'}</div>
                </div>
                <div class="analysis-item">
                    <div class="analysis-label">Density</div>
                    <div class="analysis-value">${a.hair_density || 'Medium'}</div>
                </div>
                <div class="analysis-item">
                    <div class="analysis-label">Current Length</div>
                    <div class="analysis-value">~${a.estimated_top_length_cm || '?'} cm</div>
                </div>
            `;
            
            // Find most achievable
            const recs = data.recommendations || [];
            let bestIdx = 0;
            let bestScore = -999;
            recs.forEach((look, idx) => {
                let score = look.achievability === 'ready' ? 100 : 
                            look.achievability === 'grow' ? (50 - (look.growth_weeks || 0)) : 0;
                if (score > bestScore) { bestScore = score; bestIdx = idx; }
            });
            
            let html = '';
            recs.forEach((look, idx) => {
                const isBest = idx === bestIdx;
                const isLocked = look.id === lockedLookId;
                const tierClass = (look.tier || 'trending').toLowerCase();
                const achClass = look.achievability || 'ready';
                
                let achText, achTip;
                if (achClass === 'ready') {
                    achText = '✓ Ready Now';
                    achTip = 'Your hair length works for this style';
                } else if (achClass === 'grow') {
                    achText = `↑ ${look.growth_weeks || '?'} weeks`;
                    achTip = `Grow ~${Math.round((look.growth_weeks || 4) * 0.3)} cm more`;
                } else {
                    achText = '★ Dream Look';
                    achTip = 'Save this for later';
                }
                
                const cardClass = isLocked ? 'look-card locked' : (isBest ? 'look-card featured' : 'look-card');
                const banner = isLocked ? '<div class="locked-banner">🔒 Locked</div>' : 
                               (isBest ? '<div class="best-match-banner">⭐ Best Match for Your Hair</div>' : '');
                
                const preview = look.preview_url ? 
                    `<img src="${look.preview_url}" class="look-preview" alt="${look.name}">` : 
                    `<div class="look-preview-placeholder">Preview generating...</div>`;
                
                const cutCard = look.cut_card || {};
                const lookId = look.id || idx;
                
                html += `
                <div class="${cardClass}" id="card-${lookId}">
                    ${banner}
                    <div class="look-image-container">
                        ${preview}
                        ${isLocked ? '<div class="locked-overlay"><div class="locked-stamp">LOCKED</div></div>' : ''}
                        <div class="look-badge">
                            <div class="look-badge-pct">${look.match_percentage || '?'}%</div>
                            <div class="look-badge-label">match</div>
                        </div>
                    </div>
                    <div class="look-info">
                        <span class="look-tier tier-${tierClass}">${look.tier || 'Trending'}</span>
                        <div class="look-name">${look.name || 'Hairstyle'}</div>
                        <div class="look-vibe">${look.vibe || ''}</div>
                        <div class="look-meta">
                            <span>🔧 ${look.maintenance || 'Medium'}</span>
                            <span>⏱ ${look.daily_time || '3-5 min'}</span>
                            ${look.thinning_friendly ? '<span>✓ Thin-friendly</span>' : ''}
                        </div>
                        <div class="achievability achievability-${achClass}">${achText}</div>
                        <div class="achievability-tip">${achTip}</div>
                        
                        <button class="cut-card-toggle" onclick="toggleCutCard('${lookId}')">
                            <span>View Cut Card</span>
                            <span class="arrow">▼</span>
                        </button>
                        <div class="cut-card" id="cutcard-${lookId}">
                            <div class="cut-card-row"><span class="cut-card-label">Fade</span><span class="cut-card-value">${cutCard.fade || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Top Length</span><span class="cut-card-value">${cutCard.top_length || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Texture</span><span class="cut-card-value">${cutCard.texture_method || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Fringe</span><span class="cut-card-value">${cutCard.fringe || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Styling</span><span class="cut-card-value">${cutCard.styling || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Products</span><span class="cut-card-value">${cutCard.products || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Beard</span><span class="cut-card-value">${cutCard.beard_pairing || '-'}</span></div>
                            <div class="cut-card-row"><span class="cut-card-label">Avoid</span><span class="cut-card-value">${cutCard.avoid || '-'}</span></div>
                        </div>
                        
                        <div class="look-actions">
                            ${isLocked ? 
                                `<button class="btn btn-share" onclick="openShare('${look.preview_url || ''}', '${look.name}')">📤 Share</button>` :
                                `<button class="btn btn-lock" onclick="lockLook('${lookId}')">🔒 Lock This Look</button>
                                 <button class="btn btn-share" onclick="openShare('${look.preview_url || ''}', '${look.name}')">📤</button>`
                            }
                        </div>
                    </div>
                </div>`;
            });
            
            document.getElementById('lookCards').innerHTML = html;
        }
        
        function toggleCutCard(id) {
            const card = document.getElementById('cutcard-' + id);
            const toggle = card.previousElementSibling;
            card.classList.toggle('open');
            toggle.classList.toggle('open');
        }
        
        function lockLook(id) {
            lockedLookId = id;
            if (currentResults) {
                showResults(currentResults);
            }
            // Scroll to locked card
            setTimeout(() => {
                const card = document.getElementById('card-' + id);
                if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }
        
        function openShare(imageUrl, lookName) {
            shareImageUrl = imageUrl;
            document.getElementById('shareModal').classList.add('active');
        }
        
        function closeShareModal() {
            document.getElementById('shareModal').classList.remove('active');
        }
        
        function shareToWhatsApp() {
            const text = encodeURIComponent('Check out my new hairstyle from StyleLock! 💇‍♂️');
            const url = shareImageUrl ? encodeURIComponent(shareImageUrl) : '';
            window.open(`https://wa.me/?text=${text}%20${url}`, '_blank');
            closeShareModal();
        }
        
        function downloadImage() {
            if (shareImageUrl) {
                const a = document.createElement('a');
                a.href = shareImageUrl;
                a.download = 'stylelock-look.jpg';
                a.target = '_blank';
                a.click();
            }
            closeShareModal();
        }
        
        function copyLink() {
            if (shareImageUrl) {
                navigator.clipboard.writeText(shareImageUrl).then(() => {
                    alert('Link copied!');
                });
            }
            closeShareModal();
        }
        
        // Close modal on outside click
        document.getElementById('shareModal').addEventListener('click', function(e) {
            if (e.target === this) closeShareModal();
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock AI v3.0 starting on port {port}")
    print(f"   Features: Vibe Selector, Lock Look, Share, Cut Card Detail")
    print(f"   {len(HERO_LOOKS)} Hero Looks loaded")
    print(f"   Match % calibrated to 70-92% range")
    print(f"   Anthropic: {'✅' if ANTHROPIC_API_KEY else '❌'}")
    print(f"   VModel: {'✅' if VMODEL_API_KEY else '❌'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
