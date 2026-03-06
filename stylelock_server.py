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
    print(f"  Using API key: {ANTHROPIC_KEY[:12]}...{ANTHROPIC_KEY[-4:]}")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-5-20250929",
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
            
            print(f"  Claude API status: {resp.status_code}")
            
            if resp.status_code != 200:
                error_body = resp.text
                print(f"  Claude API error: {error_body[:300]}")
                raise Exception(f"Claude API returned {resp.status_code}: {error_body[:200]}")
            
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            print(f"  Claude response: {text[:200]}")
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
            
        except json.JSONDecodeError as e:
            print(f"  Failed to parse Claude response as JSON: {e}")
            raise Exception(f"Claude returned non-JSON response: {text[:100]}")
        except httpx.HTTPStatusError as e:
            print(f"  HTTP error from Claude: {e}")
            raise


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
    """THE MAIN ENDPOINT."""
    start_time = time.time()
    
    try:
        # Read and encode image
        contents = await file.read()
        image_b64 = base64.b64encode(contents).decode("utf-8")
        print(f"Image received: {len(contents)} bytes")
        
        # ── STEP 1: Claude Vision Analysis ──
        print("Step 1: Analyzing with Claude Vision...")
        try:
            analysis = await analyze_with_claude(image_b64)
            print(f"  Analysis: {json.dumps(analysis, indent=2)}")
        except Exception as e:
            print(f"  ❌ Claude Vision failed: {e}")
            return JSONResponse(status_code=500, content={
                "success": False,
                "error": f"Claude Vision analysis failed: {str(e)}",
                "step": "analysis"
            })
        
        # ── STEP 2: Score and pick 3 looks ──
        print("Step 2: Scoring looks...")
        picks = score_and_pick(analysis)
        print(f"  Picked: {[p['name'] for p in picks]}")
        
        if not picks:
            return JSONResponse(content={
                "success": False,
                "error": "No matching looks found for your hair profile",
                "analysis": analysis,
                "step": "scoring"
            })
        
        # ── STEP 3: Upload selfie for LightX ──
        print("Step 3: Uploading image...")
        try:
            image_url = await upload_image_to_host(image_b64)
            print(f"  URL: {image_url}")
        except Exception as e:
            print(f"  ❌ Image upload failed: {e}")
            return JSONResponse(status_code=500, content={
                "success": False,
                "error": f"Image upload failed: {str(e)}",
                "analysis": analysis,
                "step": "upload"
            })
        
        # ── STEP 4: Generate 3 hairstyle previews in PARALLEL ──
        print("Step 4: Generating 3 previews (parallel)...")
        generation_tasks = [
            generate_hairstyle(image_url, pick["lightx_prompt"], pick["name"])
            for pick in picks
        ]
        
        try:
            preview_urls = await asyncio.wait_for(
                asyncio.gather(*generation_tasks, return_exceptions=True),
                timeout=180
            )
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
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": f"Backend error: {type(e).__name__}: {str(e)}",
        })


# ═══════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════
@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "StyleLock AI",
        "version": "1.1",
        "anthropic_key_set": ANTHROPIC_KEY != "your-anthropic-key" and len(ANTHROPIC_KEY) > 10,
        "anthropic_key_preview": f"{ANTHROPIC_KEY[:8]}...{ANTHROPIC_KEY[-4:]}" if len(ANTHROPIC_KEY) > 12 else "NOT SET",
        "lightx_key_set": len(LIGHTX_KEY) > 10,
    }


@app.get("/api/debug")
async def debug():
    """Debug endpoint — check if all configs are correct."""
    import httpx
    
    results = {"anthropic": "untested", "lightx": "untested", "image_host": "untested"}
    
    # Test Anthropic
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Say hi"}]
                }
            )
            if resp.status_code == 200:
                results["anthropic"] = "✅ Working"
            else:
                results["anthropic"] = f"❌ Status {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        results["anthropic"] = f"❌ Error: {str(e)[:100]}"
    
    # Test LightX
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.lightxeditor.com/external/api/v1/hairstyle",
                headers={"Content-Type": "application/json", "x-api-key": LIGHTX_KEY},
                json={"imageUrl": "https://test.com/fake.jpg", "textPrompt": "test"}
            )
            if resp.status_code in (200, 400, 422):
                results["lightx"] = f"✅ Reachable (status {resp.status_code})"
            else:
                results["lightx"] = f"⚠️ Status {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        results["lightx"] = f"❌ Error: {str(e)[:100]}"
    
    return {
        "config": {
            "anthropic_key": f"{ANTHROPIC_KEY[:8]}...{ANTHROPIC_KEY[-4:]}" if len(ANTHROPIC_KEY) > 12 else "NOT SET",
            "lightx_key": f"{LIGHTX_KEY[:8]}...{LIGHTX_KEY[-4:]}" if len(LIGHTX_KEY) > 12 else "NOT SET",
            "model": "claude-sonnet-4-5-20250929",
        },
        "tests": results,
    }


# ═══════════════════════════════════════════════════════
# FRONTEND — Served from the same server (no CORS issues)
# ═══════════════════════════════════════════════════════
from fastapi.responses import HTMLResponse

@app.get("/app", response_class=HTMLResponse)
async def frontend():
    """Serve the StyleLock AI frontend."""
    return FRONTEND_HTML


FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>StyleLock AI</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root { --bg:#0A0A0F; --card:rgba(255,255,255,0.03); --border:rgba(255,255,255,0.08); --pink:#FF3CAC; --cyan:#00E5FF; --yellow:#FFE600; --green:#00E676; --red:#FF4444; --orange:#FFB800; --text:#fff; --muted:rgba(255,255,255,0.45); --dim:rgba(255,255,255,0.25); }
  *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
  body{background:#050508;font-family:'Outfit',sans-serif;color:var(--text);min-height:100vh;display:flex;justify-content:center}
  input[type="file"]{display:none} ::-webkit-scrollbar{width:0}
  .app{width:100%;max-width:420px;min-height:100vh;background:var(--bg);position:relative;overflow-x:hidden}
  .screen{width:100%;min-height:100vh;display:flex;flex-direction:column;animation:fadeIn .3s ease}
  .screen.hidden{display:none}
  .tag{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:3px;font-weight:500}
  .btn{width:100%;padding:18px 0;border-radius:16px;border:none;font-family:'Outfit';font-size:16px;font-weight:700;cursor:pointer;position:relative;overflow:hidden}
  .btn::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);background-size:200% 100%;animation:shimmer 2s infinite}
  .btn-pink{background:linear-gradient(135deg,var(--pink),#784BA0,#2B86C5);color:white;box-shadow:0 0 28px rgba(255,60,172,.3)}
  .badge{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:8px;font-size:11px}
  .badge-ready{background:rgba(0,230,118,.1);color:var(--green)} .badge-grow{background:rgba(255,184,0,.1);color:var(--orange)} .badge-dream{background:rgba(255,68,68,.1);color:var(--red)}
  @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  @keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
  @keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
  @keyframes slideUp{0%{opacity:0;transform:translateY(20px)}100%{opacity:1;transform:translateY(0)}}
  @keyframes orbitSpin{0%{transform:translate(-50%,-50%) rotate(0)}100%{transform:translate(-50%,-50%) rotate(360deg)}}
  @keyframes blob{0%,100%{border-radius:60% 40% 30% 70%/60% 30% 70% 40%}50%{border-radius:30% 60% 70% 40%/50% 60% 30% 60%}}
  @keyframes ringPulse{0%{transform:translate(-50%,-50%) scale(1);opacity:.3}100%{transform:translate(-50%,-50%) scale(2);opacity:0}}
</style>
</head>
<body>
<div class="app" id="app">

  <!-- INTRO -->
  <div class="screen" id="screen-intro" style="padding:0 28px;position:relative;overflow:hidden">
    <div style="position:absolute;top:-60px;right:-60px;width:200px;height:200px;border-radius:50%;background:radial-gradient(circle,rgba(255,60,172,.2),transparent 70%);filter:blur(40px);animation:blob 6s ease-in-out infinite"></div>
    <div style="position:absolute;bottom:-40px;left:-40px;width:160px;height:160px;border-radius:50%;background:radial-gradient(circle,rgba(0,229,255,.15),transparent 70%);filter:blur(40px);animation:blob 8s ease-in-out infinite reverse"></div>
    <div style="flex:1;display:flex;flex-direction:column;justify-content:center;z-index:1">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px">
        <span style="font-size:36px">✂️</span>
        <div>
          <div style="font-family:'DM Mono',monospace;font-size:22px;font-weight:700;background:linear-gradient(90deg,var(--pink),#784BA0,var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent">STYLELOCK</div>
          <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--pink);letter-spacing:4px">AI HAIR TRY-ON</div>
        </div>
      </div>
      <h1 style="font-size:30px;font-weight:900;line-height:1.2;margin-bottom:14px">See <span style="background:linear-gradient(90deg,var(--pink),var(--yellow));-webkit-background-clip:text;-webkit-text-fill-color:transparent">yourself</span> with<br>3 new looks</h1>
      <p style="font-size:15px;color:var(--muted);line-height:1.7;margin-bottom:32px">One selfie. AI analyzes your face and hair. Generates photorealistic previews of YOU with 3 personalized hairstyles.</p>
      <div id="intro-steps"></div>
    </div>
    <div style="padding-bottom:40px;z-index:1">
      <input type="file" id="file-input" accept="image/*" capture="user">
      <button class="btn btn-pink" onclick="document.getElementById('file-input').click()">📸 TAKE A SELFIE</button>
      <p style="font-size:11px;color:var(--dim);text-align:center;margin-top:8px">Photos stay on your device until you hit analyze</p>
    </div>
  </div>

  <!-- PREVIEW -->
  <div class="screen hidden" id="screen-preview" style="padding:44px 24px 36px">
    <div class="tag" style="color:var(--cyan);margin-bottom:8px">PREVIEW</div>
    <h2 style="font-size:22px;font-weight:800;margin-bottom:4px">Looking good! 📸</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:16px">This selfie will be sent for AI analysis and hairstyle generation.</p>
    <div style="flex:1;border-radius:20px;overflow:hidden;border:2px solid rgba(0,229,255,.3);margin-bottom:16px">
      <img id="preview-img" style="width:100%;height:100%;object-fit:cover" alt="Your selfie">
    </div>
    <div style="display:flex;gap:12px">
      <button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:14px" onclick="resetToIntro()">🔄 Retake</button>
      <button class="btn btn-pink" style="flex:2;font-size:14px" onclick="startConsult()">✨ GENERATE 3 LOOKS</button>
    </div>
  </div>

  <!-- GENERATING -->
  <div class="screen hidden" id="screen-generating" style="align-items:center;justify-content:center;padding:32px;position:relative;overflow:hidden;background:linear-gradient(135deg,#0A0A0F,#1A0A2E)">
    <div style="position:absolute;top:50%;left:50%;width:280px;height:280px;border-radius:50%;border:1px solid rgba(255,60,172,.12);animation:orbitSpin 10s linear infinite"><div style="position:absolute;top:0;left:50%;width:8px;height:8px;border-radius:50%;background:var(--pink);transform:translateX(-50%);box-shadow:0 0 20px var(--pink)"></div></div>
    <div style="position:absolute;top:50%;left:50%;width:180px;height:180px;border-radius:50%;border:1px solid rgba(0,229,255,.1);animation:orbitSpin 7s linear infinite reverse"><div style="position:absolute;top:0;left:50%;width:6px;height:6px;border-radius:50%;background:var(--cyan);transform:translateX(-50%);box-shadow:0 0 15px var(--cyan)"></div></div>
    <div style="position:absolute;top:50%;left:50%;width:100px;height:100px;border-radius:50%;border:2px solid rgba(255,60,172,.15);animation:ringPulse 2s ease-out infinite"></div>
    <div id="gen-emoji" style="font-size:48px;margin-bottom:20px;animation:float 2s ease-in-out infinite;z-index:1">🧠</div>
    <p id="gen-step" style="font-family:'DM Mono',monospace;font-size:15px;z-index:1;text-align:center">Connecting to StyleLock AI...</p>
    <p id="gen-detail" style="font-size:13px;color:var(--muted);z-index:1;text-align:center;margin-top:6px">This takes 20-35 seconds</p>
    <div style="display:flex;gap:8px;margin-top:24px;z-index:1" id="gen-progress">
      <div class="gen-bar" data-step="analysis"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--pink);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Analysis</span></div>
      <div class="gen-bar" data-step="scoring"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--cyan);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Scoring</span></div>
      <div class="gen-bar" data-step="generating"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--yellow);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Try-On</span></div>
    </div>
  </div>

  <!-- RESULTS -->
  <div class="screen hidden" id="screen-results" style="padding:44px 24px 32px;overflow:auto">
    <div style="margin-bottom:20px">
      <div class="tag" style="color:var(--pink);margin-bottom:8px">YOUR 3 LOOKS</div>
      <h2 style="font-size:24px;font-weight:800;margin-bottom:4px">Here's you, 3 ways ✨</h2>
      <p style="font-size:13px;color:var(--muted)">AI-generated previews based on your face and hair analysis. Tap any to see the full Cut Card.</p>
    </div>
    <div id="analysis-summary" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px"></div>
    <div id="results-cards" style="display:flex;flex-direction:column;gap:16px"></div>
    <button class="btn" style="background:transparent;color:var(--dim);font-size:13px;margin-top:20px;border:none" onclick="resetToIntro()">📸 Take a new selfie</button>
  </div>

  <!-- DETAIL -->
  <div class="screen hidden" id="screen-detail" style="overflow:auto">
    <div id="detail-content"></div>
  </div>

</div>

<script>
// API is on the same server — no CORS issues
const API_BASE = "";

let currentFile = null;
let currentPhotoUrl = null;
let consultResult = null;

// Intro steps
const stepsEl = document.getElementById("intro-steps");
[{e:"📸",t:"Take one front selfie"},{e:"🧠",t:"AI analyzes your face shape, hair & density"},{e:"✨",t:"See yourself with 3 AI-generated hairstyles"},{e:"🔒",t:"Lock a look, get a barber-ready Cut Card"}].forEach(({e,t},i)=>{
  const d=document.createElement("div");
  d.style.cssText=`display:flex;align-items:center;gap:12px;margin-bottom:11px;animation:slideUp .4s ease-out ${.1+i*.06}s both`;
  d.innerHTML=`<span style="font-size:16px;width:28px;text-align:center">${e}</span><span style="font-size:14px;color:rgba(255,255,255,.55)">${t}</span>`;
  stepsEl.appendChild(d);
});

function showScreen(id){document.querySelectorAll(".screen").forEach(s=>s.classList.add("hidden"));document.getElementById("screen-"+id).classList.remove("hidden");window.scrollTo(0,0)}
function resetToIntro(){currentFile=null;currentPhotoUrl=null;consultResult=null;document.getElementById("file-input").value="";showScreen("intro")}

document.getElementById("file-input").addEventListener("change",function(e){
  const file=e.target.files?.[0];if(!file)return;
  currentFile=file;
  const reader=new FileReader();
  reader.onload=(ev)=>{currentPhotoUrl=ev.target.result;document.getElementById("preview-img").src=currentPhotoUrl;showScreen("preview")};
  reader.readAsDataURL(file);
});

function updateProgress(step,percent,emoji,text,detail){
  if(emoji)document.getElementById("gen-emoji").textContent=emoji;
  if(text)document.getElementById("gen-step").textContent=text;
  if(detail)document.getElementById("gen-detail").textContent=detail;
  const bars=document.querySelectorAll(".gen-bar");
  const steps=["analysis","scoring","generating"];
  const si=steps.indexOf(step);
  bars.forEach((bar,i)=>{const fill=bar.querySelector(".gen-fill");if(i<si)fill.style.width="100%";else if(i===si)fill.style.width=percent+"%"});
}

async function startConsult(){
  showScreen("generating");
  updateProgress("analysis",30,"🧠","Analyzing your face & hair...","Claude Vision AI is reading your features");

  try{
    const formData=new FormData();
    formData.append("file",currentFile);

    const progressSteps=[
      {delay:3000,fn:()=>updateProgress("analysis",100,"🧠","Face analyzed!","Scoring looks...")},
      {delay:5000,fn:()=>updateProgress("scoring",100,"🎯","3 looks selected!","Generating AI previews...")},
      {delay:7000,fn:()=>updateProgress("generating",20,"✨","Creating your previews...","LightX AI is generating 3 hairstyles on your face")},
      {delay:15000,fn:()=>updateProgress("generating",40,"✨","Still working...","AI image generation takes 15-45 seconds per look")},
      {delay:30000,fn:()=>updateProgress("generating",60,"✨","Almost there...","Waiting for LightX to finish rendering")},
      {delay:60000,fn:()=>updateProgress("generating",75,"⏳","Taking longer than usual...","LightX is still processing — hang tight")},
      {delay:90000,fn:()=>updateProgress("generating",80,"⏳","Very slow today...","Still waiting for LightX — this sometimes happens")},
    ];
    const timers=progressSteps.map(({delay,fn})=>setTimeout(fn,delay));

    const controller=new AbortController();
    const timeoutId=setTimeout(()=>controller.abort(),180000);

    console.log("Sending request to",API_BASE+"/api/consult");
    const response=await fetch(API_BASE+"/api/consult",{method:"POST",body:formData,signal:controller.signal});

    clearTimeout(timeoutId);
    timers.forEach(t=>clearTimeout(t));

    console.log("Response status:",response.status);
    const responseText=await response.text();
    console.log("Response body (first 500):",responseText.substring(0,500));

    if(!response.ok)throw new Error("Server error "+response.status+": "+responseText.substring(0,200));

    consultResult=JSON.parse(responseText);
    if(!consultResult.success)throw new Error(consultResult.error||"Consult failed");

    updateProgress("generating",100,"🎉","Done!","Loading your looks...");
    setTimeout(()=>renderResults(),500);

  }catch(err){
    console.error("Consult error:",err);
    const isTimeout=err.name==="AbortError";
    document.getElementById("gen-step").textContent=isTimeout?"⏳ Timed out":"⚠️ Something went wrong";
    document.getElementById("gen-detail").innerHTML=`<span style="color:var(--red);font-size:13px">${isTimeout?"Server took too long. LightX may be slow.":err.message}</span><br><div style="display:flex;gap:10px;justify-content:center;margin-top:16px"><button class="btn" style="padding:12px 20px;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:13px;width:auto" onclick="resetToIntro()">← Start over</button><button class="btn" style="padding:12px 20px;background:linear-gradient(135deg,var(--pink),#784BA0);color:white;font-size:13px;width:auto" onclick="startConsult()">🔄 Retry</button></div>`;
  }
}

function renderResults(){
  const{analysis,recommendations}=consultResult;
  const summaryEl=document.getElementById("analysis-summary");
  summaryEl.innerHTML="";
  [{l:"◆",v:analysis.faceShape},{l:"〰",v:analysis.hairTexture},{l:"▓",v:analysis.density},{l:"📏",v:analysis.estimatedTopLengthCm+"cm"},{l:"⌒",v:analysis.hairlineState}].forEach(({l,v})=>{
    summaryEl.innerHTML+=`<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:5px 10px;font-size:11px;color:var(--muted);text-transform:capitalize">${l} ${v}</div>`;
  });
  const cardsEl=document.getElementById("results-cards");
  cardsEl.innerHTML="";
  const tc_map={CLEAN:"var(--cyan)",TRENDING:"var(--pink)",BOLD:"var(--yellow)"};
  const te_map={CLEAN:"💼",TRENDING:"🔥",BOLD:"⚡"};
  recommendations.forEach((rec,i)=>{
    const tc=tc_map[rec.look.tier]||"var(--pink)";
    const te=te_map[rec.look.tier]||"✨";
    const hasImg=rec.preview_url&&rec.preview_url!=="null"&&rec.preview_url!==null;
    const ab=rec.achievability==="ready"?`<span class="badge badge-ready">🟢 Ready now</span>`:rec.achievability==="grow"?`<span class="badge badge-grow">🟡 ~${rec.growth_weeks}wk growth</span>`:`<span class="badge badge-dream">🔴 ~${rec.growth_weeks}wk</span>`;
    const card=document.createElement("div");
    card.style.cssText=`border-radius:20px;overflow:hidden;border:1px solid ${tc}30;cursor:pointer;animation:slideUp .4s ease-out ${i*.1}s both`;
    card.onclick=()=>showDetail(rec,tc,te);
    card.innerHTML=`<div style="width:100%;height:300px;background:${tc}08;position:relative">${hasImg?`<img src="${rec.preview_url}" style="width:100%;height:100%;object-fit:cover" alt="${rec.look.name}">`:`<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center"><span style="font-size:48px;margin-bottom:8px">${te}</span><span style="font-size:12px;color:var(--dim)">Preview unavailable</span></div>`}<div style="position:absolute;top:12px;left:12px;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);border-radius:10px;padding:6px 12px;display:flex;align-items:center;gap:6px"><span style="font-size:14px">${te}</span><span style="font-family:'DM Mono',monospace;font-size:10px;color:${tc}">${rec.look.tier}</span></div><div style="position:absolute;top:12px;right:12px;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);border-radius:10px;padding:6px 12px"><span style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;color:${tc}">${rec.score}</span><span style="font-size:10px;color:${tc}">%</span></div><div style="position:absolute;bottom:0;left:0;right:0;height:60px;background:linear-gradient(transparent,var(--bg))"></div></div><div style="padding:14px 18px"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px"><h3 style="font-size:18px;font-weight:800">${rec.look.name}</h3>${ab}</div><div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><span style="font-size:12px;color:var(--muted)">${rec.look.vibe}</span><span style="font-size:10px;color:var(--dim)">•</span><span style="font-size:12px;color:var(--muted)">🔧 ${rec.look.maintenance}</span><span style="font-size:10px;color:var(--dim)">•</span><span style="font-size:12px;color:var(--muted)">⏱ ${rec.look.daily_time}</span></div><div style="width:100%;padding:10px 0;border-radius:10px;border:1px solid ${tc}40;background:${tc}08;text-align:center;font-size:13px;font-weight:700;color:${tc}">VIEW CUT CARD →</div></div>`;
    cardsEl.appendChild(card);
  });
  showScreen("results");
}

function showDetail(rec,tc,te){
  const hasImg=rec.preview_url&&rec.preview_url!=="null"&&rec.preview_url!==null;
  const card=rec.look.card;
  const at=rec.achievability==="ready"?"Your hair can achieve this today":rec.achievability==="grow"?"Needs ~"+rec.growth_gap_cm+"cm more growth (~"+rec.growth_weeks+" weeks)":"Aspirational — needs significant growth";
  const ac=rec.achievability==="ready"?"var(--green)":rec.achievability==="grow"?"var(--orange)":"var(--red)";
  const ab=rec.achievability==="ready"?"🟢":rec.achievability==="grow"?"🟡":"🔴";
  const rows=[{i:"💇",l:"FADE / TAPER",v:card.fade},{i:"📏",l:"TOP LENGTH",v:card.top},{i:"↗️",l:"FRINGE",v:card.fringe},{i:"✨",l:"STYLING",v:card.styling},{i:"🧴",l:"PRODUCTS",v:card.products},{i:"🧔",l:"BEARD",v:card.beard}];
  document.getElementById("detail-content").innerHTML=`<div style="width:100%;height:340px;position:relative;flex-shrink:0">${hasImg?`<img src="${rec.preview_url}" style="width:100%;height:100%;object-fit:cover">`:`<div style="width:100%;height:100%;background:${tc}08;display:flex;align-items:center;justify-content:center"><span style="font-size:64px">${te}</span></div>`}<button onclick="showScreen('results')" style="position:absolute;top:44px;left:16px;background:rgba(0,0,0,.6);backdrop-filter:blur(10px);border:none;border-radius:10px;padding:8px 14px;color:white;font-family:'Outfit';font-size:12px;font-weight:600;cursor:pointer">← BACK</button><div style="position:absolute;bottom:0;left:0;right:0;height:80px;background:linear-gradient(transparent,var(--bg))"></div></div><div style="padding:0 24px 20px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><span class="tag" style="color:${tc}">${rec.look.tier}</span><span style="color:var(--dim)">·</span><span style="font-size:12px;color:var(--muted)">${rec.look.vibe}</span></div><h2 style="font-size:26px;font-weight:800;margin-bottom:6px">${rec.look.name} ${te}</h2><div style="background:${ac}10;border:1px solid ${ac}30;border-radius:12px;padding:10px 14px;margin-bottom:16px;display:flex;align-items:center;gap:8px"><span style="font-size:16px">${ab}</span><span style="font-size:13px;color:${ac};font-weight:600">${at}</span></div><div style="display:flex;gap:8px;margin-bottom:16px"><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">🔧 ${rec.look.maintenance}</div><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">⏱ ${rec.look.daily_time}</div><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">Match: ${rec.score}%</div></div><div class="tag" style="color:${tc};margin-bottom:10px">✂ CUT CARD</div><div style="background:var(--card);border:1px solid ${tc}18;border-radius:18px;padding:6px 18px 18px">${rows.map(({i:ic,l,v},idx)=>`<div style="display:flex;gap:12px;padding:12px 0;border-bottom:${idx<rows.length-1?'1px solid rgba(255,255,255,.05)':'none'}"><div style="width:34px;height:34px;border-radius:9px;background:${tc}12;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">${ic}</div><div><div style="font-family:'DM Mono',monospace;font-size:9px;color:${tc};letter-spacing:1.5px;margin-bottom:2px">${l}</div><div style="font-size:13px;color:rgba(255,255,255,.7);line-height:1.5">${v}</div></div></div>`).join("")}</div><div style="margin-top:14px;background:rgba(255,68,68,.05);border:1px solid rgba(255,68,68,.1);border-radius:14px;padding:12px 16px"><div style="display:flex;align-items:center;gap:6px;margin-bottom:4px"><span>⚠️</span><span style="font-family:'DM Mono',monospace;font-size:9px;color:#FF6B6B;letter-spacing:1.5px">BARBER NOTES</span></div><div style="font-size:12px;color:rgba(255,255,255,.5);line-height:1.6">${card.avoid}</div></div></div><div style="padding:16px 24px 36px;display:flex;flex-direction:column;gap:10px"><button class="btn" style="background:linear-gradient(135deg,${tc},${tc}CC);color:${tc==='var(--yellow)'?'#0A0A0F':'white'};box-shadow:0 0 30px ${tc}33">🔒 LOCK THIS LOOK</button><button class="btn" style="background:#25D366;color:white;display:flex;align-items:center;justify-content:center;gap:8px">Share via WhatsApp 💬</button><div style="display:flex;gap:10px"><button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:12px;padding:13px 0">📱 Save</button><button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:12px;padding:13px 0">📋 Copy</button></div></div>`;
  showScreen("detail");
}
</script>
</body>
</html>"""


@app.get("/api/looks")
async def list_looks():
    """Return all available Hero Looks (for debugging/admin)."""
    return {"looks": [{
        "id": l["id"], "tier": l["tier"], "name": l["name"],
        "vibe": l["vibe"], "min_length_cm": l["min_length_cm"],
        "min_density": l["min_density"],
    } for l in HERO_LOOKS]}


# ═══════════════════════════════════════════════════════
# FRONTEND — Served directly from the backend (no CORS)
# ═══════════════════════════════════════════════════════
from fastapi.responses import HTMLResponse

@app.get("/app", response_class=HTMLResponse)
async def frontend():
    """Serve the complete StyleLock frontend."""
    return FRONTEND_HTML


FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>StyleLock AI</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✂️</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{--bg:#0A0A0F;--card:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08);--pink:#FF3CAC;--cyan:#00E5FF;--yellow:#FFE600;--green:#00E676;--red:#FF4444;--orange:#FFB800;--text:#fff;--muted:rgba(255,255,255,0.45);--dim:rgba(255,255,255,0.25)}
  *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
  body{background:#050508;font-family:'Outfit',sans-serif;color:var(--text);min-height:100vh;display:flex;justify-content:center}
  input[type="file"]{display:none}::-webkit-scrollbar{width:0}
  .app{width:100%;max-width:420px;min-height:100vh;background:var(--bg);position:relative;overflow-x:hidden}
  .screen{width:100%;min-height:100vh;display:flex;flex-direction:column;animation:fadeIn .3s ease}.screen.hidden{display:none}
  .tag{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:3px;font-weight:500}
  .btn{width:100%;padding:18px 0;border-radius:16px;border:none;font-family:'Outfit';font-size:16px;font-weight:700;cursor:pointer;position:relative;overflow:hidden}
  .btn::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);background-size:200% 100%;animation:shimmer 2s infinite}
  .btn-pink{background:linear-gradient(135deg,var(--pink),#784BA0,#2B86C5);color:#fff;box-shadow:0 0 28px rgba(255,60,172,.3)}
  .badge{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:8px;font-size:11px}
  .badge-ready{background:rgba(0,230,118,.1);color:var(--green)}.badge-grow{background:rgba(255,184,0,.1);color:var(--orange)}.badge-dream{background:rgba(255,68,68,.1);color:var(--red)}
  @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  @keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
  @keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
  @keyframes slideUp{0%{opacity:0;transform:translateY(20px)}100%{opacity:1;transform:translateY(0)}}
  @keyframes orbitSpin{0%{transform:translate(-50%,-50%) rotate(0)}100%{transform:translate(-50%,-50%) rotate(360deg)}}
  @keyframes blob{0%,100%{border-radius:60% 40% 30% 70%/60% 30% 70% 40%}50%{border-radius:30% 60% 70% 40%/50% 60% 30% 60%}}
  @keyframes ringPulse{0%{transform:translate(-50%,-50%) scale(1);opacity:.3}100%{transform:translate(-50%,-50%) scale(2);opacity:0}}
</style>
</head>
<body>
<div class="app" id="app">

  <!-- INTRO -->
  <div class="screen" id="screen-intro" style="padding:0 28px;position:relative;overflow:hidden">
    <div style="position:absolute;top:-60px;right:-60px;width:200px;height:200px;border-radius:50%;background:radial-gradient(circle,rgba(255,60,172,.2),transparent 70%);filter:blur(40px);animation:blob 6s ease-in-out infinite"></div>
    <div style="position:absolute;bottom:-40px;left:-40px;width:160px;height:160px;border-radius:50%;background:radial-gradient(circle,rgba(0,229,255,.15),transparent 70%);filter:blur(40px);animation:blob 8s ease-in-out infinite reverse"></div>
    <div style="flex:1;display:flex;flex-direction:column;justify-content:center;z-index:1">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px">
        <span style="font-size:36px">✂️</span>
        <div>
          <div style="font-family:'DM Mono',monospace;font-size:22px;font-weight:700;background:linear-gradient(90deg,var(--pink),#784BA0,var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent">STYLELOCK</div>
          <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--pink);letter-spacing:4px">AI HAIR TRY-ON</div>
        </div>
      </div>
      <h1 style="font-size:30px;font-weight:900;line-height:1.2;margin-bottom:14px">See <span style="background:linear-gradient(90deg,var(--pink),var(--yellow));-webkit-background-clip:text;-webkit-text-fill-color:transparent">yourself</span> with<br>3 new looks</h1>
      <p style="font-size:15px;color:var(--muted);line-height:1.7;margin-bottom:28px">One selfie. AI analyzes your face and hair. Generates photorealistic previews of YOU with 3 personalized hairstyles.</p>
      <div id="intro-steps"></div>
    </div>
    <div style="padding-bottom:40px;z-index:1">
      <input type="file" id="file-input" accept="image/*" capture="user">
      <button class="btn btn-pink" onclick="document.getElementById('file-input').click()">📸 TAKE A SELFIE</button>
      <p style="font-size:11px;color:var(--dim);text-align:center;margin-top:8px">Your photo is sent for analysis, then deleted</p>
    </div>
  </div>

  <!-- PREVIEW -->
  <div class="screen hidden" id="screen-preview" style="padding:44px 24px 36px">
    <div class="tag" style="color:var(--cyan);margin-bottom:8px">PREVIEW</div>
    <h2 style="font-size:22px;font-weight:800;margin-bottom:4px">Looking good! 📸</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:16px">This selfie will be sent for AI analysis and hairstyle generation.</p>
    <div style="flex:1;border-radius:20px;overflow:hidden;border:2px solid rgba(0,229,255,.3);margin-bottom:16px">
      <img id="preview-img" style="width:100%;height:100%;object-fit:cover" alt="selfie">
    </div>
    <div style="display:flex;gap:12px">
      <button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:14px" onclick="resetApp()">🔄 Retake</button>
      <button class="btn btn-pink" style="flex:2;font-size:14px" onclick="startConsult()">✨ GENERATE 3 LOOKS</button>
    </div>
  </div>

  <!-- GENERATING -->
  <div class="screen hidden" id="screen-generating" style="align-items:center;justify-content:center;padding:32px;position:relative;overflow:hidden;background:linear-gradient(135deg,#0A0A0F,#1A0A2E)">
    <div style="position:absolute;top:50%;left:50%;width:280px;height:280px;border-radius:50%;border:1px solid rgba(255,60,172,.12);animation:orbitSpin 10s linear infinite"><div style="position:absolute;top:0;left:50%;width:8px;height:8px;border-radius:50%;background:var(--pink);transform:translateX(-50%);box-shadow:0 0 20px var(--pink)"></div></div>
    <div style="position:absolute;top:50%;left:50%;width:180px;height:180px;border-radius:50%;border:1px solid rgba(0,229,255,.1);animation:orbitSpin 7s linear infinite reverse"><div style="position:absolute;top:0;left:50%;width:6px;height:6px;border-radius:50%;background:var(--cyan);transform:translateX(-50%);box-shadow:0 0 15px var(--cyan)"></div></div>
    <div style="position:absolute;top:50%;left:50%;width:100px;height:100px;border-radius:50%;border:2px solid rgba(255,60,172,.15);animation:ringPulse 2s ease-out infinite"></div>
    <div id="gen-emoji" style="font-size:48px;margin-bottom:20px;animation:float 2s ease-in-out infinite;z-index:1">🧠</div>
    <p id="gen-step" style="font-family:'DM Mono',monospace;font-size:15px;z-index:1;text-align:center">Connecting...</p>
    <p id="gen-detail" style="font-size:13px;color:var(--muted);z-index:1;text-align:center;margin-top:6px">This takes 20-60 seconds</p>
    <div style="display:flex;gap:8px;margin-top:24px;z-index:1">
      <div class="gen-bar" data-step="analysis"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--pink);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Analysis</span></div>
      <div class="gen-bar" data-step="scoring"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--cyan);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Scoring</span></div>
      <div class="gen-bar" data-step="generating"><div style="width:60px;height:4px;border-radius:2px;background:rgba(255,255,255,.08);overflow:hidden"><div class="gen-fill" style="width:0%;height:100%;border-radius:2px;background:var(--yellow);transition:width .5s"></div></div><span style="font-size:9px;color:var(--dim);display:block;text-align:center;margin-top:4px">Try-On</span></div>
    </div>
  </div>

  <!-- RESULTS -->
  <div class="screen hidden" id="screen-results" style="padding:44px 24px 32px;overflow:auto">
    <div style="margin-bottom:20px">
      <div class="tag" style="color:var(--pink);margin-bottom:8px">YOUR 3 LOOKS</div>
      <h2 style="font-size:24px;font-weight:800;margin-bottom:4px">Here's you, 3 ways ✨</h2>
      <p style="font-size:13px;color:var(--muted)">AI-generated previews based on your face analysis. Tap any to see the Cut Card.</p>
    </div>
    <div id="analysis-chips" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px"></div>
    <div id="results-cards" style="display:flex;flex-direction:column;gap:16px"></div>
    <button class="btn" style="background:transparent;color:var(--dim);font-size:13px;margin-top:20px;border:none" onclick="resetApp()">📸 Take a new selfie</button>
  </div>

  <!-- DETAIL -->
  <div class="screen hidden" id="screen-detail" style="overflow:auto">
    <div id="detail-content"></div>
  </div>

</div>

<script>
const API_BASE = "";  // Same origin — no CORS issues!

let currentFile = null, currentPhotoUrl = null, consultResult = null;

// Intro steps
["📸 Take one front selfie","🧠 AI analyzes face shape, hair & density","✨ See yourself with 3 AI-generated hairstyles","🔒 Lock a look, get a barber-ready Cut Card"].forEach((t,i) => {
  const d = document.createElement("div");
  d.style.cssText = "display:flex;align-items:center;gap:12px;margin-bottom:11px;animation:slideUp .4s ease-out "+(0.1+i*0.06)+"s both";
  d.innerHTML = '<span style="font-size:16px;width:28px;text-align:center">'+t.slice(0,2)+'</span><span style="font-size:14px;color:rgba(255,255,255,0.55)">'+t.slice(3)+'</span>';
  document.getElementById("intro-steps").appendChild(d);
});

function showScreen(id){document.querySelectorAll(".screen").forEach(s=>s.classList.add("hidden"));document.getElementById("screen-"+id).classList.remove("hidden");window.scrollTo(0,0)}
function resetApp(){currentFile=null;currentPhotoUrl=null;consultResult=null;document.getElementById("file-input").value="";showScreen("intro")}

document.getElementById("file-input").addEventListener("change",function(e){
  const f=e.target.files?.[0];if(!f)return;currentFile=f;
  const r=new FileReader();r.onload=(ev)=>{currentPhotoUrl=ev.target.result;document.getElementById("preview-img").src=currentPhotoUrl;showScreen("preview")};r.readAsDataURL(f);
});

function updateGen(step,pct,emoji,text,detail){
  if(emoji)document.getElementById("gen-emoji").textContent=emoji;
  if(text)document.getElementById("gen-step").textContent=text;
  if(detail)document.getElementById("gen-detail").textContent=detail;
  const steps=["analysis","scoring","generating"];const idx=steps.indexOf(step);
  document.querySelectorAll(".gen-bar").forEach((bar,i)=>{const fill=bar.querySelector(".gen-fill");if(i<idx)fill.style.width="100%";else if(i===idx)fill.style.width=pct+"%"});
}

async function startConsult(){
  showScreen("generating");
  updateGen("analysis",30,"🧠","Analyzing your face & hair...","Claude Vision AI is reading your features");
  try{
    const fd=new FormData();fd.append("file",currentFile);
    const timers=[
      setTimeout(()=>updateGen("analysis",100,"🧠","Face analyzed!","Scoring looks..."),3000),
      setTimeout(()=>updateGen("scoring",100,"🎯","3 looks selected!","Generating AI previews..."),5000),
      setTimeout(()=>updateGen("generating",20,"✨","Creating your previews...","LightX AI is generating hairstyles on your face"),7000),
      setTimeout(()=>updateGen("generating",40,"✨","Still working...","AI generation takes 15-45 seconds per look"),15000),
      setTimeout(()=>updateGen("generating",60,"✨","Almost there...","Waiting for LightX to finish"),30000),
      setTimeout(()=>updateGen("generating",75,"⏳","Taking longer than usual...","LightX is still processing — hang tight"),60000),
    ];
    const ctrl=new AbortController();const tout=setTimeout(()=>ctrl.abort(),180000);
    const resp=await fetch(API_BASE+"/api/consult",{method:"POST",body:fd,signal:ctrl.signal});
    clearTimeout(tout);timers.forEach(t=>clearTimeout(t));
    if(!resp.ok){const e=await resp.text();throw new Error("Server "+resp.status+": "+e.substring(0,150))}
    consultResult=await resp.json();
    if(!consultResult.success)throw new Error(consultResult.error||"Failed");
    updateGen("generating",100,"🎉","Done!","Loading your looks...");
    setTimeout(()=>renderResults(),500);
  }catch(err){
    console.error(err);const isT=err.name==="AbortError";
    document.getElementById("gen-step").textContent=isT?"⏳ Timed out":"⚠️ Something went wrong";
    document.getElementById("gen-detail").innerHTML='<span style="color:var(--red);font-size:13px">'+(isT?"Server took too long.":err.message)+'</span><br><div style="display:flex;gap:10px;justify-content:center;margin-top:16px"><button class="btn" style="padding:12px 20px;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:13px;width:auto" onclick="resetApp()">← Back</button><button class="btn" style="padding:12px 20px;background:linear-gradient(135deg,var(--pink),#784BA0);color:#fff;font-size:13px;width:auto" onclick="startConsult()">🔄 Retry</button></div>';
  }
}

function renderResults(){
  const{analysis:a,recommendations:recs}=consultResult;
  const ch=document.getElementById("analysis-chips");ch.innerHTML="";
  [{l:"◆",v:a.faceShape},{l:"〰",v:a.hairTexture},{l:"▓",v:a.density},{l:"📏",v:a.estimatedTopLengthCm+"cm"},{l:"⌒",v:a.hairlineState}].forEach(({l,v})=>{ch.innerHTML+='<div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:5px 10px;font-size:11px;color:var(--muted);text-transform:capitalize">'+l+" "+v+"</div>"});
  const tc={"CLEAN":"var(--cyan)","TRENDING":"var(--pink)","BOLD":"var(--yellow)"};
  const te={"CLEAN":"💼","TRENDING":"🔥","BOLD":"⚡"};
  const cd=document.getElementById("results-cards");cd.innerHTML="";
  recs.forEach((r,i)=>{
    const c=tc[r.look.tier]||"var(--pink)",e=te[r.look.tier]||"✨",has=r.preview_url&&r.preview_url!=="null"&&r.preview_url!==null;
    const ab=r.achievability==="ready"?'<span class="badge badge-ready">🟢 Ready now</span>':r.achievability==="grow"?'<span class="badge badge-grow">🟡 ~'+r.growth_weeks+' weeks</span>':'<span class="badge badge-dream">🔴 ~'+r.growth_weeks+' weeks</span>';
    const d=document.createElement("div");d.style.cssText="border-radius:20px;overflow:hidden;border:1px solid "+c+"30;cursor:pointer;animation:slideUp .4s ease-out "+i*.1+"s both";
    d.onclick=()=>showDetail(r,c,e);
    d.innerHTML='<div style="width:100%;height:300px;background:'+c+'08;position:relative">'+(has?'<img src="'+r.preview_url+'" style="width:100%;height:100%;object-fit:cover" alt="'+r.look.name+'">':'<div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center"><span style="font-size:48px;margin-bottom:8px">'+e+'</span><span style="font-size:12px;color:var(--dim)">Preview unavailable</span></div>')+'<div style="position:absolute;top:12px;left:12px;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);border-radius:10px;padding:6px 12px;display:flex;align-items:center;gap:6px"><span style="font-size:14px">'+e+'</span><span style="font-family:DM Mono,monospace;font-size:10px;color:'+c+'">'+r.look.tier+'</span></div><div style="position:absolute;top:12px;right:12px;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);border-radius:10px;padding:6px 12px"><span style="font-family:DM Mono,monospace;font-size:18px;font-weight:700;color:'+c+'">'+r.score+'</span><span style="font-size:10px;color:'+c+'">%</span></div><div style="position:absolute;bottom:0;left:0;right:0;height:60px;background:linear-gradient(transparent,#0A0A0F)"></div></div><div style="padding:14px 18px"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px"><h3 style="font-size:18px;font-weight:800">'+r.look.name+'</h3>'+ab+'</div><div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><span style="font-size:12px;color:var(--muted)">'+r.look.vibe+'</span><span style="font-size:10px;color:var(--dim)">•</span><span style="font-size:12px;color:var(--muted)">🔧 '+r.look.maintenance+'</span><span style="font-size:10px;color:var(--dim)">•</span><span style="font-size:12px;color:var(--muted)">⏱ '+r.look.daily_time+'</span></div><div style="width:100%;padding:10px 0;border-radius:10px;border:1px solid '+c+'40;background:'+c+'08;text-align:center;font-size:13px;font-weight:700;color:'+c+'">VIEW CUT CARD →</div></div>';
    cd.appendChild(d);
  });
  showScreen("results");
}

function showDetail(r,c,e){
  const has=r.preview_url&&r.preview_url!=="null"&&r.preview_url!==null;const card=r.look.card;
  const at=r.achievability==="ready"?"Your hair can achieve this today":r.achievability==="grow"?"Needs ~"+r.growth_gap_cm+"cm more (~"+r.growth_weeks+" weeks)":"Aspirational — needs ~"+r.growth_weeks+" weeks growth";
  const ac=r.achievability==="ready"?"var(--green)":r.achievability==="grow"?"var(--orange)":"var(--red)";
  const ab=r.achievability==="ready"?"🟢":r.achievability==="grow"?"🟡":"🔴";
  const rows=[{i:"💇",l:"FADE / TAPER",v:card.fade},{i:"📏",l:"TOP LENGTH",v:card.top},{i:"↗️",l:"FRINGE",v:card.fringe},{i:"✨",l:"STYLING",v:card.styling},{i:"🧴",l:"PRODUCTS",v:card.products},{i:"🧔",l:"BEARD",v:card.beard}];
  document.getElementById("detail-content").innerHTML='<div style="width:100%;height:340px;position:relative;flex-shrink:0">'+(has?'<img src="'+r.preview_url+'" style="width:100%;height:100%;object-fit:cover">':'<div style="width:100%;height:100%;background:'+c+'08;display:flex;align-items:center;justify-content:center"><span style="font-size:64px">'+e+'</span></div>')+'<button onclick="showScreen(\'results\')" style="position:absolute;top:44px;left:16px;background:rgba(0,0,0,.6);backdrop-filter:blur(10px);border:none;border-radius:10px;padding:8px 14px;color:#fff;font-family:Outfit;font-size:12px;font-weight:600;cursor:pointer">← BACK</button><div style="position:absolute;bottom:0;left:0;right:0;height:80px;background:linear-gradient(transparent,#0A0A0F)"></div></div><div style="padding:0 24px 20px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><span class="tag" style="color:'+c+'">'+r.look.tier+'</span><span style="color:var(--dim)">·</span><span style="font-size:12px;color:var(--muted)">'+r.look.vibe+'</span></div><h2 style="font-size:26px;font-weight:800;margin-bottom:6px">'+r.look.name+' '+e+'</h2><div style="background:'+ac+'10;border:1px solid '+ac+'30;border-radius:12px;padding:10px 14px;margin-bottom:16px;display:flex;align-items:center;gap:8px"><span style="font-size:16px">'+ab+'</span><span style="font-size:13px;color:'+ac+';font-weight:600">'+at+'</span></div><div style="display:flex;gap:8px;margin-bottom:16px"><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">🔧 '+r.look.maintenance+'</div><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">⏱ '+r.look.daily_time+'</div><div style="background:var(--card);border-radius:8px;padding:5px 10px;font-size:11px;color:var(--muted)">Match: '+r.score+'%</div></div><div class="tag" style="color:'+c+';margin-bottom:10px">✂ CUT CARD</div><div style="background:var(--card);border:1px solid '+c+'18;border-radius:18px;padding:6px 18px 18px">'+rows.map((x,idx)=>'<div style="display:flex;gap:12px;padding:12px 0;border-bottom:'+(idx<rows.length-1?"1px solid rgba(255,255,255,.05)":"none")+'"><div style="width:34px;height:34px;border-radius:9px;background:'+c+'12;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">'+x.i+'</div><div><div style="font-family:DM Mono,monospace;font-size:9px;color:'+c+';letter-spacing:1.5px;margin-bottom:2px">'+x.l+'</div><div style="font-size:13px;color:rgba(255,255,255,.7);line-height:1.5">'+x.v+'</div></div></div>').join("")+'</div><div style="margin-top:14px;background:rgba(255,68,68,.05);border:1px solid rgba(255,68,68,.1);border-radius:14px;padding:12px 16px"><div style="display:flex;align-items:center;gap:6px;margin-bottom:4px"><span>⚠️</span><span style="font-family:DM Mono,monospace;font-size:9px;color:#FF6B6B;letter-spacing:1.5px">BARBER NOTES</span></div><div style="font-size:12px;color:rgba(255,255,255,.5);line-height:1.6">'+card.avoid+'</div></div></div><div style="padding:16px 24px 36px;display:flex;flex-direction:column;gap:10px"><button class="btn" style="background:linear-gradient(135deg,'+c+','+c+'CC);color:'+(c==="var(--yellow)"?"#0A0A0F":"#fff")+';box-shadow:0 0 30px '+c+'33">🔒 LOCK THIS LOOK</button><button class="btn" style="background:#25D366;color:#fff;display:flex;align-items:center;justify-content:center;gap:8px">Share via WhatsApp 💬</button><div style="display:flex;gap:10px"><button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:12px;padding:13px 0">📱 Save</button><button class="btn" style="flex:1;background:var(--card);border:1px solid var(--border);color:var(--muted);font-size:12px;padding:13px 0">📋 Copy</button></div></div>';
  showScreen("detail");
}
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
