"""
StyleLock AI - Backend Server v4.1
MAGAZINE EDITION - Full Editorial Redesign
- Full-bleed photos (one look = one screen)
- MASSIVE tier typography over photos
- Wavy/vintage stamp badges
- Cream/colored backgrounds per tier
- Magazine-style Cut Card (full page)
- Poster-worthy Locked screen
- Swipeable results carousel
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
            "fade": "Burst fade around ears, guard 0 to 2",
            "top_length": "5-8 cm",
            "texture_method": "Enhance natural curl/wave pattern",
            "fringe": "Curls or waves fall naturally",
            "styling": "Curl cream while wet, air dry or diffuse",
            "products": "Curl cream, light oil, diffuser",
            "beard_pairing": "Stubble or shaped beard",
            "avoid": "Brushing when dry, heavy products"
        }
    },
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
            "fade": "Mid-high fade, guard 0.5 to 2",
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

app = FastAPI(title="StyleLock AI", version="4.1")

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
# HELPER FUNCTIONS (same as before)
# ============================================================

async def upload_image_to_host(image_base64: str) -> str:
    print("  📤 Uploading user image to host...")
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
    return {"status": "ok", "service": "StyleLock AI", "version": "4.1", "edition": "MAGAZINE", "looks_count": len(HERO_LOOKS)}

@app.get("/api/debug")
async def debug():
    results = {"tests": {}}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json={"model": CLAUDE_MODEL, "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]})
            results["tests"]["anthropic"] = "✅" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e: results["tests"]["anthropic"] = f"❌ {e}"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.vmodel.ai/api/user/v1/me", headers={"Authorization": f"Bearer {VMODEL_API_KEY}"})
            results["tests"]["vmodel"] = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception as e: results["tests"]["vmodel"] = f"❌ {e}"
    return results

@app.post("/api/consult")
async def consult(request: ConsultRequest):
    print("\n" + "="*60 + "\nNEW CONSULTATION\n" + "="*60)
    try:
        analysis = await analyze_with_claude(request.image_base64)
        recs = score_and_recommend(analysis, request.vibe_preference)
        print("Step 3: Uploading image...")
        target = await upload_image_to_host(request.image_base64)
        recs = await generate_all_previews(target, recs)
        print("\n✅ DONE\n" + "="*60)
        return {"success": True, "analysis": analysis, "recommendations": recs}
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>STYLELOCK</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Anton&family=Caveat:wght@500;700&family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --black: #0A0A0A;
            --white: #FFFFFF;
            --cream: #F5F0E6;
            --volt: #D4FF00;
            --blue: #0047FF;
            --gray: #888888;
            --taupe: #C4B8A8;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        html, body { height: 100%; overflow: hidden; }
        body { font-family: 'Inter', sans-serif; background: var(--black); color: var(--black); }
        
        /* Screens */
        .screen { display: none; height: 100vh; width: 100vw; position: fixed; top: 0; left: 0; overflow: hidden; }
        .screen.active { display: flex; flex-direction: column; }
        
        /* ===== HOME SCREEN ===== */
        .home { background: var(--cream); position: relative; }
        .home-bg {
            position: absolute; top: -10%; left: -20%; right: -20%;
            font-family: 'Anton', sans-serif; font-size: 22vw; line-height: 0.85;
            color: var(--blue); text-transform: uppercase; opacity: 1;
            pointer-events: none; z-index: 1; white-space: nowrap;
        }
        .home-bg span { display: block; }
        .home-content { position: relative; z-index: 2; flex: 1; display: flex; flex-direction: column; justify-content: flex-end; padding: 24px; }
        .home-labels { position: absolute; top: 20px; left: 20px; right: 20px; display: flex; justify-content: space-between; z-index: 3; }
        .label { font-family: 'Space Mono', monospace; font-size: 9px; letter-spacing: 0.15em; text-transform: uppercase; color: var(--black); opacity: 0.5; }
        .home-upload { background: var(--white); border: 2px dashed #ddd; padding: 40px 24px; text-align: center; margin-bottom: 20px; }
        .upload-icon { font-size: 40px; margin-bottom: 12px; }
        .upload-text { font-size: 12px; color: var(--gray); margin-bottom: 20px; line-height: 1.5; }
        .btn { display: block; width: 100%; padding: 18px; border: none; font-family: 'Anton', sans-serif; font-size: 14px; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; margin-bottom: 10px; }
        .btn-black { background: var(--black); color: var(--white); }
        .btn-outline { background: transparent; color: var(--black); border: 2px solid var(--black); }
        .btn-blue { background: var(--blue); color: var(--white); }
        .btn-volt { background: var(--volt); color: var(--black); }
        input[type="file"] { display: none; }
        
        /* ===== PREVIEW SCREEN ===== */
        .preview { background: var(--cream); }
        .preview-bg {
            position: absolute; top: 0; left: -10%; right: -10%;
            font-family: 'Anton', sans-serif; font-size: 18vw; line-height: 0.9;
            color: var(--black); opacity: 0.08; pointer-events: none; z-index: 1;
        }
        .preview-photo-wrap {
            position: relative; z-index: 2; flex: 1; display: flex; align-items: center; justify-content: center; padding: 20px;
        }
        .preview-photo-container {
            position: relative; width: 75%; max-width: 280px; aspect-ratio: 3/4; background: var(--white); box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }
        .preview-photo { width: 100%; height: 100%; object-fit: cover; filter: grayscale(100%) contrast(1.1); }
        .preview-id-strip { position: absolute; top: 10px; left: 10px; right: 10px; display: flex; justify-content: space-between; }
        .preview-id-strip span { font-family: 'Space Mono', monospace; font-size: 8px; letter-spacing: 0.1em; text-transform: uppercase; background: var(--white); padding: 4px 8px; }
        .preview-script {
            position: absolute; bottom: -30px; right: -20px;
            font-family: 'Caveat', cursive; font-size: 32px; color: var(--volt);
            transform: rotate(-5deg); text-shadow: 2px 2px 0 var(--black);
        }
        .preview-headline {
            position: absolute; bottom: 60px; left: 0; right: 0;
            font-family: 'Anton', sans-serif; font-size: 14vw; text-align: center;
            color: var(--black); text-transform: uppercase; line-height: 0.9;
        }
        .preview-actions { position: relative; z-index: 2; padding: 20px 24px 40px; }
        
        /* ===== LOADING SCREEN ===== */
        .loading { background: var(--black); justify-content: center; align-items: center; }
        .loading-text {
            font-family: 'Anton', sans-serif; font-size: 20vw; color: var(--white);
            text-transform: uppercase; animation: pulse 1.2s ease-in-out infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .loading-bars { display: flex; gap: 6px; margin-top: 30px; }
        .loading-bar { height: 4px; background: var(--volt); animation: glitch 0.6s ease-in-out infinite; }
        .loading-bar:nth-child(1) { width: 40px; }
        .loading-bar:nth-child(2) { width: 60px; animation-delay: 0.1s; }
        .loading-bar:nth-child(3) { width: 30px; animation-delay: 0.2s; }
        .loading-bar:nth-child(4) { width: 50px; animation-delay: 0.3s; }
        @keyframes glitch { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; transform: translateX(2px); } }
        .loading-script { font-family: 'Caveat', cursive; font-size: 28px; color: var(--volt); margin-top: 20px; }
        .loading-step { font-family: 'Space Mono', monospace; font-size: 10px; color: var(--gray); margin-top: 20px; letter-spacing: 0.2em; text-transform: uppercase; }
        
        /* ===== RESULTS CAROUSEL ===== */
        .results { background: var(--cream); overflow: hidden; }
        .results-header {
            position: absolute; top: 0; left: 0; right: 0; z-index: 100;
            padding: 20px; display: flex; justify-content: space-between; align-items: flex-start;
        }
        .results-title { font-family: 'Anton', sans-serif; font-size: 8vw; color: var(--black); line-height: 0.9; }
        .results-title span { color: var(--blue); }
        .results-nav { display: flex; gap: 8px; margin-top: 10px; }
        .nav-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--black); opacity: 0.2; cursor: pointer; }
        .nav-dot.active { opacity: 1; }
        
        .carousel { display: flex; height: 100%; transition: transform 0.4s ease; }
        .slide { min-width: 100vw; height: 100vh; position: relative; display: flex; flex-direction: column; }
        
        /* Slide backgrounds per tier */
        .slide-clean { background: var(--cream); }
        .slide-trending { background: linear-gradient(to bottom, #E8E0D5 0%, #D4CFC5 100%); }
        .slide-bold { background: var(--black); color: var(--white); }
        
        .slide-photo {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 70%; max-width: 300px; aspect-ratio: 3/4;
            box-shadow: 0 30px 80px rgba(0,0,0,0.3); z-index: 2;
        }
        .slide-photo img { width: 100%; height: 100%; object-fit: cover; }
        
        .slide-tier {
            position: absolute; top: 12%; left: 0; right: 0;
            font-family: 'Anton', sans-serif; font-size: 28vw; text-align: center;
            line-height: 0.8; z-index: 1; pointer-events: none;
        }
        .slide-clean .slide-tier { color: var(--black); }
        .slide-trending .slide-tier { color: var(--volt); text-shadow: 3px 3px 0 var(--black); }
        .slide-bold .slide-tier { color: var(--blue); }
        
        /* Wavy stamp badge */
        .stamp {
            position: absolute; bottom: 25%; left: 50%; transform: translateX(-50%) rotate(-8deg);
            width: 100px; height: 100px; z-index: 10;
        }
        .stamp svg { width: 100%; height: 100%; }
        .stamp-text {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            text-align: center;
        }
        .stamp-pct { font-family: 'Anton', sans-serif; font-size: 24px; display: block; }
        .stamp-label { font-family: 'Space Mono', monospace; font-size: 8px; letter-spacing: 0.1em; }
        .slide-clean .stamp-pct, .slide-trending .stamp-pct { color: var(--blue); }
        .slide-bold .stamp-pct { color: var(--volt); }
        
        .slide-script {
            position: absolute; bottom: 18%; right: 15%;
            font-family: 'Caveat', cursive; font-size: 24px; transform: rotate(-5deg); z-index: 10;
        }
        .slide-clean .slide-script, .slide-trending .slide-script { color: var(--blue); }
        .slide-bold .slide-script { color: var(--volt); }
        
        .slide-actions {
            position: absolute; bottom: 0; left: 0; right: 0;
            padding: 20px 24px 40px; z-index: 20;
        }
        .slide-bold .slide-actions .btn-black { background: var(--white); color: var(--black); }
        
        /* ===== CUT CARD SCREEN ===== */
        .cutcard { background: var(--cream); overflow-y: auto; }
        .cutcard-header {
            position: sticky; top: 0; background: var(--cream);
            padding: 20px; display: flex; align-items: center; gap: 15px;
            border-bottom: 1px solid #ddd; z-index: 10;
        }
        .cutcard-back { font-size: 24px; cursor: pointer; }
        .cutcard-title { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; }
        .cutcard-photo { width: 100%; aspect-ratio: 4/3; object-fit: cover; filter: grayscale(100%); }
        .cutcard-script {
            position: absolute; top: 50%; right: 20px; transform: rotate(-10deg);
            font-family: 'Caveat', cursive; font-size: 20px; color: var(--volt);
        }
        .cutcard-badge {
            position: absolute; bottom: 20px; right: 20px;
            background: var(--blue); color: var(--white);
            padding: 8px 16px; font-family: 'Anton', sans-serif; font-size: 12px;
            text-transform: uppercase; transform: rotate(3deg);
        }
        .cutcard-content { padding: 24px; }
        .cutcard-section { margin-bottom: 24px; border-bottom: 1px solid #ddd; padding-bottom: 20px; }
        .cutcard-section:last-child { border-bottom: none; }
        .cutcard-label {
            display: inline-block; background: var(--blue); color: var(--white);
            font-family: 'Space Mono', monospace; font-size: 9px; padding: 4px 8px;
            letter-spacing: 0.1em; margin-bottom: 8px;
        }
        .cutcard-value { font-family: 'Anton', sans-serif; font-size: 28px; text-transform: uppercase; margin-bottom: 4px; }
        .cutcard-desc { font-size: 13px; color: var(--gray); line-height: 1.5; }
        .cutcard-actions { padding: 20px 24px 40px; }
        
        /* ===== LOCKED SCREEN ===== */
        .locked { background: var(--cream); }
        .locked-photo {
            position: absolute; top: 0; left: 0; right: 0; bottom: 30%;
            overflow: hidden;
        }
        .locked-photo img { width: 100%; height: 100%; object-fit: cover; filter: grayscale(100%) contrast(1.1); }
        .locked-headline {
            position: absolute; top: 5%; left: 0; right: 0;
            font-family: 'Anton', sans-serif; font-size: 25vw; text-align: center;
            color: var(--black); line-height: 0.85; z-index: 2;
        }
        .locked-stamp {
            position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%) rotate(-15deg);
            border: 4px solid var(--blue); border-radius: 50%; width: 120px; height: 120px;
            display: flex; align-items: center; justify-content: center; z-index: 10;
        }
        .locked-stamp-inner {
            font-family: 'Anton', sans-serif; font-size: 18px; color: var(--blue);
            text-transform: uppercase; letter-spacing: 0.1em;
        }
        .locked-script {
            position: absolute; top: 55%; left: 50%; transform: translateX(-50%) rotate(-5deg);
            font-family: 'Caveat', cursive; font-size: 36px; color: var(--volt);
            text-shadow: 2px 2px 0 var(--black); z-index: 10;
        }
        .locked-actions {
            position: absolute; bottom: 0; left: 0; right: 0;
            padding: 20px 24px 40px; background: var(--black); z-index: 20;
        }
        .locked-actions .btn { margin-bottom: 12px; }
        .locked-actions .btn:last-child { margin-bottom: 0; }
        
        /* ===== ERROR ===== */
        .error { background: var(--black); justify-content: center; align-items: center; padding: 40px; text-align: center; }
        .error-icon { font-size: 60px; margin-bottom: 20px; }
        .error-text { color: #ff6b6b; margin-bottom: 30px; font-size: 14px; }
        
        /* Share Modal */
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
        .modal.active { display: flex; }
        .modal-box { background: var(--white); width: 100%; max-width: 340px; }
        .modal-header { padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
        .modal-title { font-family: 'Anton', sans-serif; font-size: 16px; }
        .modal-close { font-size: 24px; cursor: pointer; }
        .modal-body { padding: 20px; }
        .share-btn { display: flex; align-items: center; gap: 12px; width: 100%; padding: 16px; background: #f5f5f5; border: none; font-size: 14px; cursor: pointer; margin-bottom: 10px; }
        .share-btn:last-child { margin-bottom: 0; }
    </style>
</head>
<body>

<!-- HOME -->
<div class="screen home active" id="homeScreen">
    <div class="home-bg"><span>STYLE</span><span>LOCK</span><span>STYLE</span><span>LOCK</span></div>
    <div class="home-labels"><span class="label">Identity</span><span class="label">Beta 1.0</span></div>
    <div class="home-content">
        <div class="home-upload">
            <div class="upload-icon">📸</div>
            <p class="upload-text">Front-facing photo<br>Good lighting • Face visible</p>
            <label class="btn btn-black">Take Selfie<input type="file" accept="image/*" capture="user" id="cameraInput"></label>
            <label class="btn btn-outline">Choose Photo<input type="file" accept="image/*" id="galleryInput"></label>
        </div>
    </div>
</div>

<!-- PREVIEW -->
<div class="screen preview" id="previewScreen">
    <div class="preview-bg">DRAFT<br>READY<br>SELF<br>ID</div>
    <div class="preview-photo-wrap">
        <div class="preview-photo-container">
            <div class="preview-id-strip"><span>Self ID</span><span>Draft 01</span></div>
            <img id="previewImg" class="preview-photo" src="" alt="">
            <span class="preview-script">this is you</span>
        </div>
    </div>
    <div class="preview-headline">CHECK</div>
    <div class="preview-actions">
        <button class="btn btn-black" onclick="generate()">Analyze This Face</button>
        <button class="btn btn-outline" onclick="goHome()">← Retake</button>
    </div>
</div>

<!-- LOADING -->
<div class="screen loading" id="loadingScreen">
    <div class="loading-text" id="loadingText">READING</div>
    <div class="loading-bars"><div class="loading-bar"></div><div class="loading-bar"></div><div class="loading-bar"></div><div class="loading-bar"></div></div>
    <p class="loading-script">hold still</p>
    <p class="loading-step" id="loadingStep">Analyzing features...</p>
</div>

<!-- ERROR -->
<div class="screen error" id="errorScreen">
    <div class="error-icon">⚠️</div>
    <p class="error-text" id="errorText">Something went wrong</p>
    <button class="btn btn-black" style="background:#fff;color:#000" onclick="goHome()">Try Again</button>
</div>

<!-- RESULTS CAROUSEL -->
<div class="screen results" id="resultsScreen">
    <div class="results-header">
        <div>
            <div class="results-title">YOUR <span>3</span><br>FUTURES</div>
            <div class="results-nav" id="resultsNav"></div>
        </div>
        <button class="btn btn-outline" style="width:auto;padding:10px 16px;font-size:11px" onclick="goHome()">←</button>
    </div>
    <div class="carousel" id="carousel"></div>
</div>

<!-- CUT CARD -->
<div class="screen cutcard" id="cutcardScreen">
    <div class="cutcard-header">
        <span class="cutcard-back" onclick="backToResults()">←</span>
        <span class="cutcard-title">StyleLock Cut Card</span>
    </div>
    <div style="position:relative">
        <img id="cutcardPhoto" class="cutcard-photo" src="" alt="">
        <span class="cutcard-script">show this to the barber</span>
        <span class="cutcard-badge" id="cutcardBadge">READY</span>
    </div>
    <div class="cutcard-content" id="cutcardContent"></div>
    <div class="cutcard-actions">
        <button class="btn btn-blue" id="cutcardLockBtn">Lock This Look</button>
    </div>
</div>

<!-- LOCKED -->
<div class="screen locked" id="lockedScreen">
    <div class="locked-photo"><img id="lockedPhoto" src="" alt=""></div>
    <div class="locked-headline">LOCKED</div>
    <div class="locked-stamp"><span class="locked-stamp-inner">✓ LOCKED</span></div>
    <span class="locked-script">this is it</span>
    <div class="locked-actions">
        <button class="btn btn-volt" onclick="showBarber()">Show Your Barber</button>
        <button class="btn btn-outline" style="border-color:#fff;color:#fff" onclick="saveToPhone()">Save to Phone</button>
        <button class="btn btn-outline" style="border-color:#444;color:#888" onclick="goHome()">Start Over</button>
    </div>
</div>

<!-- SHARE MODAL -->
<div class="modal" id="shareModal">
    <div class="modal-box">
        <div class="modal-header"><span class="modal-title">Share</span><span class="modal-close" onclick="closeModal()">×</span></div>
        <div class="modal-body">
            <button class="share-btn" onclick="shareWhatsApp()">💬 WhatsApp</button>
            <button class="share-btn" onclick="saveToPhone()">💾 Save to Phone</button>
            <button class="share-btn" onclick="copyLink()">🔗 Copy Link</button>
        </div>
    </div>
</div>

<script>
let imageBase64 = '';
let results = null;
let currentSlide = 0;
let currentLookIdx = 0;

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
document.getElementById('cameraInput').addEventListener('change', handleImage);
document.getElementById('galleryInput').addEventListener('change', handleImage);

async function generate() {
    show('loadingScreen');
    const phases = [{t:'READING',s:'Analyzing face shape...'},{t:'READING',s:'Detecting hair texture...'},{t:'MATCHING',s:'Finding your looks...'},{t:'BUILDING',s:'Generating previews...'}];
    let i = 0;
    const iv = setInterval(() => {
        i = (i + 1) % phases.length;
        document.getElementById('loadingText').textContent = phases[i].t;
        document.getElementById('loadingStep').textContent = phases[i].s;
    }, 2500);
    
    try {
        const resp = await fetch('/api/consult', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image_base64: imageBase64, vibe_preference: 'balanced'})
        });
        clearInterval(iv);
        const data = await resp.json();
        if (!resp.ok || !data.success) throw new Error(data.detail || 'Failed');
        results = data;
        renderResults();
    } catch(e) {
        clearInterval(iv);
        document.getElementById('errorText').textContent = e.message;
        show('errorScreen');
    }
}

function renderResults() {
    const recs = results.recommendations || [];
    const nav = document.getElementById('resultsNav');
    const carousel = document.getElementById('carousel');
    
    nav.innerHTML = recs.map((_, i) => `<div class="nav-dot ${i===0?'active':''}" onclick="goSlide(${i})"></div>`).join('');
    
    carousel.innerHTML = recs.map((look, i) => {
        const tier = (look.tier || 'TRENDING').toUpperCase();
        const tierClass = tier.toLowerCase();
        const scripts = ['not bad', 'pick one', 'this could be you'];
        const ach = look.achievability === 'ready' ? 'READY' : look.achievability === 'grow' ? `${look.growth_weeks}W GROW` : 'DREAM';
        
        return `
        <div class="slide slide-${tierClass}">
            <div class="slide-tier">${tier}</div>
            <div class="slide-photo">
                ${look.preview_url ? `<img src="${look.preview_url}" alt="${look.name}">` : '<div style="width:100%;height:100%;background:#ddd;display:flex;align-items:center;justify-content:center;font-size:12px;color:#888">Generating...</div>'}
            </div>
            <div class="stamp">
                <svg viewBox="0 0 100 100"><path d="M50 2 C55 8, 62 5, 68 8 C74 11, 78 6, 85 12 C92 18, 97 15, 98 25 C99 35, 95 40, 98 50 C101 60, 96 65, 92 72 C88 79, 93 85, 85 90 C77 95, 72 92, 65 95 C58 98, 52 95, 45 98 C38 101, 32 97, 25 92 C18 87, 12 91, 8 82 C4 73, 8 67, 5 58 C2 49, 5 42, 3 33 C1 24, 6 18, 12 12 C18 6, 25 10, 32 5 C39 0, 45 4, 50 2 Z" fill="none" stroke="${tier==='BOLD'?'#D4FF00':'#0047FF'}" stroke-width="2"/>
                </svg>
                <div class="stamp-text"><span class="stamp-pct">${look.match_percentage}%</span><span class="stamp-label">MATCH</span></div>
            </div>
            <span class="slide-script">${scripts[i] || 'pick one'}</span>
            <div class="slide-actions">
                <button class="btn btn-black" onclick="viewCutCard(${i})">View Cut Card</button>
                <button class="btn btn-outline" ${tier==='BOLD'?'style="border-color:#fff;color:#fff"':''} onclick="lockLook(${i})">Lock This Look</button>
            </div>
        </div>`;
    }).join('');
    
    show('resultsScreen');
}

function goSlide(i) {
    currentSlide = i;
    document.getElementById('carousel').style.transform = `translateX(-${i * 100}vw)`;
    document.querySelectorAll('.nav-dot').forEach((d, idx) => d.classList.toggle('active', idx === i));
}

function viewCutCard(i) {
    currentLookIdx = i;
    const look = results.recommendations[i];
    const cc = look.cut_card || {};
    
    document.getElementById('cutcardPhoto').src = look.preview_url || '';
    document.getElementById('cutcardBadge').textContent = look.achievability === 'ready' ? 'READY' : look.achievability === 'grow' ? 'GROW' : 'DREAM';
    
    const sections = [
        {label: 'FADE', key: 'fade'},
        {label: 'TOP', key: 'top_length'},
        {label: 'FRINGE', key: 'fringe'},
        {label: 'STYLING', key: 'styling'},
        {label: 'PRODUCTS', key: 'products'},
        {label: 'AVOID', key: 'avoid'}
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

function lockLook(i) {
    currentLookIdx = i;
    const look = results.recommendations[i];
    document.getElementById('lockedPhoto').src = look.preview_url || '';
    show('lockedScreen');
}

function showBarber() {
    show('cutcardScreen');
}

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
        navigator.clipboard.writeText(look.preview_url).then(() => alert('Link copied!'));
    }
    closeModal();
}

function closeModal() { document.getElementById('shareModal').classList.remove('active'); }
document.getElementById('shareModal').onclick = e => { if (e.target.id === 'shareModal') closeModal(); };

// Swipe support
let touchStartX = 0;
document.getElementById('resultsScreen').addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; });
document.getElementById('resultsScreen').addEventListener('touchend', e => {
    const diff = touchStartX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 50) {
        if (diff > 0 && currentSlide < 2) goSlide(currentSlide + 1);
        else if (diff < 0 && currentSlide > 0) goSlide(currentSlide - 1);
    }
});
</script>
</body>
</html>'''


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock v4.1 MAGAZINE EDITION on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
