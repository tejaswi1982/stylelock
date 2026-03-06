"""
StyleLock AI — Backend Server (Claude + VModel)
===============================================
Receives a selfie, uses Claude for analysis, scores hero looks,
then uses VModel AI Hairstyle (reference-image workflow) to generate previews.

DEPLOY:
  Railway / Render / any Python host

SETUP:
  pip install fastapi uvicorn httpx python-multipart

RUN LOCAL:
  python -m uvicorn stylelock_server:app --reload --host 127.0.0.1 --port 8000

RAILWAY START COMMAND:
  uvicorn stylelock_server:app --host 0.0.0.0 --port $PORT

REQUIRED ENV VARS:
  ANTHROPIC_API_KEY=...
  ANTHROPIC_MODEL=...
  VMODEL_API_TOKEN=...
  VMODEL_HAIRSTYLE_VERSION=5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e

OPTIONAL ENV VARS:
  FREEIMAGE_KEY=...
  IMGBB_KEY=...
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx
import base64
import json
import asyncio
import time
import os
import random
from typing import Optional, Dict, Any
from urllib.parse import quote

app = FastAPI(title="StyleLock AI", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # lock down later
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────
# ENV
# ──────────────────────────────────────────────────────
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "").strip()

VMODEL_API_TOKEN = os.getenv("VMODEL_API_TOKEN", "").strip()
VMODEL_HAIRSTYLE_VERSION = os.getenv(
    "VMODEL_HAIRSTYLE_VERSION",
    "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e"
).strip()

FREEIMAGE_KEY = os.getenv("FREEIMAGE_KEY", "6d207e02198a847aa98d0a2a901485a5").strip()
IMGBB_KEY = os.getenv("IMGBB_KEY", "d36eb6591370ae7f9089d85ff1e7237c").strip()

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
VMODEL_CREATE_URL = "https://api.vmodel.ai/api/tasks/v1/create"
VMODEL_GET_URL_BASE = "https://api.vmodel.ai/api/tasks/v1/get"

# ──────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────
def _timeout(timeout_s: float) -> httpx.Timeout:
    return httpx.Timeout(timeout_s, connect=15.0, read=timeout_s, write=timeout_s, pool=timeout_s)

async def post_with_retries(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    data: Any = None,
    json_body: Any = None,
    timeout_s: float = 60,
    tries: int = 3,
    label: str = "HTTP POST",
) -> httpx.Response:
    for attempt in range(1, tries + 1):
        try:
            async with httpx.AsyncClient(timeout=_timeout(timeout_s)) as client:
                resp = await client.post(url, headers=headers, data=data, json=json_body)
                if resp.status_code in (429, 500, 502, 503, 504):
                    body_preview = (resp.text or "")[:250]
                    raise httpx.HTTPStatusError(
                        f"{label}: transient status {resp.status_code}. Body: {body_preview}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
            if attempt < tries:
                backoff = (2 ** (attempt - 1)) + random.random()
                print(f"⚠️ {label} failed ({attempt}/{tries}): {repr(e)}")
                print(f"   Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                print(f"❌ {label} failed after {tries} attempts: {repr(e)}")
                raise
    raise Exception(f"{label} failed unexpectedly")

async def get_with_retries(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: float = 60,
    tries: int = 3,
    label: str = "HTTP GET",
) -> httpx.Response:
    for attempt in range(1, tries + 1):
        try:
            async with httpx.AsyncClient(timeout=_timeout(timeout_s)) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code in (429, 500, 502, 503, 504):
                    body_preview = (resp.text or "")[:250]
                    raise httpx.HTTPStatusError(
                        f"{label}: transient status {resp.status_code}. Body: {body_preview}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
            if attempt < tries:
                backoff = (2 ** (attempt - 1)) + random.random()
                print(f"⚠️ {label} failed ({attempt}/{tries}): {repr(e)}")
                print(f"   Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                print(f"❌ {label} failed after {tries} attempts: {repr(e)}")
                raise
    raise Exception(f"{label} failed unexpectedly")

# ──────────────────────────────────────────────────────
# HERO LOOKS
# IMPORTANT: replace each vmodel_source with a REAL public URL
# ──────────────────────────────────────────────────────
HERO_LOOKS = [
    {
        "id": "T1-01", "tier": "CLEAN", "name": "Classic Scissor Taper",
        "vibe": "Corporate Polish", "maintenance": "Low", "daily_time": "2-3 min",
        "min_length_cm": 5, "min_density": "low", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":3,"round":3,"square":3,"oblong":3,"diamond":3,"heart":3},
        "texture_scores": {"straight":3,"wavy":3,"curly":2,"coily":1},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/classic_scissor_taper.jpg",
        "card": {
            "fade": "Scissor taper — graduated 1cm ear to 3cm parietal ridge. No clippers.",
            "top": "5-7 cm, point cutting for natural texture",
            "fringe": "Side-swept or slightly off-centre",
            "styling": "Towel dry → light cream → comb → air dry",
            "products": "Light hold cream or matte paste",
            "avoid": "Heavy product looks greasy on Indian hair. Not ideal for very curly.",
            "beard": "All styles. Best: clean shaven or stubble."
        }
    },
    {
        "id": "T1-04", "tier": "CLEAN", "name": "Executive Contour",
        "vibe": "Traditional Grooming", "maintenance": "High", "daily_time": "7-10 min",
        "min_length_cm": 6, "min_density": "low", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":3,"round":3,"square":2,"oblong":2,"diamond":2,"heart":2},
        "texture_scores": {"straight":3,"wavy":2,"curly":1,"coily":0},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/executive_contour.jpg",
        "card": {
            "fade": "Traditional taper — Guard 4 to Guard 2, gradual, no skin.",
            "top": "6-8 cm, layered for volume illusion. NO thinning shears.",
            "fringe": "Side-swept with volume at crown",
            "styling": "Blow dry with round brush → mousse → set with fingers",
            "products": "Volumizing mousse + light pomade",
            "avoid": "Requires blow drying. NO thinning shears on fine hair.",
            "beard": "Short groomed or clean shaven."
        }
    },
    {
        "id": "T2-01", "tier": "TRENDING", "name": "Taper + Textured Top",
        "vibe": "Everyday Sharp", "maintenance": "Medium", "daily_time": "4-5 min",
        "min_length_cm": 5, "min_density": "medium", "receding_ok": False, "thinning_ok": False,
        "required_texture": None,
        "face_scores": {"oval":3,"round":2,"square":3,"oblong":2,"diamond":2,"heart":2},
        "texture_scores": {"straight":3,"wavy":3,"curly":2,"coily":1},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/taper_textured_top.jpg",
        "card": {
            "fade": "Low-mid taper — Guard 1.5 nape, Guard 3 temples.",
            "top": "5-8 cm, point cut + texturize",
            "fringe": "Forward or side, messy-intentional",
            "styling": "Towel dry → matte paste → fingers → lift front",
            "products": "Matte paste or texturizing clay",
            "avoid": "Needs product — without it reads as bedhead. Retaper every 2-3 weeks.",
            "beard": "Stubble or clean shaven."
        }
    },
    {
        "id": "T2-02", "tier": "TRENDING", "name": "Textured French Crop",
        "vibe": "Effortless Cool", "maintenance": "Low", "daily_time": "2-3 min",
        "min_length_cm": 3, "min_density": "medium", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":3,"round":3,"square":2,"oblong":2,"diamond":2,"heart":3},
        "texture_scores": {"straight":3,"wavy":3,"curly":1,"coily":0},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/textured_french_crop.jpg",
        "card": {
            "fade": "Mid-high fade — Guard 1 nape, Guard 2 temples.",
            "top": "3-5 cm, longer at fringe. Heavy point cutting.",
            "fringe": "Forward textured fringe to mid-forehead",
            "styling": "Towel dry → matte clay → push fringe forward → break apart",
            "products": "Matte clay or texture spray",
            "avoid": "NOT for curly hair. Great for thick Indian hair. Hides receding hairline.",
            "beard": "Stubble is the classic pairing."
        }
    },
    {
        "id": "T2-03", "tier": "TRENDING", "name": "Two-Block Cut",
        "vibe": "K-Pop Influence", "maintenance": "Medium", "daily_time": "8-12 min",
        "min_length_cm": 8, "min_density": "high", "receding_ok": False, "thinning_ok": False,
        "required_texture": "straight",
        "face_scores": {"oval":2,"round":1,"square":2,"oblong":3,"diamond":2,"heart":3},
        "texture_scores": {"straight":3,"wavy":1,"curly":0,"coily":0},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/two_block_cut.jpg",
        "card": {
            "fade": "Disconnected block — Guard 2-3, NO blend, sharp horizontal line.",
            "top": "8-12 cm, slide cut layers, curtain bangs",
            "fringe": "Curtain bangs or side-swept",
            "styling": "Blow dry (essential) → cream → part → optional flat iron",
            "products": "Styling cream + heat protectant",
            "avoid": "ONLY straight to slightly wavy. Curly will poof. Blow dry every time.",
            "beard": "Clean shaven strongly recommended."
        }
    },
    {
        "id": "T2-05", "tier": "TRENDING", "name": "Curls / Waves Shaping",
        "vibe": "Natural Texture", "maintenance": "Medium", "daily_time": "10-15 min",
        "min_length_cm": 5, "min_density": "medium", "receding_ok": False, "thinning_ok": False,
        "required_texture": "curly",
        "face_scores": {"oval":3,"round":3,"square":3,"oblong":3,"diamond":3,"heart":3},
        "texture_scores": {"straight":0,"wavy":2,"curly":3,"coily":3},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/curls_waves_shaping.jpg",
        "card": {
            "fade": "Low/mid taper, preserve curl length. Min 2cm sides.",
            "top": "5-10 cm (varies by curl tightness)",
            "fringe": "Natural — curls determine direction",
            "styling": "Curl cream soaking wet → scrunch → diffuse → scrunch out crunch",
            "products": "Curl cream + gel. Sulphate-free shampoo.",
            "avoid": "NO THINNING SHEARS. Show Cut Card BEFORE barber starts.",
            "beard": "Natural groomed beard."
        }
    },
    {
        "id": "T3-01", "tier": "BOLD", "name": "Quiff + Skin Fade",
        "vibe": "Statement Style", "maintenance": "High", "daily_time": "10-15 min",
        "min_length_cm": 8, "min_density": "high", "receding_ok": False, "thinning_ok": False,
        "required_texture": None,
        "face_scores": {"oval":3,"round":2,"square":2,"oblong":2,"diamond":3,"heart":2},
        "texture_scores": {"straight":3,"wavy":3,"curly":1,"coily":0},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/quiff_skin_fade.jpg",
        "card": {
            "fade": "Skin fade — Guard 0 nape, Guard 1.5 temples.",
            "top": "8-12 cm front, 5-7 cm crown",
            "fringe": "Up and back — quiff off forehead",
            "styling": "Blow dry up → strong clay → shape quiff → hairspray",
            "products": "Strong clay + hairspray. Blow dryer essential.",
            "avoid": "Without blow dry = bad combover. Touch-up every 1.5 weeks.",
            "beard": "Clean shaven or sharp stubble."
        }
    },
    {
        "id": "T3-02", "tier": "BOLD", "name": "Buzz + Sharp Line-up",
        "vibe": "Bold Minimal", "maintenance": "Very Low", "daily_time": "0-1 min",
        "min_length_cm": 0.5, "min_density": "any", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":2,"round":2,"square":3,"oblong":2,"diamond":2,"heart":2},
        "texture_scores": {"straight":3,"wavy":3,"curly":3,"coily":3},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/buzz_lineup.jpg",
        "card": {
            "fade": "Uniform buzz — Guard 1-2 all over.",
            "top": "0.5-1.5 cm, clipper only",
            "fringe": "N/A",
            "styling": "Done. Moisturize scalp. SPF outdoors.",
            "products": "Scalp moisturizer only.",
            "avoid": "Head shape exposed. Line-up fades in ~1 week.",
            "beard": "Full beard = power combo."
        }
    },
    {
        "id": "T3-03", "tier": "BOLD", "name": "Burst Fade",
        "vibe": "Athletic Edge", "maintenance": "Medium", "daily_time": "3-5 min",
        "min_length_cm": 4, "min_density": "medium", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":2,"round":3,"square":3,"oblong":2,"diamond":2,"heart":2},
        "texture_scores": {"straight":3,"wavy":3,"curly":3,"coily":2},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/burst_fade.jpg",
        "card": {
            "fade": "Burst fade — Guard 0 behind ear arc, Guard 1-2 nape.",
            "top": "4-8 cm, point cut texture",
            "fringe": "Forward or messy up",
            "styling": "Towel dry → matte paste → texture → style up",
            "products": "Matte paste or clay",
            "avoid": "MUST be symmetrical. Skilled barber essential.",
            "beard": "Stubble or short beard."
        }
    },
    {
        "id": "T3-05", "tier": "BOLD", "name": "Bleached / Color Crop",
        "vibe": "Editorial", "maintenance": "Very High", "daily_time": "5 min + colour",
        "min_length_cm": 3, "min_density": "medium", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,
        "face_scores": {"oval":3,"round":3,"square":3,"oblong":3,"diamond":3,"heart":3},
        "texture_scores": {"straight":3,"wavy":3,"curly":3,"coily":2},
        "vmodel_source": "https://YOUR_PUBLIC_BUCKET/hero_looks/bleached_color_crop.jpg",
        "card": {
            "fade": "Mid-high fade — Guard 1-2, colour on top only.",
            "top": "3-6 cm, textured crop base",
            "fringe": "Forward — colour shows from front",
            "styling": "Colour-safe shampoo → product → texture fingers",
            "products": "Colour-safe products. Purple shampoo if blonde.",
            "avoid": "Indian hair needs MULTIPLE sessions. Budget ₹3-8K. Fades 4-6 weeks.",
            "beard": "Dark beard + light hair = max contrast."
        }
    },
]

# ──────────────────────────────────────────────────────
# STEP 1 — Claude analysis
# ──────────────────────────────────────────────────────
async def analyze_with_claude(image_b64: str) -> dict:
    if not ANTHROPIC_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")
    if not ANTHROPIC_MODEL:
        raise HTTPException(status_code=500, detail="ANTHROPIC_MODEL is not set")

    print("STEP 1: Claude analyze")

    resp = await post_with_retries(
        ANTHROPIC_URL,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        json_body={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 1000,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                    {"type": "text", "text": """Analyze this person's hair for a hairstyle recommendation app.
Be very precise about measurements. Return ONLY valid JSON:
{"faceShape":"oval|round|square|oblong|diamond|heart",
"hairTexture":"straight|wavy|curly|coily",
"density":"thick|medium|thin|very_thin",
"estimatedTopLengthCm":<number>,
"hairlineState":"normal|slightly_receding|receding|very_receding",
"crownState":"full|slightly_thin|thinning|bald_spot",
"foreheadSize":"small|medium|large",
"jawDefinition":"strong|medium|soft",
"currentStyle":"<description>",
"greyPercentage":<number>,
"beardPresent":true|false,
"beardStyle":"<description>",
"achievabilityNotes":"<2 sentences on realistic hairstyle options>"}"""}
                ]
            }]
        },
        timeout_s=90,
        tries=3,
        label="Claude analyze",
    )

    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    clean = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Claude JSON parse error: {e}. Preview: {clean[:300]}")

    return result

# ──────────────────────────────────────────────────────
# STEP 2 — Scoring
# ──────────────────────────────────────────────────────
def score_and_pick(analysis: dict) -> list:
    face = analysis.get("faceShape", "oval").lower()
    texture = analysis.get("hairTexture", "wavy").lower()
    density = analysis.get("density", "medium").lower()
    length = analysis.get("estimatedTopLengthCm", 5)
    hairline = analysis.get("hairlineState", "normal").lower()
    crown = analysis.get("crownState", "full").lower()

    is_receding = "receding" in hairline
    is_thinning = "thin" in density or "thin" in crown

    scored = []
    for look in HERO_LOOKS:
        if look["required_texture"]:
            if look["required_texture"] == "straight" and texture not in ("straight",):
                continue
            if look["required_texture"] == "curly" and texture not in ("curly", "coily"):
                continue

        tex_score = look["texture_scores"].get(texture, 0)
        if tex_score == 0:
            continue

        min_len = look["min_length_cm"]
        if length >= min_len:
            length_pts = 40
            achievability = "ready"
        elif length >= min_len * 0.6:
            length_pts = 25
            achievability = "grow"
        elif length >= min_len * 0.3:
            length_pts = 10
            achievability = "dream"
        else:
            length_pts = 0
            achievability = "blocked"

        if achievability == "blocked":
            continue

        density_req = look["min_density"]
        if density_req == "any" or density_req == "low":
            density_pts = 30
        elif density_req == "medium":
            if "thin" in density or "very" in density:
                density_pts = 10
            else:
                density_pts = 30
        elif density_req == "high":
            if "thick" in density:
                density_pts = 30
            elif "medium" in density:
                density_pts = 15
            else:
                continue
        else:
            density_pts = 20

        if is_receding and not look["receding_ok"]:
            hairline_pts = 0
        elif is_receding and look["receding_ok"]:
            hairline_pts = 15
        else:
            hairline_pts = 15

        face_pts = look["face_scores"].get(face, 1) / 3 * 15
        thin_bonus = 5 if is_thinning and look["thinning_ok"] else 0
        total = round(length_pts + density_pts + hairline_pts + face_pts + thin_bonus)

        if achievability in ("grow", "dream"):
            gap = max(0, min_len - length)
            weeks = round(gap / 1.25 * 4.3)
        else:
            gap = 0
            weeks = 0

        scored.append({
            **look,
            "score": total,
            "achievability": achievability,
            "growth_gap_cm": round(gap, 1),
            "growth_weeks": weeks,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    tiers = ["CLEAN", "TRENDING", "BOLD"]
    picks = []
    for tier in tiers:
        tier_looks = [l for l in scored if l["tier"] == tier]
        ready = [l for l in tier_looks if l["achievability"] == "ready"]
        grow = [l for l in tier_looks if l["achievability"] == "grow"]
        dream = [l for l in tier_looks if l["achievability"] == "dream"]

        if ready:
            picks.append(ready[0])
        elif grow:
            picks.append(grow[0])
        elif dream:
            picks.append(dream[0])

    return picks[:3]

# ──────────────────────────────────────────────────────
# STEP 3 — Upload target image to public host
# ──────────────────────────────────────────────────────
async def upload_image_to_host(image_b64: str) -> str:
    print("STEP 3: Upload selfie to public host")

    # freeimage.host
    try:
        resp = await post_with_retries(
            "https://freeimage.host/api/1/upload",
            data={
                "key": FREEIMAGE_KEY,
                "action": "upload",
                "source": image_b64,
                "format": "json",
            },
            timeout_s=45,
            tries=3,
            label="freeimage.host upload",
        )
        data = resp.json()
        url = (data.get("image", {}) or {}).get("url")
        if url:
            return url
    except Exception as e:
        print(f"⚠️ freeimage.host failed: {repr(e)}")

    # imgbb fallback
    try:
        resp = await post_with_retries(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_KEY,
                "image": image_b64,
                "expiration": 600,
            },
            timeout_s=45,
            tries=3,
            label="imgbb upload",
        )
        data = resp.json()
        if data.get("success"):
            url = (data.get("data", {}) or {}).get("url")
            if url:
                return url
    except Exception as e:
        print(f"⚠️ imgbb failed: {repr(e)}")

    raise HTTPException(status_code=502, detail="Could not upload selfie to public host")

# ──────────────────────────────────────────────────────
# STEP 4 — VModel generation
# source = hairstyle reference URL
# target = uploaded selfie URL
# ──────────────────────────────────────────────────────
async def generate_hairstyle_vmodel(target_image_url: str, source_image_url: str, look_name: str = "") -> Optional[str]:
    if not VMODEL_API_TOKEN:
        print(f"⚠️ VMODEL_API_TOKEN missing. Skipping: {look_name}")
        return None

    if not VMODEL_HAIRSTYLE_VERSION:
        print(f"⚠️ VMODEL_HAIRSTYLE_VERSION missing. Skipping: {look_name}")
        return None

    if not source_image_url or "YOUR_PUBLIC_BUCKET" in source_image_url:
        print(f"⚠️ Missing real vmodel_source URL for: {look_name}")
        return None

    print(f"STEP 4: VModel generate - {look_name}")

    headers = {
        "Authorization": f"Bearer {VMODEL_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Create task
    try:
        create_resp = await post_with_retries(
            VMODEL_CREATE_URL,
            headers=headers,
            json_body={
                "version": VMODEL_HAIRSTYLE_VERSION,
                "input": {
                    "source": source_image_url,
                    "target": target_image_url,
                    "disable_safety_checker": False,
                },
            },
            timeout_s=60,
            tries=3,
            label=f"VModel create ({look_name})",
        )
        create_data = create_resp.json()
    except Exception as e:
        print(f"❌ VModel create failed [{look_name}]: {repr(e)}")
        return None

    task_id = ((create_data.get("result") or {}).get("task_id"))
    if not task_id:
        print(f"❌ No task_id from VModel [{look_name}]: {json.dumps(create_data)[:300]}")
        return None

    # Poll task
    for attempt in range(40):
        await asyncio.sleep(3)

        try:
            poll_resp = await get_with_retries(
                f"{VMODEL_GET_URL_BASE}/{task_id}",
                headers={"Authorization": f"Bearer {VMODEL_API_TOKEN}"},
                timeout_s=45,
                tries=3,
                label=f"VModel poll ({look_name})",
            )
            poll_data = poll_resp.json()
        except Exception as e:
            print(f"⚠️ VModel poll error [{look_name}] attempt {attempt+1}: {repr(e)}")
            continue

        result = poll_data.get("result") or {}
        status = (result.get("status") or "").lower()
        output = result.get("output") or []

        print(f"    [{look_name}] poll {attempt+1}/40 status={status}")

        if status == "succeeded" and output:
            return output[0]

        if status in ("failed", "canceled"):
            print(f"❌ VModel failed [{look_name}]: {result.get('error')}")
            return None

    print(f"❌ VModel timeout [{look_name}]")
    return None

# ──────────────────────────────────────────────────────
# MAIN ENDPOINT
# ──────────────────────────────────────────────────────
@app.post("/api/consult")
async def consult(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        image_b64 = base64.b64encode(contents).decode("utf-8")
        print(f"Image received: {len(contents)} bytes")

        # 1. analyze
        analysis = await analyze_with_claude(image_b64)

        # 2. score
        picks = score_and_pick(analysis)
        if not picks:
            return JSONResponse(status_code=400, content={
                "success": False,
                "error": "No matching looks found for this hair profile",
                "analysis": analysis,
                "step": "scoring",
            })

        # 3. upload user selfie once
        target_image_url = await upload_image_to_host(image_b64)

        # 4. generate all three previews in parallel
        generation_tasks = [
            generate_hairstyle_vmodel(target_image_url, pick["vmodel_source"], pick["name"])
            for pick in picks
        ]

        try:
            raw_preview_urls = await asyncio.wait_for(
                asyncio.gather(*generation_tasks, return_exceptions=True),
                timeout=180,
            )
            raw_preview_urls = [u if isinstance(u, str) else None for u in raw_preview_urls]
        except asyncio.TimeoutError:
            print("⚠️ VModel generation timed out")
            raw_preview_urls = [None] * len(picks)

        # Build response; use backend proxy so frontend can display VModel outputs
        recommendations = []
        for pick, raw_url in zip(picks, raw_preview_urls):
            proxy_url = None
            if raw_url:
                proxy_url = f"/api/proxy-image?url={quote(raw_url, safe='')}"
            recommendations.append({
                "look": {
                    "id": pick["id"],
                    "tier": pick["tier"],
                    "name": pick["name"],
                    "vibe": pick["vibe"],
                    "maintenance": pick["maintenance"],
                    "daily_time": pick["daily_time"],
                    "card": pick["card"],
                },
                "score": pick["score"],
                "achievability": pick["achievability"],
                "growth_gap_cm": pick.get("growth_gap_cm", 0),
                "growth_weeks": pick.get("growth_weeks", 0),
                "preview_url": proxy_url,
                "raw_preview_url": raw_url,
            })

        elapsed = round(time.time() - start_time, 1)
        print(f"✅ Done in {elapsed}s")

        return JSONResponse({
            "success": True,
            "elapsed_seconds": elapsed,
            "analysis": analysis,
            "recommendations": recommendations,
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": f"Backend error: {type(e).__name__}: {str(e)}",
        })

# ──────────────────────────────────────────────────────
# PROXY VModel output so browser can display it
# VModel task docs indicate output files may require Authorization
# ──────────────────────────────────────────────────────
@app.get("/api/proxy-image")
async def proxy_image(url: str = Query(...)):
    if not VMODEL_API_TOKEN:
        raise HTTPException(status_code=500, detail="VMODEL_API_TOKEN missing")

    try:
        resp = await get_with_retries(
            url,
            headers={"Authorization": f"Bearer {VMODEL_API_TOKEN}"},
            timeout_s=60,
            tries=3,
            label="Proxy image",
        )
        content_type = resp.headers.get("content-type", "image/webp")
        return Response(content=resp.content, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch proxied image: {e}")

# ──────────────────────────────────────────────────────
# DEBUG / HEALTH
# ──────────────────────────────────────────────────────
@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "StyleLock AI",
        "version": "2.0",
        "anthropic_key_set": bool(ANTHROPIC_KEY),
        "anthropic_model_set": bool(ANTHROPIC_MODEL),
        "vmodel_token_set": bool(VMODEL_API_TOKEN),
        "vmodel_version": VMODEL_HAIRSTYLE_VERSION,
    }

@app.get("/api/looks")
async def list_looks():
    return {
        "looks": [{
            "id": l["id"],
            "tier": l["tier"],
            "name": l["name"],
            "vibe": l["vibe"],
            "min_length_cm": l["min_length_cm"],
            "min_density": l["min_density"],
            "has_vmodel_source": bool(l.get("vmodel_source")) and "YOUR_PUBLIC_BUCKET" not in l.get("vmodel_source", ""),
        } for l in HERO_LOOKS]
    }

@app.get("/api/debug")
async def debug():
    return {
        "config": {
            "anthropic_key_set": bool(ANTHROPIC_KEY),
            "anthropic_model": ANTHROPIC_MODEL or "NOT SET",
            "vmodel_token_set": bool(VMODEL_API_TOKEN),
            "vmodel_version": VMODEL_HAIRSTYLE_VERSION or "NOT SET",
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
