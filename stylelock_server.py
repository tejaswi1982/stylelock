"""
StyleLock AI — Backend Server (Robust + Debuggable)
===================================================
One endpoint receives a selfie, orchestrates:
Claude Vision + Scoring Engine + Image Host Upload + LightX
Returns 3 hairstyle previews with Cut Cards.

DEPLOY: Railway, Render, or any Python hosting
SETUP:
  pip install fastapi uvicorn httpx python-multipart

RUN (local):
  python -m uvicorn stylelock_server:app --reload --host 127.0.0.1 --port 8000

RUN (Railway Start Command):
  uvicorn stylelock_server:app --host 0.0.0.0 --port $PORT

ENV VARS:
  ANTHROPIC_API_KEY=sk-ant-...
  LIGHTX_API_KEY=...
  (optional) ANTHROPIC_MODEL=...
  (optional) FREEIMAGE_KEY=...
  (optional) IMGBB_KEY=...
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import base64
import json
import asyncio
import time
import os
import random
from typing import Optional, Dict, Any


app = FastAPI(title="StyleLock AI", version="1.0")

# Allow all origins for MVP (lock down for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════
# ENV / API KEYS (DO NOT hardcode production keys)
# ═══════════════════════════════════════════════════════
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
LIGHTX_KEY = os.getenv("LIGHTX_API_KEY", "").strip()

# Keep model configurable so you can change without redeploying
# NOTE: Replace this default with a valid model for your Anthropic account if needed.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest").strip()

FREEIMAGE_KEY = os.getenv("FREEIMAGE_KEY", "6d207e02198a847aa98d0a2a901485a5").strip()
IMGBB_KEY = os.getenv("IMGBB_KEY", "d36eb6591370ae7f9089d85ff1e7237c").strip()

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
LIGHTX_HAIRSTYLE_URL = "https://api.lightxeditor.com/external/api/v1/hairstyle"
LIGHTX_ORDER_STATUS_URL = "https://api.lightxeditor.com/external/api/v1/order-status"

# ═══════════════════════════════════════════════════════
# Helper: robust HTTP POST with retries
# ═══════════════════════════════════════════════════════
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
    """
    Retries on common transient failures:
    - RemoteProtocolError (peer closed connection / incomplete chunked read)
    - timeouts
    - 429 and common 5xx

    Raises on final failure.
    """
    for attempt in range(1, tries + 1):
        try:
            async with httpx.AsyncClient(timeout=_timeout(timeout_s)) as client:
                resp = await client.post(url, headers=headers, data=data, json=json_body)

                # Retry on rate-limit or transient server issues
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
                print(f"⚠️ {label} failed (attempt {attempt}/{tries}): {repr(e)}")
                print(f"   Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                print(f"❌ {label} failed after {tries} attempts: {repr(e)}")
                raise

    raise Exception(f"{label} failed for unknown reasons")


# ═══════════════════════════════════════════════════════
# HERO LOOKS DATABASE (from your Workstream 1 spreadsheet)
# ═══════════════════════════════════════════════════════
HERO_LOOKS = [
    {
        "id": "T1-01", "tier": "CLEAN", "name": "Classic Scissor Taper",
        "vibe": "Corporate Polish", "maintenance": "Low", "daily_time": "2-3 min",
        "min_length_cm": 5, "min_density": "low", "receding_ok": True, "thinning_ok": True,
        "required_texture": None,  # works with all
        "face_scores": {"oval":3,"round":3,"square":3,"oblong":3,"diamond":3,"heart":3},
        "texture_scores": {"straight":3,"wavy":3,"curly":2,"coily":1},
        "lightx_prompt": "classic mens scissor tapered haircut, sides graduated short neat taper, 5-7cm textured top, side swept, clean natural hairline, professional corporate groomed look, barbershop quality",
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
        "lightx_prompt": "executive mens contour haircut, traditional grooming, side swept with volume at crown, conservative taper sides, professional refined look, barbershop quality",
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
        "lightx_prompt": "low mid taper fade haircut with textured messy top for men, point cut texture, 5-8cm on top, pushed forward, modern trendy casual style, clean edge up, Indian man",
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
        "lightx_prompt": "textured french crop haircut for men, mid to high fade on sides, choppy textured fringe falling on forehead, 3-5cm on top, modern casual trendy style, clean edge up, Indian man",
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
        "lightx_prompt": "korean two block cut haircut for men, disconnected sides guard 2, long curtain bangs 8-12cm on top, centre parting, clean sharp disconnect line, modern kpop style",
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
        "required_texture": "curly",  # only for curly/coily
        "face_scores": {"oval":3,"round":3,"square":3,"oblong":3,"diamond":3,"heart":3},
        "texture_scores": {"straight":0,"wavy":2,"curly":3,"coily":3},
        "lightx_prompt": "natural curly hair shaping for men, defined curls on top, low taper fade sides, curl enhancing cut, natural texture, medium length curls",
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
        "lightx_prompt": "modern quiff hairstyle with high skin fade for men, hair swept up and back from forehead, voluminous top 10cm, sharp razor temple edge up, bold statement masculine look",
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
        "lightx_prompt": "clean buzz cut for men guard 1 all over, razor sharp line up at temples and forehead, minimal hair bold masculine look, clean shaven sides, sharp edges",
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
        "lightx_prompt": "burst fade haircut for men, curved fade behind ear, textured top 4-8cm, sporty athletic style, clean symmetrical burst shape, modern masculine look",
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
        "lightx_prompt": "bleached platinum blonde short crop haircut for men, mid high fade sides natural dark, bright blonde textured top, editorial bold fashion look, contrast dark beard light hair",
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


# ═══════════════════════════════════════════════════════
# STEP 1: CLAUDE VISION — Analyze the selfie
# ═══════════════════════════════════════════════════════
async def analyze_with_claude(image_b64: str) -> dict:
    """Send selfie to Claude Vision, get structured hair/face analysis."""
    if not ANTHROPIC_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not set. Add it in Railway → Service → Variables.",
        )

    print("CALL: Claude analyze - starting")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
    }

    payload = {
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
    }

    # Claude can be slow / flaky. Give it more time + retries.
    resp = await post_with_retries(
        ANTHROPIC_URL,
        headers=headers,
        json_body=payload,
        timeout_s=90,
        tries=3,
        label="Claude analyze",
    )

    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []))
    clean = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as e:
        preview = clean[:600]
        print("❌ Claude returned non-JSON or malformed JSON. Preview:", preview)
        raise HTTPException(status_code=500, detail=f"Claude JSON parse error: {e}. Preview: {preview}")

    print("CALL: Claude analyze - done")
    return parsed


# ═══════════════════════════════════════════════════════
# STEP 2: SCORING ENGINE — Pick best 3 looks
# ═══════════════════════════════════════════════════════
def score_and_pick(analysis: dict) -> list:
    """Score all Hero Looks against detected attributes, return top 3."""
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
        # --- Hard filters ---
        if look["required_texture"]:
            if look["required_texture"] == "straight" and texture not in ("straight",):
                continue
            if look["required_texture"] == "curly" and texture not in ("curly", "coily"):
                continue

        tex_score = look["texture_scores"].get(texture, 0)
        if tex_score == 0:
            continue

        # --- Achievability score ---
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

        # Density (30 points)
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

        # Hairline (15 points)
        if is_receding and not look["receding_ok"]:
            hairline_pts = 0
        elif is_receding and look["receding_ok"]:
            hairline_pts = 15
        else:
            hairline_pts = 15

        # Face compatibility (15 points)
        face_pts = look["face_scores"].get(face, 1) / 3 * 15

        # Thinning bonus
        thin_bonus = 5 if is_thinning and look["thinning_ok"] else 0

        total = round(length_pts + density_pts + hairline_pts + face_pts + thin_bonus)

        # Growth estimate
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


# ═══════════════════════════════════════════════════════
# STEP 3A: Upload image to host (robust + retries)
# ═══════════════════════════════════════════════════════
async def upload_image_to_host(image_b64: str) -> str:
    """Upload base64 image to a free host and return URL."""
    print("CALL: Upload image host - starting")

    # Try freeimage.host
    try:
        resp = await post_with_retries(
            "https://freeimage.host/api/1/upload",
            data={
                "key": FREEIMAGE_KEY,
                "action": "upload",
                "source": image_b64,
                "format": "json"
            },
            timeout_s=45,
            tries=3,
            label="freeimage.host upload",
        )
        data = resp.json()
        url = (data.get("image", {}) or {}).get("url")
        if url:
            print(f"CALL: Upload image host - freeimage OK: {url}")
            return url
        else:
            print(f"⚠️ freeimage.host response missing url: {json.dumps(data)[:250]}")
    except Exception as e:
        print(f"⚠️ freeimage.host upload failed: {repr(e)}")

    # Fallback: imgbb
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
                print(f"CALL: Upload image host - imgbb OK: {url}")
                return url
        print(f"⚠️ imgbb response: {json.dumps(data)[:250]}")
    except Exception as e:
        print(f"⚠️ imgbb upload failed: {repr(e)}")

    raise HTTPException(status_code=502, detail="Image upload failed (freeimage + imgbb). Try again.")


# ═══════════════════════════════════════════════════════
# STEP 3B: LIGHTX — Generate hairstyle previews (robust)
# ═══════════════════════════════════════════════════════
async def generate_hairstyle(image_url: str, prompt: str, look_name: str = "") -> Optional[str]:
    """Call LightX API to generate one hairstyle preview."""
    if not LIGHTX_KEY:
        print(f"⚠️ LIGHTX_API_KEY missing. Skipping LightX generation for: {look_name}")
        return None

    print(f"CALL: LightX generate - starting: {look_name}")

    # Submit job (with retries)
    try:
        resp = await post_with_retries(
            LIGHTX_HAIRSTYLE_URL,
            headers={"Content-Type": "application/json", "x-api-key": LIGHTX_KEY},
            json_body={"imageUrl": image_url, "textPrompt": prompt},
            timeout_s=90,
            tries=3,
            label=f"LightX submit ({look_name})",
        )
        data = resp.json()
        print(f"CALL: LightX submit - {look_name} - resp: {json.dumps(data)[:300]}")
    except Exception as e:
        print(f"❌ LightX submit FAILED [{look_name}]: {repr(e)}")
        return None

    output = (data.get("body", {}) or {}).get("output") or data.get("output")
    if output:
        print(f"CALL: LightX generate - done (direct output): {look_name}")
        return output

    order_id = (data.get("body", {}) or {}).get("orderId") or data.get("orderId")
    if not order_id:
        print(f"❌ LightX submit missing orderId [{look_name}]. Full: {json.dumps(data)[:400]}")
        return None

    # Poll status (with retries)
    for attempt in range(40):  # ~2 minutes
        await asyncio.sleep(3)

        try:
            poll_resp = await post_with_retries(
                LIGHTX_ORDER_STATUS_URL,
                headers={"Content-Type": "application/json", "x-api-key": LIGHTX_KEY},
                json_body={"orderId": order_id},
                timeout_s=45,
                tries=3,
                label=f"LightX poll ({look_name})",
            )
            poll_data = poll_resp.json()
        except Exception as e:
            print(f"⚠️ LightX poll error [{look_name}] attempt {attempt+1}: {repr(e)}")
            continue

        status = (
            (poll_data.get("body", {}) or {}).get("status")
            or poll_data.get("status")
            or ""
        ).lower()

        output = (
            (poll_data.get("body", {}) or {}).get("output")
            or poll_data.get("output")
            or None
        )

        print(f"CALL: LightX poll {attempt+1}/40 - {look_name} - status='{status}'")

        if output:
            print(f"CALL: LightX generate - done: {look_name}")
            return output

        if status in ("failed", "error", "cancelled"):
            print(f"❌ LightX failed [{look_name}] resp: {json.dumps(poll_data)[:250]}")
            return None

    print(f"❌ LightX timeout after polls [{look_name}]")
    return None


# ═══════════════════════════════════════════════════════
# MAIN ENDPOINT — The one API call the app makes
# ═══════════════════════════════════════════════════════
@app.post("/api/consult")
async def consult(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        # Read and encode image
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        image_b64 = base64.b64encode(contents).decode("utf-8")

        # ── STEP 1: Claude Vision Analysis ──
        print("STEP 1: Analyzing with Claude Vision...")
        analysis = await analyze_with_claude(image_b64)
        print("STEP 1: Done.")

        # ── STEP 2: Score and pick 3 looks ──
        print("STEP 2: Scoring looks...")
        picks = score_and_pick(analysis)
        if not picks:
            raise HTTPException(status_code=500, detail="Scoring returned no picks for this analysis")
        print(f"  Picked: {[p['name'] for p in picks]}")

        # ── STEP 3: Upload selfie for LightX ──
        print("STEP 3: Uploading image for LightX...")
        image_url = await upload_image_to_host(image_b64)
        print(f"  Uploaded URL: {image_url}")

        # ── STEP 4: Generate 3 hairstyle previews in PARALLEL ──
        print("STEP 4: Generating 3 previews (parallel)...")
        generation_tasks = [
            generate_hairstyle(image_url, pick["lightx_prompt"], pick["name"])
            for pick in picks
        ]

        try:
            preview_urls = await asyncio.wait_for(
                asyncio.gather(*generation_tasks, return_exceptions=True),
                timeout=180  # 3 minute max
            )
            preview_urls = [url if isinstance(url, str) else None for url in preview_urls]
        except asyncio.TimeoutError:
            print("⚠️ Generation timed out after 3 minutes")
            preview_urls = [None] * len(picks)

        # ── BUILD RESPONSE ──
        recommendations = []
        for pick, preview_url in zip(picks, preview_urls):
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
                "preview_url": preview_url,
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
        # This gives your frontend a readable error instead of a vague 500
        print("🔥 /api/consult crashed:", repr(e))
        raise HTTPException(status_code=500, detail=f"Backend error: {type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════
@app.get("/")
async def health():
    return {"status": "ok", "service": "StyleLock AI", "version": "1.0"}


@app.get("/api/looks")
async def list_looks():
    """Return all available Hero Looks (for debugging/admin)."""
    return {"looks": [{
        "id": l["id"], "tier": l["tier"], "name": l["name"],
        "vibe": l["vibe"], "min_length_cm": l["min_length_cm"],
        "min_density": l["min_density"],
    } for l in HERO_LOOKS]}


# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
