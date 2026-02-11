# backend/routers/payments.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Annotated
import stripe
import os

from backend import schemas, crud
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY


@router.get('/create-checkout-session')
async def create_checkout_session(
    current_user: Annotated[schemas.UserResponse, Depends(get_current_user)]
):
    """
    Create Stripe checkout sessions for Premium and Ultra subscription plans.
    Returns URLs for both plans.
    """
    print(f'Checkout link hit by user: {current_user.email}')
    
    try:
        # Premium plan checkout session
        checkout_session_premium = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': settings.STRIPE_PRICE_PREMIUM,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{settings.FRONTEND_URL}/dashboard",
            cancel_url=f"{settings.FRONTEND_URL}/pricing?canceled=true",
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'plan': 'premium'
            }
        )
        
        # Ultra plan checkout session
        checkout_session_ultra = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': settings.STRIPE_PRICE_ULTRA,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{settings.FRONTEND_URL}/dashboard",
            cancel_url=f"{settings.FRONTEND_URL}/pricing?canceled=true",
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'plan': 'ultra'
            }
        )
        
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    
    print(f"Created checkout sessions for user {current_user.email}")
    return JSONResponse(content={
        'premium': checkout_session_premium.url, 
        'ultra': checkout_session_ultra.url
    })

@router.post('/webhook')
async def webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events for payment completion.
    """
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        
        print(f"Received webhook event: {event['type']}")
        
        # Handle checkout session completed (initial purchase)
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Retrieve full session with line items
            session_with_items = stripe.checkout.Session.retrieve(
                session['id'], 
                expand=['line_items']
            )
            
            price_id = session_with_items['line_items']['data'][0]['price']['id']
            customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')
            
            print(f"Payment completed - Price ID: {price_id}, Email: {customer_email}")
            
            # Check payment status and add credits accordingly
            if session['payment_status'] == 'paid':
                _add_credits_for_price(db, customer_email, price_id)
        
        # Handle invoice paid (renewals and initial payments)
        elif event['type'] == 'invoice.paid':
            invoice = event['data']['object']
            
            # Skip if this is a draft invoice or the first invoice of a subscription
            # (already handled by checkout.session.completed)
            if invoice.get('billing_reason') == 'subscription_create':
                print("Skipping initial subscription invoice (handled by checkout.session.completed)")
                return {"status": "success"}

            print('now this gggggg') 
            # Get customer email
            customer_email = None
            if invoice.get('customer_email'):
                customer_email = invoice['customer_email']
            elif invoice.get('customer'):
                customer = stripe.Customer.retrieve(invoice['customer'])
                customer_email = customer.email
            
            # Get price ID from the invoice line items
            if invoice.get('lines') and invoice['lines'].get('data'):
                price_id = invoice['lines']['data'][0]['price']['id']
                print(f"Invoice paid - Price ID: {price_id}, Email: {customer_email}")
                _add_credits_for_price(db, customer_email, price_id)
            
        # Handle invoice payment failed
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            print(f"Payment failed for invoice: {invoice['id']}")
            
    except ValueError as e:
        print(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail=f'Invalid payload: {e}')
    except stripe.error.SignatureVerificationError as e:
        print(f"Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail=f'Signature verification failed: {e}')
    except Exception as e:
        print(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"status": "success"}


def _add_credits_for_price(db: Session, customer_email: str, price_id: str):
    """Helper function to add credits based on price ID"""
    if price_id == settings.STRIPE_PRICE_PREMIUM:
        print(f'Adding 25 credits to {customer_email}')
        crud.add_subscription_credits(db, customer_email, 25)
    elif price_id == settings.STRIPE_PRICE_ULTRA:
        print(f'Adding 50 credits to {customer_email}')
        crud.add_subscription_credits(db, customer_email, 50)
    else:
        print(f'Unknown price ID: {price_id}')


@router.get('/subscription-status')
async def get_subscription_status(
    current_user: Annotated[schemas.UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get current user's subscription status and credits.
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "subscription": user.subscription,
        "credits": user.credits,
        "email": user.email
    }