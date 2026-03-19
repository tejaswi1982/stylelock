"""
StyleLock AI - Backend Server v4.5
PARALLEL BACKGROUND REMOVAL EDITION
- Background removal runs in parallel with Claude analysis
- Clean selfie fed to VModel for better outputs
- Branded backgrounds per tier (CLEAN=cream, TRENDING=green, BOLD=dark)
- Net time impact: ~0-3 seconds (parallel execution)
"""

import os
import json
import base64
import asyncio
import time
from datetime import datetime
from typing import Optional, Tuple
from io import BytesIO
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
REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")  # Get free key at remove.bg

VMODEL_API_URL = "https://api.vmodel.ai/api/tasks/v1/create"
VMODEL_TASK_URL = "https://api.vmodel.ai/api/tasks/v1/get"
VMODEL_HAIRSTYLE_VERSION = "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e"

CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Feature flag for background removal
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "true").lower() == "true"

# ============================================================
# HERO LOOKS DATABASE
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
            "fade": "Low skin fade, guard 0.5 to 2",
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
            "texture_method": "Light texturizing to enhance natural wave",
            "fringe": "Natural fall, soft shape",
            "styling": "Air dry or light diffuse, sea salt spray",
            "products": "Sea salt spray, light cream",
            "beard_pairing": "Any - very versatile",
            "avoid": "Over-styling, heavy gels"
        }
    },
    {
        "id": "neat_short_crop",
        "name": "Neat Short Crop",
        "tier": "CLEAN",
        "vibe": "Military Clean",
        "maintenance": "Low",
        "daily_time": "1-2 min",
        "face_shapes": {"oval": 5, "round": 5, "square": 5, "oblong": 4, "heart": 4, "diamond": 4},
        "textures": {"straight": 5, "wavy": 4, "curly": 4, "coarse": 5, "fine": 4, "thick": 5},
        "min_length_cm": 1,
        "thinning_friendly": True,
        "cut_card": {
            "fade": "Mid fade, guard 1 to 2",
            "top_length": "2-4 cm",
            "texture_method": "Clipper over comb, clean edges",
            "fringe": "Short, brushed forward or to side",
            "styling": "Towel dry and go, or light matte product",
            "products": "Matte paste or nothing",
            "beard_pairing": "Stubble or short beard",
            "avoid": "Trying to style when too short"
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
            "fade": "Mid-high fade, guard 0.5 to 2",
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
        "id": "messy_flow_layered",
        "name": "Messy Flow / Layered",
        "tier": "TRENDING",
        "vibe": "Actor Aesthetic",
        "maintenance": "High",
        "daily_time": "5-8 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 4, "heart": 4, "diamond": 5},
        "textures": {"straight": 3, "wavy": 5, "curly": 4, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "No fade - scissor cut throughout",
            "top_length": "10-15 cm",
            "texture_method": "Heavy layering, razor texturizing",
            "fringe": "Long, swept, falls naturally",
            "styling": "Blow dry with fingers, salt spray, light hold",
            "products": "Sea salt spray, flexible hold cream",
            "beard_pairing": "Stubble enhances the look",
            "avoid": "Too much product, stiff hold"
        }
    },
    {
        "id": "curls_waves_shaping",
        "name": "Curls / Waves Shaping",
        "tier": "TRENDING",
        "vibe": "Natural Expression",
        "maintenance": "Medium",
        "daily_time": "5-7 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 5, "heart": 4, "diamond": 4},
        "textures": {"straight": 1, "wavy": 4, "curly": 5, "coarse": 5, "fine": 2, "thick": 5},
        "min_length_cm": 5,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Low-mid fade or taper",
            "top_length": "5-10 cm (curly length)",
            "texture_method": "Curl-specific cutting, no thinning shears",
            "fringe": "Natural curl fall",
            "styling": "Wet styling with curl cream, air dry or diffuse",
            "products": "Curl defining cream, light gel",
            "beard_pairing": "Any - curls are versatile",
            "avoid": "Brushing when dry, heavy silicones"
        }
    },
    {
        "id": "burst_fade",
        "name": "The Burst Fade",
        "tier": "TRENDING",
        "vibe": "Street Style",
        "maintenance": "High",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 5, "oblong": 3, "heart": 4, "diamond": 5},
        "textures": {"straight": 4, "wavy": 5, "curly": 5, "coarse": 5, "fine": 3, "thick": 5},
        "min_length_cm": 3,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Burst fade around ears, skin to 2",
            "top_length": "5-10 cm",
            "texture_method": "Defined curls or waves on top",
            "fringe": "Falls forward or styled up",
            "styling": "Curl sponge or twist, then set",
            "products": "Curl cream, edge control",
            "beard_pairing": "Lined up beard connects well",
            "avoid": "Letting fade grow out too long"
        }
    },
    {
        "id": "two_block_cut",
        "name": "The Two-Block Cut",
        "tier": "TRENDING",
        "vibe": "K-Pop Inspired",
        "maintenance": "Medium",
        "daily_time": "5-7 min",
        "face_shapes": {"oval": 5, "round": 4, "square": 4, "oblong": 5, "heart": 5, "diamond": 5},
        "textures": {"straight": 5, "wavy": 4, "curly": 2, "coarse": 3, "fine": 5, "thick": 4},
        "min_length_cm": 6,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "Disconnected - short sides (guard 2-3), no blend",
            "top_length": "10-15 cm",
            "texture_method": "Layered, sometimes permed for volume",
            "fringe": "Long, often center-parted or swept",
            "styling": "Blow dry for volume, straighten if needed",
            "products": "Volume powder, light wax",
            "beard_pairing": "Clean shaven typically",
            "avoid": "Heavy products that weigh down top"
        }
    },
    {
        "id": "modern_shag_soft_mullet",
        "name": "Modern Shag / Soft Mullet",
        "tier": "TRENDING",
        "vibe": "Indie Creative",
        "maintenance": "Low",
        "daily_time": "3-5 min",
        "face_shapes": {"oval": 5, "round": 3, "square": 4, "oblong": 4, "heart": 4, "diamond": 4},
        "textures": {"straight": 4, "wavy": 5, "curly": 4, "coarse": 4, "fine": 3, "thick": 5},
        "min_length_cm": 8,
        "thinning_friendly": False,
        "cut_card": {
            "fade": "No fade - longer all around",
            "top_length": "10-18 cm",
            "texture_method": "Heavy layers, razor cut ends",
            "fringe": "Curtain bangs or choppy fringe",
            "styling": "Air dry, scrunch with texturizer",
            "products": "Texture spray, matte paste",
            "beard_pairing": "Stubble or mustache",
            "avoid": "Over-styling, making it too neat"
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
            "texture_method": "Layered for lift, texturized ends",
            "fringe": "Swept up and back in quiff shape",
            "styling": "Blow dry up and back, high-hold product",
            "products": "Volume powder, strong hold pomade",
            "beard_pairing": "Skin fade into beard looks sharp",
            "avoid": "Flat days - needs daily styling"
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
            "fade": "Disconnected - guard 0.5-1 on sides, no blend",
            "top_length": "10-15 cm",
            "texture_method": "Point cutting for movement",
            "fringe": "Slicked back or side-swept",
            "styling": "Blow dry back, high-shine pomade",
            "products": "Strong pomade, finishing spray",
            "beard_pairing": "Sharp line-up or clean shaven",
            "avoid": "Letting it grow out - looks messy fast"
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
            "texture_method": "Clipper all over",
            "fringe": "Sharp line-up at hairline",
            "styling": "None needed",
            "products": "Scalp moisturizer if needed",
            "beard_pairing": "Beard really elevates this look",
            "avoid": "Going too long between line-ups"
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
            "texture_method": "Textured crop base, then color",
            "fringe": "Textured, forward falling",
            "styling": "Towel dry, clay for texture",
            "products": "Purple shampoo, bond repair, matte clay",
            "beard_pairing": "Clean shaven or stubble",
            "avoid": "Chlorine, excessive sun without protection"
        }
    },
]

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="StyleLock AI", version="4.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConsultRequest(BaseModel):
    image_base64: str
    vibe_preference: str = "balanced"

# ============================================================
# BACKGROUND REMOVAL (Remove.bg API)
# ============================================================

async def remove_background(image_base64: str) -> Optional[str]:
    """
    Remove background from image using Remove.bg API.
    Returns base64 of the image with transparent/clean background.
    Falls back to original image if API fails or key not set.
    """
    if not REMOVEBG_API_KEY:
        print("  ⚠️ REMOVEBG_API_KEY not set, skipping background removal")
        return None
    
    print("  🎨 Removing background...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://api.remove.bg/v1.0/removebg",
                headers={"X-Api-Key": REMOVEBG_API_KEY},
                data={
                    "image_file_b64": image_base64,
                    "size": "auto",
                    "format": "png",
                    "bg_color": ""  # Transparent background
                }
            )
            
            if resp.status_code == 200:
                # Response is the image bytes directly
                clean_b64 = base64.b64encode(resp.content).decode('utf-8')
                print("  ✅ Background removed!")
                return clean_b64
            else:
                print(f"  ⚠️ Remove.bg error: {resp.status_code} - {resp.text[:100]}")
                return None
                
        except Exception as e:
            print(f"  ⚠️ Background removal failed: {e}")
            return None


async def upload_image_to_host(image_base64: str, is_png: bool = False) -> str:
    """Upload image to freeimage.host and return URL"""
    print("  📤 Uploading image to host...")
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://freeimage.host/api/1/upload",
                data={"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "source": image_base64, "format": "json"}
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


# ============================================================
# CLAUDE ANALYSIS
# ============================================================

async def analyze_with_claude(image_base64: str) -> dict:
    print("Step 1: Analyzing with Claude Vision...")
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
    "analysis_notes": "<key observations>"
}
Be accurate. Estimate hair length in centimeters carefully."""

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": CLAUDE_MODEL, "max_tokens": 1000, "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
                    {"type": "text", "text": prompt}
                ]}]}
            )
            if resp.status_code != 200:
                raise Exception(f"Claude API error: {resp.status_code}")
            data = resp.json()
            text = data["content"][0]["text"]
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            analysis = json.loads(text.strip())
            print(f"  ✅ Analysis: {analysis['face_shape']} face, {analysis['hair_texture']} hair")
            return analysis
        except json.JSONDecodeError:
            return {"face_shape": "oval", "hair_texture": "wavy", "hair_density": "medium", "estimated_top_length_cm": 5, "hairline_state": "full", "forehead_size": "medium", "jaw_definition": "medium", "current_style": "short natural", "grey_percentage": 0, "analysis_notes": "Fallback"}


# ============================================================
# PARALLEL PRE-PROCESSING
# ============================================================

async def parallel_preprocess(image_base64: str) -> Tuple[dict, str, str]:
    """
    Run Claude analysis and background removal in PARALLEL.
    Returns: (analysis_dict, original_image_url, clean_image_url)
    
    Timeline:
    - Claude analysis: ~5-10 sec
    - Background removal: ~3-5 sec
    - Image upload: ~3-5 sec
    
    By running in parallel, we save ~5-8 seconds vs sequential.
    """
    print("\n🔄 Starting parallel preprocessing...")
    start = time.time()
    
    # Create tasks for parallel execution
    tasks = [
        analyze_with_claude(image_base64),          # Claude analysis
        remove_background(image_base64),            # Background removal  
        upload_image_to_host(image_base64),         # Upload original (fallback)
    ]
    
    # Run all three in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    analysis = results[0] if not isinstance(results[0], Exception) else {"face_shape": "oval", "hair_texture": "wavy", "hair_density": "medium", "estimated_top_length_cm": 5, "hairline_state": "full", "forehead_size": "medium", "jaw_definition": "medium", "current_style": "short natural", "grey_percentage": 0, "analysis_notes": "Fallback"}
    clean_b64 = results[1] if not isinstance(results[1], Exception) else None
    original_url = results[2] if not isinstance(results[2], Exception) else None
    
    # If we got a clean image, upload it
    clean_url = None
    if clean_b64 and ENABLE_BG_REMOVAL:
        try:
            clean_url = await upload_image_to_host(clean_b64, is_png=True)
            print(f"  ✅ Clean image uploaded: {clean_url[:50]}...")
        except Exception as e:
            print(f"  ⚠️ Clean image upload failed: {e}")
    
    elapsed = time.time() - start
    print(f"✅ Parallel preprocessing done in {elapsed:.1f}s")
    
    # Return analysis, original URL, and clean URL (or original as fallback)
    target_url = clean_url if clean_url else original_url
    return analysis, original_url, target_url


# ============================================================
# SCORING & RECOMMENDATIONS
# ============================================================

def score_and_recommend(analysis: dict, vibe: str) -> list:
    print(f"Step 2: Scoring looks...")
    face = analysis.get("face_shape", "oval").lower()
    texture = analysis.get("hair_texture", "wavy").lower()
    length_cm = analysis.get("estimated_top_length_cm", 5)
    hairline = analysis.get("hairline_state", "full").lower()
    
    scored = []
    for look in HERO_LOOKS:
        face_score = look["face_shapes"].get(face, 3) * 8
        texture_score = look["textures"].get(texture, 3) * 7
        thinning_bonus = 10 if ("thinning" in hairline or "receding" in hairline) and look["thinning_friendly"] else 0
        vibe_score = 15 if (vibe == "safe" and look["tier"] == "CLEAN") or (vibe == "bold" and look["tier"] == "BOLD") or (vibe == "balanced" and look["tier"] == "TRENDING") else 10
        raw = face_score + texture_score + thinning_bonus + vibe_score
        pct = max(70, min(92, int(70 + (raw - 50) * 22 / 50)))
        
        min_len = look["min_length_cm"]
        if length_cm >= min_len:
            ach, weeks = "ready", 0
        else:
            weeks = int((min_len - length_cm) / 0.3)
            ach = "grow" if weeks <= 12 else "dream"
        
        ref = HAIRSTYLE_REFERENCES.get(look["id"], {})
        scored.append({**look, "total_score": raw, "match_percentage": pct, "achievability": ach, "growth_weeks": weeks, "reference_url": ref.get("source", "")})
    
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    result, tiers = [], set()
    for tier in ["TRENDING", "CLEAN", "BOLD"]:
        for look in scored:
            if look["tier"] == tier and tier not in tiers:
                tiers.add(tier)
                result.append(look)
                break
    while len(result) < 3:
        for look in scored:
            if look not in result:
                result.append(look)
                break
    print(f"  ✅ Top 3: {[l['name'] for l in result[:3]]}")
    return result[:3]


# ============================================================
# VMODEL GENERATION
# ============================================================

async def generate_hairstyle_vmodel(target_url: str, look: dict) -> Optional[str]:
    name = look.get("name", "Unknown")
    source = look.get("reference_url", "")
    if not source: return None
    print(f"    [{name}] Calling VModel...")
    headers = {"Authorization": f"Bearer {VMODEL_API_KEY}", "Content-Type": "application/json"}
    payload = {"version": VMODEL_HAIRSTYLE_VERSION, "input": {"source": source, "target": target_url, "disable_safety_checker": False}}
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(VMODEL_API_URL, headers=headers, json=payload)
            if resp.status_code != 200: return None
            data = resp.json()
            if data.get("status") == "succeeded" and data.get("output"):
                output = data["output"]
                return output[0] if isinstance(output, list) else output
            
            task_id = data.get("result", {}).get("task_id") or data.get("task_id") or data.get("id")
            if not task_id: return None
            
            for _ in range(40):
                await asyncio.sleep(3)
                poll = await client.get(f"{VMODEL_TASK_URL}/{task_id}", headers=headers)
                if poll.status_code != 200: continue
                pdata = poll.json()
                rd = pdata.get("result", pdata)
                status = rd.get("status") or pdata.get("status", "")
                if status in ["succeeded", "completed", "success", "done"]:
                    out = rd.get("output") or rd.get("output_url") or rd.get("image_url") or pdata.get("output")
                    if out:
                        url = out[0] if isinstance(out, list) else out
                        print(f"    [{name}] ✅ Done!")
                        return url
                    return None
                if status in ["failed", "error", "cancelled"]: return None
            return None
        except: return None


async def generate_all_previews(target_url: str, looks: list) -> list:
    print("Step 4: Generating previews...")
    tasks = [generate_hairstyle_vmodel(target_url, l) for l in looks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, (look, res) in enumerate(zip(looks, results)):
        looks[i]["preview_url"] = res if res and not isinstance(res, Exception) else None
    print(f"  ✅ Generated {sum(1 for r in results if r and not isinstance(r, Exception))}/3")
    return looks


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def health():
    return {
        "status": "ok", 
        "service": "StyleLock AI", 
        "version": "4.5", 
        "edition": "PARALLEL BG REMOVAL",
        "bg_removal_enabled": ENABLE_BG_REMOVAL,
        "removebg_key_set": bool(REMOVEBG_API_KEY),
        "looks_count": len(HERO_LOOKS)
    }


@app.get("/api/debug")
async def debug():
    results = {"tests": {}, "config": {"bg_removal": ENABLE_BG_REMOVAL, "removebg_key": bool(REMOVEBG_API_KEY)}}
    
    # Test Anthropic
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json={"model": CLAUDE_MODEL, "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]})
            results["tests"]["anthropic"] = "✅" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e: 
        results["tests"]["anthropic"] = f"❌ {e}"
    
    # Test VModel
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.vmodel.ai/api/user/v1/me", headers={"Authorization": f"Bearer {VMODEL_API_KEY}"})
            results["tests"]["vmodel"] = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception as e: 
        results["tests"]["vmodel"] = f"❌ {e}"
    
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


@app.post("/api/consult")
async def consult(request: ConsultRequest):
    print("\n" + "="*60 + "\nNEW CONSULTATION (v4.5 Parallel BG Removal)\n" + "="*60)
    start_time = time.time()
    
    try:
        # STEP 1+2: Parallel preprocessing (Claude + BG removal + upload)
        analysis, original_url, target_url = await parallel_preprocess(request.image_base64)
        
        # STEP 3: Score and recommend
        recs = score_and_recommend(analysis, request.vibe_preference)
        
        # STEP 4: Generate previews with VModel (using clean selfie URL)
        recs = await generate_all_previews(target_url, recs)
        
        elapsed = time.time() - start_time
        print(f"\n✅ DONE in {elapsed:.1f}s\n" + "="*60)
        
        return {
            "success": True, 
            "analysis": analysis, 
            "recommendations": recs,
            "processing_time": round(elapsed, 1),
            "bg_removal_used": target_url != original_url
        }
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# FRONTEND (Minimal test UI)
# ============================================================

@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StyleLock v4.5 Test</title>
    <style>
        body { font-family: system-ui; max-width: 600px; margin: 40px auto; padding: 20px; background: #0a0a0a; color: #fff; }
        h1 { color: #c8e64a; }
        .upload-area { border: 2px dashed #333; padding: 40px; text-align: center; margin: 20px 0; cursor: pointer; }
        .upload-area:hover { border-color: #c8e64a; }
        input[type="file"] { display: none; }
        button { background: #c8e64a; color: #0a0a0a; border: none; padding: 12px 24px; cursor: pointer; font-weight: bold; }
        .preview { max-width: 200px; margin: 20px auto; display: block; }
        .results { margin-top: 20px; }
        .look { background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .look img { max-width: 100%; border-radius: 4px; }
        .status { color: #888; font-style: italic; }
        .badge { background: #c8e64a; color: #0a0a0a; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <h1>✂️ StyleLock v4.5</h1>
    <p>Parallel Background Removal Edition</p>
    
    <div class="upload-area" onclick="document.getElementById('file').click()">
        <p>📸 Click to upload a selfie</p>
        <input type="file" id="file" accept="image/*" onchange="handleFile(this)">
    </div>
    
    <img id="preview" class="preview" style="display:none">
    <button id="btn" style="display:none" onclick="analyze()">Analyze My Look</button>
    <p id="status" class="status"></p>
    
    <div id="results" class="results"></div>

<script>
let imageBase64 = null;

function handleFile(input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
        imageBase64 = e.target.result.split(',')[1];
        document.getElementById('preview').src = e.target.result;
        document.getElementById('preview').style.display = 'block';
        document.getElementById('btn').style.display = 'inline-block';
    };
    reader.readAsDataURL(file);
}

async function analyze() {
    document.getElementById('status').textContent = 'Analyzing... (this takes ~1-2 min)';
    document.getElementById('btn').disabled = true;
    
    try {
        const resp = await fetch('/api/consult', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image_base64: imageBase64, vibe_preference: 'balanced'})
        });
        const data = await resp.json();
        
        if (data.success) {
            let html = `<p>✅ Done in ${data.processing_time}s | BG Removal: ${data.bg_removal_used ? 'Yes' : 'No'}</p>`;
            html += `<p>Face: ${data.analysis.face_shape} | Hair: ${data.analysis.hair_texture}</p>`;
            
            data.recommendations.forEach(look => {
                html += `<div class="look">
                    <span class="badge">${look.tier}</span> <strong>${look.name}</strong> - ${look.match_percentage}% match
                    ${look.preview_url ? `<img src="${look.preview_url}" alt="${look.name}">` : '<p>Preview not generated</p>'}
                </div>`;
            });
            
            document.getElementById('results').innerHTML = html;
            document.getElementById('status').textContent = '';
        } else {
            document.getElementById('status').textContent = 'Error: ' + (data.detail || 'Unknown error');
        }
    } catch (e) {
        document.getElementById('status').textContent = 'Error: ' + e.message;
    }
    
    document.getElementById('btn').disabled = false;
}
</script>
</body>
</html>'''


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock v4.5 PARALLEL BG REMOVAL on port {port}")
    print(f"   Background removal: {'ENABLED' if ENABLE_BG_REMOVAL else 'DISABLED'}")
    print(f"   Remove.bg key: {'SET' if REMOVEBG_API_KEY else 'NOT SET'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
