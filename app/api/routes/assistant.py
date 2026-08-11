from __future__ import annotations

import re
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.core.config import settings


router = APIRouter(prefix="/assistant", tags=["assistant"])

# Maximum characters we forward to prevent abuse
_MAX_MESSAGE_LEN = 800

SYSTEM_PROMPT = (
    "You are IntelliBMS, an AI battery safety monitor. "
    "Your job is to read the battery's current State of Health (SoH), Remaining Useful Life (RUL), "
    "and degradation drivers, and provide a concise, safety-aware summary.\n\n"
    "CRITICAL RULES & GUARDRAILS:\n"
    "1. Start your response with a clear safety category: 'Normal Operation', 'Monitor Closely', or 'Replace Soon'.\n"
    "2. Briefly explain what is driving the degradation based on the provided drivers.\n"
    "3. You MUST explain that the RUL is an estimate with inherent uncertainty based on historical assumptions.\n"
    "4. You MUST include a safety disclaimer stating: 'Disclaimer: This is a predictive estimate based on historical patterns. Always consult manufacturer guidelines.'\n"
    "5. NEVER output operational instructions like 'bypass BMS', 'override limits', or suggest any unsafe usage.\n\n"
    "FORMAT: Provide your response as a single, readable paragraph (2-3 sentences max)."
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_LEN)


class ChatResponse(BaseModel):
    reply: str


class AdminStatusResponse(BaseModel):
    is_admin: bool


def _generate_local_fallback(message: str) -> str:
    """
    Generates a high-quality, safety-aware narrative locally if external AI services are unavailable or out of credits.
    """
    soh_match = re.search(r"SOH\s*([\d.]+)", message, re.IGNORECASE)
    rul_match = re.search(r"RUL\s*([\d.]+)", message, re.IGNORECASE)
    drivers_match = re.search(r"Drivers:\s*(.+)$", message, re.IGNORECASE)

    soh = float(soh_match.group(1)) if soh_match else 90.0
    rul = float(rul_match.group(1)) if rul_match else 100.0
    drivers_str = drivers_match.group(1).strip() if drivers_match else "Normal Aging"

    if soh < 80 or rul < 40:
        category = "Replace Soon"
        status_text = f"Battery health has dropped to {soh:.1f}% with an estimated RUL of {int(rul)} cycles."
        action_text = f"Immediate action required. High risk of failure driven by: {drivers_str}."
    elif soh < 90 or "High Temperature" in drivers_str or "Internal Resistance" in drivers_str:
        category = "Monitor Closely"
        status_text = f"Degradation factors ({drivers_str}) are actively impacting performance. SOH is at {soh:.1f}% and RUL is {int(rul)} cycles."
        action_text = "Schedule maintenance to investigate driving factors and prevent further rapid degradation."
    else:
        category = "Normal Operation"
        status_text = f"Battery parameters are currently within normal baseline parameters. SOH is {soh:.1f}%, RUL is {int(rul)} cycles."
        action_text = f"Routine degradation detected ({drivers_str}). Continue standard monitoring."

    return (
        f"{category}: {status_text} {action_text} "
        f"Note that predicted Remaining Useful Life carries inherent statistical uncertainty based on cycle history. "
        f"Disclaimer: This is a predictive estimate based on historical patterns. Always consult manufacturer guidelines."
    )


@router.get("/status", response_model=AdminStatusResponse)
async def admin_status(
    _: None = Depends(require_admin),
) -> AdminStatusResponse:
    """
    Returns { is_admin: true } when the X-Admin-Token header is valid.
    The frontend calls this on load to decide whether to render the widget.
    """
    return AdminStatusResponse(is_admin=True)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    _: None = Depends(require_admin),
) -> ChatResponse:
    """
    Generates AI narrative using n8n webhook,
    and finally using local intelligent fallback to ensure 100% uptime.
    """
    # 1. Primary Mode: n8n Webhook
    if settings.n8n_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.n8n_webhook_url,
                    json={"message": body.message},
                    headers={"X-N8N-API-Key": settings.n8n_api_key or ""},
                )
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception:
                        data = {"reply": response.text.strip()}

                    reply = (
                        data.get("reply")
                        or data.get("output")
                        or data.get("text")
                    )
                    if reply:
                        return ChatResponse(reply=str(reply))
                else:
                    print(f"[Assistant] n8n webhook returned HTTP {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[Assistant] n8n webhook call failed: {e}")

    # 2. Local Intelligent Fallback Engine (Guarantees zero downtime)
    fallback_reply = _generate_local_fallback(body.message)
    return ChatResponse(reply=fallback_reply)


