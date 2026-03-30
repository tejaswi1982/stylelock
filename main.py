"""
StyleLock AI - Backend Server v51
Clean architecture: separate files for HTML, CSS, JS, and images.
"""

import os
import base64
import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# =============================================================================
# CONFIGURATION
# =============================================================================

# Environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
VMODEL_API_KEY = os.getenv("VMODEL_API_KEY", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "false").lower() == "true"

# VMODEL API endpoint
VMODEL_API_URL = "https://developer.vmodel.ai/api/vmodel/hairchange"

# Hairstyle configurations
HAIRSTYLES = {
    "bold": {
        "id": "101",
        "name": "BOLD",
        "top_length": "3 inches",
        "sides": "0.5 fade",
        "texture": "textured",
        "products": "matte clay"
    },
    "clean": {
        "id": "102",
        "name": "CLEAN",
        "top_length": "2 inches",
        "sides": "skin fade",
        "texture": "smooth",
        "products": "pomade"
    },
    "trending": {
        "id": "103",
        "name": "TRENDING",
        "top_length": "4 inches",
        "sides": "1 guard",
        "texture": "wavy",
        "products": "sea salt spray"
    }
}

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="StyleLock AI",
    description="AI-powered hairstyle recommendations",
    version="51"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the directory where main.py is located
BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# =============================================================================
# ROUTES - Pages
# =============================================================================

@app.get("/", response_class=JSONResponse)
async def root():
    """Health check and API status endpoint."""
    return {
        "app": "StyleLock AI",
        "version": "51",
        "status": "running",
        "apis": {
            "anthropic": "configured" if ANTHROPIC_API_KEY else "not configured",
            "vmodel": "configured" if VMODEL_API_KEY else "not configured",
            "razorpay": "configured" if RAZORPAY_KEY_ID else "demo mode",
            "removebg": "configured" if REMOVEBG_API_KEY else "not configured",
            "bg_removal_enabled": ENABLE_BG_REMOVAL
        }
    }


@app.get("/app", response_class=HTMLResponse)
async def serve_app(request: Request):
    """Serve the main application."""
    return templates.TemplateResponse("app.html", {"request": request})


# =============================================================================
# ROUTES - API Endpoints
# =============================================================================

@app.post("/api/create-order")
async def create_razorpay_order():
    """Create a Razorpay order for payment."""
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        # Demo mode - skip payment
        return {
            "order_id": "demo_order",
            "amount": 7900,
            "currency": "INR",
            "demo": True
        }
    
    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": 7900,  # ₹79 in paise
            "currency": "INR",
            "payment_capture": 1
        })
        return {
            "order_id": order["id"],
            "amount": 7900,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID
        }
    except Exception as e:
        print(f"Razorpay error: {e}")
        return {"order_id": "demo_order", "amount": 7900, "currency": "INR", "demo": True}


@app.post("/api/generate-looks")
async def generate_looks(request: Request):
    """Generate hairstyle looks using VMODEL API."""
    try:
        data = await request.json()
        image_base64 = data.get("image", "")
        
        if not image_base64:
            return JSONResponse(
                {"error": "No image provided"},
                status_code=400
            )
        
        # Step 1: Remove background if enabled
        processed_image = image_base64
        if ENABLE_BG_REMOVAL and REMOVEBG_API_KEY:
            processed_image = await remove_background(image_base64)
        
        # Step 2: Generate hairstyles
        looks = await generate_all_hairstyles(processed_image)
        
        return {"looks": looks, "success": True}
        
    except Exception as e:
        print(f"generate_looks error: {e}")
        return JSONResponse(
            {"error": str(e), "success": False},
            status_code=500
        )


# =============================================================================
# HELPER FUNCTIONS - External APIs
# =============================================================================

async def remove_background(image_base64: str) -> str:
    """Remove background from image using remove.bg API."""
    if not REMOVEBG_API_KEY:
        return image_base64
    
    try:
        # Extract base64 data (remove data URL prefix if present)
        if "base64," in image_base64:
            image_data = image_base64.split("base64,")[1]
        else:
            image_data = image_base64
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.remove.bg/v1.0/removebg",
                data={
                    "size": "auto",
                    "image_file_b64": image_data,
                    "bg_color": "1a2f2a"  # Match our dark green background
                },
                headers={"X-Api-Key": REMOVEBG_API_KEY}
            )
            
            if response.status_code == 200:
                result_b64 = base64.b64encode(response.content).decode()
                return f"data:image/png;base64,{result_b64}"
            else:
                print(f"remove.bg error: {response.status_code} - {response.text[:200]}")
                return image_base64
                
    except Exception as e:
        print(f"remove.bg exception: {e}")
        return image_base64


async def generate_hairstyle_vmodel(image_base64: str, hairstyle_id: str) -> str | None:
    """Generate a single hairstyle using VMODEL API."""
    if not VMODEL_API_KEY:
        return None
    
    try:
        # Extract base64 data
        if "base64," in image_base64:
            image_data = image_base64.split("base64,")[1]
        else:
            image_data = image_base64
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                VMODEL_API_URL,
                json={
                    "image": image_data,
                    "hairstyle_id": hairstyle_id
                },
                headers={
                    "Authorization": f"Bearer {VMODEL_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("result"):
                    return data["result"]
                elif data.get("output"):
                    return data["output"]
            
            print(f"VMODEL error: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"VMODEL exception: {e}")
        return None


async def generate_all_hairstyles(image_base64: str) -> list:
    """Generate all hairstyle looks, with fallback to static images."""
    looks = []
    
    if VMODEL_API_KEY:
        # Try to generate with VMODEL API in parallel
        tasks = [
            generate_hairstyle_vmodel(image_base64, style["id"])
            for style in HAIRSTYLES.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (style_key, style_info), result in zip(HAIRSTYLES.items(), results):
            if result and not isinstance(result, Exception) and isinstance(result, str):
                # API success
                looks.append({
                    "name": style_info["name"],
                    "image": result if result.startswith("data:") else f"data:image/jpeg;base64,{result}",
                    "top_length": style_info["top_length"],
                    "sides": style_info["sides"],
                    "texture": style_info["texture"],
                    "products": style_info["products"]
                })
            else:
                # Fallback to static image
                looks.append({
                    "name": style_info["name"],
                    "image": f"/static/images/hairstyle_{style_key}.jpg",
                    "top_length": style_info["top_length"],
                    "sides": style_info["sides"],
                    "texture": style_info["texture"],
                    "products": style_info["products"]
                })
    else:
        # No API key - use all static images
        for style_key, style_info in HAIRSTYLES.items():
            looks.append({
                "name": style_info["name"],
                "image": f"/static/images/hairstyle_{style_key}.jpg",
                "top_length": style_info["top_length"],
                "sides": style_info["sides"],
                "texture": style_info["texture"],
                "products": style_info["products"]
            })
    
    return looks


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 StyleLock AI v51 starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
