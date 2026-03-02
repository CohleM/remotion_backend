# backend/routers/referral.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend import crud, schemas
from backend.database import get_db
from backend.routers.auth import get_current_user, verify_affiliate_token

router = APIRouter(prefix="/referral", tags=["referral"])


# ─── /me ─────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=schemas.ReferrerResponse)
async def get_referral_me(
    referrer_id: int = Depends(verify_affiliate_token),
    db: Session = Depends(get_db),
):
    """
    Returns the referrer's profile including total earned, clicks,
    signups, and customers. Used on affiliate homepage load.
    """
    referrer = crud.get_referrer_by_id(db, referrer_id)
    if not referrer:
        raise HTTPException(status_code=404, detail="Referrer not found")
    return schemas.ReferrerResponse.model_validate(referrer)


# ─── Create / replace referral code ──────────────────────────────────────────

@router.post("/create", response_model=schemas.ReferrerResponse)
async def create_referral_code(
    payload: schemas.ReferrerCreate,
    referrer_id: int = Depends(verify_affiliate_token),
    db: Session = Depends(get_db),
):
    """
    Replace the referrer's current code with a new one.
    The new code must be unique across all referrers.
    """

    print('referrer id create ', referrer_id)
    import re
    code = payload.code.lower().strip()

    if not re.match(r'^[a-z0-9_]{3,20}$', code):
        raise HTTPException(
            status_code=400,
            detail="Code must be 3–20 characters, letters/numbers/underscores only."
        )

    # Check uniqueness (exclude self)
    existing = crud.get_referrer_by_code(db, code)
    if existing and existing.id != referrer_id:
        raise HTTPException(status_code=400, detail="Code already taken. Please choose another.")


    print('referrer id ', referrer_id)
    referrer = crud.get_referrer_by_id(db, referrer_id)
    if not referrer:
        raise HTTPException(status_code=404, detail="Referrer not found")

    referrer.code = code
    db.commit()
    db.refresh(referrer)
    return schemas.ReferrerResponse.model_validate(referrer)


# ─── Click tracking ───────────────────────────────────────────────────────────

@router.post("/click/{code}", status_code=200)
async def track_click(code: str, db: Session = Depends(get_db)):
    """
    Increment click count for a referral code.
    Called by the frontend when a visitor lands via a referral link.
    No auth required — public endpoint.
    """
    referrer = crud.get_referrer_by_code(db, code)
    if not referrer:
        raise HTTPException(status_code=404, detail="Referral code not found")

    crud.increment_referrer_clicks(db, code)
    return {"status": "ok"}


# ─── Referred users list ──────────────────────────────────────────────────────

@router.get("/users", response_model=List[schemas.ReferralUserResponse])
async def get_referral_users(
    referrer_id: int = Depends(verify_affiliate_token),
    db: Session = Depends(get_db),
):
    """
    Returns the list of users who signed up through this referrer's link.
    Emails are masked for privacy.
    """
    rows = crud.get_referral_users(db, referrer_id)
    result = []
    for referral, user in rows:
        masked = _mask_email(user.email)
        result.append(schemas.ReferralUserResponse(
            id=referral.id,
            masked_email=masked,
            converted=bool(referral.converted),
            created_at=referral.created_at,
        ))
    return result


# ─── Payouts ──────────────────────────────────────────────────────────────────

@router.get("/payouts", response_model=List[schemas.PayoutResponse])
async def get_payouts(
    referrer_id: int = Depends(verify_affiliate_token),
    db: Session = Depends(get_db),
):
    """Returns payout history for the authenticated referrer."""
    payouts = crud.get_payouts_for_referrer(db, referrer_id)
    return [schemas.PayoutResponse.model_validate(p) for p in payouts]


# ─── Profile update ───────────────────────────────────────────────────────────

@router.patch("/profile", response_model=schemas.ReferrerResponse)
async def update_profile(
    payload: schemas.ReferrerProfileUpdate,
    referrer_id: int = Depends(verify_affiliate_token),
    db: Session = Depends(get_db),
):
    """Update payout details: name, address, PayPal email."""
    referrer = crud.get_referrer_by_id(db, referrer_id)

    print('test', referrer_id, referrer)
    if not referrer:
        raise HTTPException(status_code=404, detail="Referrer not found")

    update_data = payload.model_dump(exclude_unset=True)
    updated = crud.update_referrer_profile_by_id(db, referrer_id, update_data)
    return schemas.ReferrerResponse.model_validate(updated)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    """Partially hide email for privacy."""
    try:
        local, domain = email.split('@')
        visible = local[:max(2, len(local) - 5)]
        hidden = '*' * min(5, len(local) - len(visible))
        return f"{visible}{hidden}@{domain}"
    except Exception:
        return email