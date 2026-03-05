"""
StyleLock AI — Backend Server
==============================
This is the brain of the app. One endpoint receives a selfie,
orchestrates Claude Vision + Scoring Engine + LightX, and returns
3 hairstyle previews with Cut Cards.

DEPLOY: Railway, Render, or any Python hosting
SETUP:
  pip install fastapi uvicorn httpx python-multipart

RUN:
  uvicorn server:app --host 0.0.0.0 --port 8000

ENV VARS NEEDED:
  ANTHROPIC_API_KEY=sk-ant-...
  LIGHTX_API_KEY=622e21fee31e...
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import base64
import json
import asyncio
import time
import os

app = FastAPI(title="StyleLock AI", version="1.0")

# Allow all origins for MVP (lock down for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════
# API KEYS (set these as environment variables)
# ═══════════════════════════════════════════════════════
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-key")
LIGHTX_KEY = os.getenv("LIGHTX_API_KEY", "622e21fee31e4a4988469f199e87c673_5d0ce065974c49798b676587688da793_andoraitools")


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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
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
        )
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)


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
        # Texture requirement
        if look["required_texture"]:
            if look["required_texture"] == "straight" and texture not in ("straight",):
                continue
            if look["required_texture"] == "curly" and texture not in ("curly", "coily"):
                continue
        
        # Texture score = 0 means blocked
        tex_score = look["texture_scores"].get(texture, 0)
        if tex_score == 0:
            continue
        
        # --- Achievability score ---
        # Length (40 points)
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
                continue  # blocked — thin hair can't do high-density looks
        else:
            density_pts = 20
        
        # Hairline (15 points)
        if is_receding and not look["receding_ok"]:
            hairline_pts = 0
        elif is_receding and look["receding_ok"]:
            hairline_pts = 15  # bonus — designed for this
        else:
            hairline_pts = 15
        
        # Face compatibility (15 points)
        face_pts = look["face_scores"].get(face, 1) / 3 * 15
        
        # Thinning bonus
        thin_bonus = 5 if is_thinning and look["thinning_ok"] else 0
        
        total = round(length_pts + density_pts + hairline_pts + face_pts + thin_bonus)
        
        # Growth estimate
        if achievability == "grow" or achievability == "dream":
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
    
    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    # Pick top 1 per tier, prioritize "ready" looks
    tiers = ["CLEAN", "TRENDING", "BOLD"]
    picks = []
    for tier in tiers:
        tier_looks = [l for l in scored if l["tier"] == tier]
        # Prefer "ready" looks
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
# STEP 3: LIGHTX — Generate hairstyle previews
# ═══════════════════════════════════════════════════════
async def generate_hairstyle(image_url: str, prompt: str, look_name: str = "") -> str | None:
    """Call LightX API to generate one hairstyle preview."""
    print(f"    [{look_name}] Calling LightX API...")
    async with httpx.AsyncClient(timeout=120) as client:
        # Submit generation
        try:
            resp = await client.post(
                "https://api.lightxeditor.com/external/api/v1/hairstyle",
                headers={"Content-Type": "application/json", "x-api-key": LIGHTX_KEY},
                json={"imageUrl": image_url, "textPrompt": prompt}
            )
            data = resp.json()
            print(f"    [{look_name}] Submit response: {json.dumps(data)[:300]}")
        except Exception as e:
            print(f"    [{look_name}] Submit FAILED: {e}")
            return None
        
        # Check for direct output (some API versions return immediately)
        output = data.get("body", {}).get("output")
        if output:
            print(f"    [{look_name}] Got direct output!")
            return output
        
        # Also check top-level output
        if data.get("output"):
            print(f"    [{look_name}] Got top-level output!")
            return data["output"]
        
        # Get order ID and poll
        order_id = data.get("body", {}).get("orderId") or data.get("orderId")
        if not order_id:
            print(f"    [{look_name}] ERROR: No orderId in response. Full: {json.dumps(data)}")
            return None
        
        print(f"    [{look_name}] Order ID: {order_id} — polling...")
        
        # Poll for result
        for attempt in range(40):  # up to 2 minutes
            await asyncio.sleep(3)
            try:
                poll = await client.post(
                    "https://api.lightxeditor.com/external/api/v1/order-status",
                    headers={"Content-Type": "application/json", "x-api-key": LIGHTX_KEY},
                    json={"orderId": order_id}
                )
                poll_data = poll.json()
                
                # Try multiple possible status locations
                status = (
                    poll_data.get("body", {}).get("status") or
                    poll_data.get("status") or
                    ""
                ).lower()
                
                print(f"    [{look_name}] Poll #{attempt+1}: status='{status}'")
                
                # Check for output in multiple possible locations
                output = (
                    poll_data.get("body", {}).get("output") or
                    poll_data.get("output") or
                    None
                )
                
                if output:
                    print(f"    [{look_name}] ✅ Got output URL!")
                    return output
                
                # Check if completed even without explicit status match
                if status in ("active", "completed", "success", "done", "finished"):
                    if output:
                        return output
                    # Sometimes output is nested differently
                    body = poll_data.get("body", {})
                    for key in ["output", "outputUrl", "result", "image", "imageUrl", "url"]:
                        if body.get(key):
                            print(f"    [{look_name}] ✅ Found output in body.{key}")
                            return body[key]
                
                if status in ("failed", "error", "cancelled"):
                    print(f"    [{look_name}] ❌ Generation failed. Response: {json.dumps(poll_data)[:200]}")
                    return None
                    
            except Exception as e:
                print(f"    [{look_name}] Poll error: {e}")
                continue
        
        print(f"    [{look_name}] ❌ Timeout after 40 polls")
        return None


async def upload_image_to_host(image_b64: str) -> str:
    """Upload base64 image to a free host and return URL."""
    print("  Uploading to freeimage.host...")
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": "6d207e02198a847aa98d0a2a901485a5",
                    "action": "upload",
                    "source": image_b64,
                    "format": "json"
                }
            )
            data = resp.json()
            if data.get("status_code") == 200 or data.get("image", {}).get("url"):
                url = data["image"]["url"]
                print(f"  ✅ Uploaded to freeimage.host: {url}")
                return url
            else:
                print(f"  ⚠️ freeimage.host response: {json.dumps(data)[:200]}")
        except Exception as e:
            print(f"  ⚠️ freeimage.host failed: {e}")
        
        # Fallback: try imgbb
        print("  Trying imgbb fallback...")
        try:
            resp = await client.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": "d36eb6591370ae7f9089d85ff1e7237c",  # free public key
                    "image": image_b64,
                    "expiration": 600,
                }
            )
            data = resp.json()
            if data.get("success"):
                url = data["data"]["url"]
                print(f"  ✅ Uploaded to imgbb: {url}")
                return url
            else:
                print(f"  ⚠️ imgbb response: {json.dumps(data)[:200]}")
        except Exception as e:
            print(f"  ⚠️ imgbb failed: {e}")
        
        raise Exception("Could not upload image to any host")


# ═══════════════════════════════════════════════════════
# MAIN ENDPOINT — The one API call the app makes
# ═══════════════════════════════════════════════════════
@app.post("/api/consult")
async def consult(file: UploadFile = File(...)):
    """
    THE MAIN ENDPOINT.
    
    Input: A selfie (JPEG/PNG)
    Output: {
        "analysis": { face/hair attributes from Claude Vision },
        "recommendations": [
            {
                "look": { name, tier, vibe, card, ... },
                "score": 87,
                "achievability": "ready" | "grow" | "dream",
                "growth_weeks": 0,
                "preview_url": "https://..." (AI-generated image of user with this hairstyle)
            },
            ... (3 total)
        ]
    }
    """
    start_time = time.time()
    
    # Read and encode image
    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")
    
    # ── STEP 1: Claude Vision Analysis ──
    print("Step 1: Analyzing with Claude Vision...")
    analysis = await analyze_with_claude(image_b64)
    print(f"  Analysis: {json.dumps(analysis, indent=2)}")
    
    # ── STEP 2: Score and pick 3 looks ──
    print("Step 2: Scoring looks...")
    picks = score_and_pick(analysis)
    print(f"  Picked: {[p['name'] for p in picks]}")
    
    # ── STEP 3: Upload selfie for LightX ──
    print("Step 3: Uploading image...")
    image_url = await upload_image_to_host(image_b64)
    print(f"  URL: {image_url}")
    
    # ── STEP 4: Generate 3 hairstyle previews in PARALLEL ──
    print("Step 4: Generating 3 previews (parallel)...")
    generation_tasks = [
        generate_hairstyle(image_url, pick["lightx_prompt"], pick["name"])
        for pick in picks
    ]
    
    try:
        preview_urls = await asyncio.wait_for(
            asyncio.gather(*generation_tasks, return_exceptions=True),
            timeout=180  # 3 minute max
        )
        # Convert exceptions to None
        preview_urls = [
            url if isinstance(url, str) else None
            for url in preview_urls
        ]
    except asyncio.TimeoutError:
        print("  ⚠️ Generation timed out after 3 minutes")
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
    print(f"Done in {elapsed}s")
    
    return JSONResponse({
        "success": True,
        "elapsed_seconds": elapsed,
        "analysis": analysis,
        "recommendations": recommendations,
    })


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
