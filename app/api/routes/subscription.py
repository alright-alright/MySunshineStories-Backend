"""
Subscription and payment management API routes
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request, Header, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import stripe
import os

from app.core.dependencies import CurrentUser, DatabaseSession
from app.services.stripe_service import stripe_service, SUBSCRIPTION_PLANS
from app.models.database_models import SubscriptionTier
from app.schemas.subscription import SubscriptionResponse

router = APIRouter()

# Stripe webhook secret
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# Request/Response models
class CreateCheckoutRequest(BaseModel):
    plan: str = Field(..., description="Subscription plan: plus or unlimited")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")


class CreatePaymentIntentRequest(BaseModel):
    description: str = Field(default="One-time story generation")


class UpdateSubscriptionRequest(BaseModel):
    plan: str = Field(..., description="New subscription plan: plus or unlimited")


class CheckoutResponse(BaseModel):
    checkout_url: str


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int


class CustomerPortalResponse(BaseModel):
    portal_url: str


class UsageResponse(BaseModel):
    stories_used: int
    stories_limit: int
    stories_remaining: int
    individual_credits: int
    subscription_tier: str
    can_generate_story: bool


class PricingResponse(BaseModel):
    plans: Dict[str, Any]


# ============== Subscription Management ==============

@router.get("/plans", response_model=PricingResponse)
async def get_subscription_plans():
    """Get available subscription plans and pricing"""
    return PricingResponse(plans=SUBSCRIPTION_PLANS)


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Get current user's subscription details"""
    if not current_user.subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )
    
    # Get latest status from Stripe if subscribed
    if current_user.subscription.stripe_subscription_id:
        stripe_data = stripe_service.retrieve_subscription(
            current_user.subscription.stripe_subscription_id
        )
        if stripe_data:
            # Update local subscription status
            current_user.subscription.status = stripe_data["status"]
            current_user.subscription.cancel_at_period_end = stripe_data["cancel_at_period_end"]
            db.commit()
    
    return SubscriptionResponse.from_orm_model(current_user.subscription)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Create a Stripe checkout session for subscription upgrade"""
    try:
        checkout_url = stripe_service.create_checkout_session(
            user=current_user,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            db=db
        )
        return CheckoutResponse(checkout_url=checkout_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/payment-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Create a payment intent for one-time story purchase"""
    try:
        # Individual story price is $5.00
        amount = SUBSCRIPTION_PLANS["individual"]["price_per_story"]
        
        payment_data = stripe_service.create_payment_intent(
            user=current_user,
            amount=amount,
            description=request.description,
            db=db
        )
        return PaymentIntentResponse(**payment_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment intent"
        )


@router.put("/update", response_model=Dict[str, str])
async def update_subscription(
    request: UpdateSubscriptionRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update subscription to a different plan"""
    if not current_user.subscription or not current_user.subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to update"
        )
    
    if request.plan not in ["plus", "unlimited"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription plan"
        )
    
    new_price_id = SUBSCRIPTION_PLANS[request.plan]["stripe_price_id"]
    
    result = stripe_service.update_subscription(
        subscription_id=current_user.subscription.stripe_subscription_id,
        new_price_id=new_price_id
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update subscription"
        )
    
    return {"message": "Subscription updated successfully", "status": result["status"]}


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = Field(default=False, description="Cancel immediately vs at period end")


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Cancel the current subscription"""
    if not current_user.subscription or not current_user.subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to cancel"
        )
    
    success = stripe_service.cancel_subscription(
        subscription_id=current_user.subscription.stripe_subscription_id,
        immediate=request.immediate
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )
    
    # Update local subscription status
    if request.immediate:
        current_user.subscription.status = "cancelled"
        current_user.subscription.tier = SubscriptionTier.FREE
    else:
        current_user.subscription.cancel_at_period_end = True
    
    db.commit()
    
    return {
        "message": "Subscription cancelled successfully",
        "immediate": request.immediate
    }


@router.post("/reactivate")
async def reactivate_subscription(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Reactivate a cancelled subscription before period end"""
    if not current_user.subscription or not current_user.subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription to reactivate"
        )
    
    if not current_user.subscription.cancel_at_period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not scheduled for cancellation"
        )
    
    try:
        stripe.Subscription.modify(
            current_user.subscription.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        current_user.subscription.cancel_at_period_end = False
        db.commit()
        
        return {"message": "Subscription reactivated successfully"}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription"
        )


# ============== Customer Portal ==============

class CustomerPortalRequest(BaseModel):
    return_url: str = Field(..., description="URL to return to after managing billing")


@router.post("/portal", response_model=CustomerPortalResponse)
async def create_customer_portal(
    request: CustomerPortalRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Create a Stripe customer portal session for billing management"""
    if not current_user.subscription or not current_user.subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No customer account found"
        )
    
    try:
        portal_url = stripe_service.create_customer_portal_session(
            customer_id=current_user.subscription.stripe_customer_id,
            return_url=request.return_url
        )
        return CustomerPortalResponse(portal_url=portal_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )


# ============== Usage Tracking ==============

@router.get("/usage", response_model=UsageResponse)
async def get_usage_stats(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Get current usage statistics and limits"""
    subscription = current_user.subscription
    
    if not subscription:
        # Free tier defaults
        return UsageResponse(
            stories_used=0,
            stories_limit=3,
            stories_remaining=3,
            individual_credits=0,
            subscription_tier="free",
            can_generate_story=True
        )
    
    # Calculate remaining stories
    can_generate = False
    stories_remaining = 0
    
    if subscription.tier == SubscriptionTier.FREE:
        # Free tier or individual payments
        if subscription.individual_story_credits > 0:
            can_generate = True
            stories_remaining = subscription.individual_story_credits
        else:
            stories_remaining = max(0, subscription.stories_per_month - subscription.stories_created_this_month)
            can_generate = stories_remaining > 0
    else:
        # Subscription plans
        if subscription.stories_per_month == -1:  # Unlimited
            can_generate = True
            stories_remaining = -1
        else:
            stories_remaining = max(0, subscription.stories_per_month - subscription.stories_created_this_month)
            can_generate = stories_remaining > 0
    
    return UsageResponse(
        stories_used=subscription.stories_created_this_month,
        stories_limit=subscription.stories_per_month,
        stories_remaining=stories_remaining,
        individual_credits=subscription.individual_story_credits or 0,
        subscription_tier=subscription.tier.value,
        can_generate_story=can_generate
    )


@router.post("/use-credit")
async def use_story_credit(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Use a story credit (for individual payment users)"""
    subscription = current_user.subscription
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription found"
        )
    
    if subscription.individual_story_credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No story credits available"
        )
    
    # Deduct credit
    subscription.individual_story_credits -= 1
    subscription.stories_created_this_month += 1
    db.commit()
    
    return {
        "message": "Story credit used",
        "credits_remaining": subscription.individual_story_credits
    }


# ============== Webhook Handling ==============

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: DatabaseSession,
    stripe_signature: str = Header(None)
):
    """Handle Stripe webhook events"""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    # Get raw body
    payload = await request.body()
    
    try:
        # Verify webhook signature
        event = stripe_service.verify_webhook_signature(
            payload=payload,
            sig_header=stripe_signature,
            webhook_secret=STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Handle different event types
    event_type = event["type"]
    event_data = event["data"]
    
    try:
        if event_type == "checkout.session.completed":
            # Handle successful checkout
            session = event_data["object"]
            # Process the successful payment
            # This is handled by subscription.created event
            
        elif event_type == "customer.subscription.created":
            stripe_service.handle_subscription_created(event_data, db)
            
        elif event_type == "customer.subscription.updated":
            stripe_service.handle_subscription_updated(event_data, db)
            
        elif event_type == "customer.subscription.deleted":
            stripe_service.handle_subscription_deleted(event_data, db)
            
        elif event_type == "payment_intent.succeeded":
            stripe_service.handle_payment_succeeded(event_data, db)
            
        elif event_type == "invoice.payment_failed":
            stripe_service.handle_invoice_payment_failed(event_data, db)
            
        else:
            print(f"Unhandled event type: {event_type}")
        
        return {"status": "success"}
        
    except Exception as e:
        print(f"Error handling webhook: {str(e)}")
        # Return success to prevent Stripe from retrying
        return {"status": "success", "error": str(e)}


# ============== Payment History ==============

@router.get("/history")
async def get_payment_history(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = 10
):
    """Get payment history for the current user"""
    if not current_user.subscription or not current_user.subscription.stripe_customer_id:
        return {"payments": []}
    
    try:
        # Retrieve payment intents from Stripe
        payment_intents = stripe.PaymentIntent.list(
            customer=current_user.subscription.stripe_customer_id,
            limit=limit
        )
        
        payments = []
        for intent in payment_intents.data:
            if intent.status == "succeeded":
                payments.append({
                    "id": intent.id,
                    "amount": intent.amount,
                    "currency": intent.currency,
                    "description": intent.description,
                    "created": intent.created,
                    "status": intent.status
                })
        
        return {"payments": payments}
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment history"
        )