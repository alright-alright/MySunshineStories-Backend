"""
Stripe payment processing service
"""
import stripe
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json

from app.core.config import settings
from app.models.database_models import User, Subscription, SubscriptionTier
from app.schemas.subscription import SubscriptionUpdate

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Subscription Plans Configuration
SUBSCRIPTION_PLANS = {
    "individual": {
        "name": "Individual",
        "price_per_story": 500,  # $5.00 in cents
        "type": "per_use",
        "features": {
            "stories_per_month": 1,  # Pay per story
            "sunshines_limit": 1,
            "has_pdf_export": True,
            "has_image_generation": True,
            "has_custom_illustrations": False,
            "has_multi_language": False,
            "has_api_access": False
        }
    },
    "plus": {
        "name": "Plus",
        "price_monthly": 1000,  # $10.00 in cents
        "stripe_price_id": "price_plus_monthly",  # Replace with actual Stripe price ID
        "type": "subscription",
        "features": {
            "stories_per_month": 10,
            "sunshines_limit": 3,
            "has_pdf_export": True,
            "has_image_generation": True,
            "has_custom_illustrations": False,
            "has_multi_language": True,
            "has_api_access": False
        }
    },
    "unlimited": {
        "name": "Unlimited",
        "price_monthly": 3000,  # $30.00 in cents
        "stripe_price_id": "price_unlimited_monthly",  # Replace with actual Stripe price ID
        "type": "subscription",
        "features": {
            "stories_per_month": -1,  # Unlimited
            "sunshines_limit": -1,  # Unlimited
            "has_pdf_export": True,
            "has_image_generation": True,
            "has_custom_illustrations": True,
            "has_multi_language": True,
            "has_api_access": True
        }
    }
}


class StripeService:
    """Service for handling Stripe payments and subscriptions"""
    
    @staticmethod
    def create_customer(user: User) -> str:
        """Create a Stripe customer for a user"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name or user.username,
                metadata={
                    "user_id": user.id
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create Stripe customer: {str(e)}")
    
    @staticmethod
    def get_or_create_customer(user: User, db: Session) -> str:
        """Get existing or create new Stripe customer"""
        if user.subscription and user.subscription.stripe_customer_id:
            return user.subscription.stripe_customer_id
        
        # Create new customer
        customer_id = StripeService.create_customer(user)
        
        # Update subscription record
        if user.subscription:
            user.subscription.stripe_customer_id = customer_id
            db.commit()
        
        return customer_id
    
    @staticmethod
    def create_checkout_session(
        user: User,
        plan: str,
        success_url: str,
        cancel_url: str,
        db: Session
    ) -> str:
        """Create a Stripe checkout session for subscription"""
        if plan not in SUBSCRIPTION_PLANS:
            raise ValueError(f"Invalid subscription plan: {plan}")
        
        plan_config = SUBSCRIPTION_PLANS[plan]
        
        if plan_config["type"] != "subscription":
            raise ValueError(f"Plan {plan} is not a subscription plan")
        
        customer_id = StripeService.get_or_create_customer(user, db)
        
        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": plan_config["stripe_price_id"],
                    "quantity": 1
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": user.id,
                    "plan": plan
                }
            )
            return checkout_session.url
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create checkout session: {str(e)}")
    
    @staticmethod
    def create_payment_intent(
        user: User,
        amount: int,
        description: str,
        db: Session
    ) -> Dict[str, Any]:
        """Create a payment intent for one-time payment"""
        customer_id = StripeService.get_or_create_customer(user, db)
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency="usd",
                customer=customer_id,
                description=description,
                metadata={
                    "user_id": user.id,
                    "type": "individual_story"
                }
            )
            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": amount
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create payment intent: {str(e)}")
    
    @staticmethod
    def cancel_subscription(subscription_id: str, immediate: bool = False) -> bool:
        """Cancel a Stripe subscription"""
        try:
            if immediate:
                stripe.Subscription.delete(subscription_id)
            else:
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            return True
        except stripe.error.StripeError as e:
            print(f"Failed to cancel subscription: {str(e)}")
            return False
    
    @staticmethod
    def update_subscription(
        subscription_id: str,
        new_price_id: str
    ) -> Optional[Dict[str, Any]]:
        """Update subscription to a different plan"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update the subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id
                }],
                proration_behavior="create_prorations"
            )
            
            return {
                "subscription_id": updated_subscription.id,
                "status": updated_subscription.status,
                "current_period_end": updated_subscription.current_period_end
            }
        except stripe.error.StripeError as e:
            print(f"Failed to update subscription: {str(e)}")
            return None
    
    @staticmethod
    def create_customer_portal_session(
        customer_id: str,
        return_url: str
    ) -> str:
        """Create a customer portal session for billing management"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create portal session: {str(e)}")
    
    @staticmethod
    def retrieve_subscription(subscription_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve subscription details from Stripe"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at
            }
        except stripe.error.StripeError as e:
            print(f"Failed to retrieve subscription: {str(e)}")
            return None
    
    @staticmethod
    def handle_subscription_created(event_data: Dict[str, Any], db: Session):
        """Handle subscription.created webhook event"""
        subscription_data = event_data["object"]
        customer_id = subscription_data["customer"]
        
        # Find user by customer ID
        subscription = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()
        
        if subscription:
            # Determine tier based on price
            price_id = subscription_data["items"]["data"][0]["price"]["id"]
            tier = StripeService._get_tier_from_price_id(price_id)
            
            # Update subscription
            subscription.stripe_subscription_id = subscription_data["id"]
            subscription.tier = tier
            subscription.status = "active"
            subscription.current_period_start = datetime.fromtimestamp(
                subscription_data["current_period_start"], tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                subscription_data["current_period_end"], tz=timezone.utc
            )
            
            # Update features based on tier
            plan_features = StripeService._get_plan_features_by_tier(tier)
            for key, value in plan_features.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            db.commit()
    
    @staticmethod
    def handle_subscription_updated(event_data: Dict[str, Any], db: Session):
        """Handle subscription.updated webhook event"""
        subscription_data = event_data["object"]
        
        # Find subscription by Stripe ID
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_data["id"]
        ).first()
        
        if subscription:
            # Update subscription status
            subscription.status = subscription_data["status"]
            subscription.cancel_at_period_end = subscription_data["cancel_at_period_end"]
            
            if subscription_data["canceled_at"]:
                subscription.cancelled_at = datetime.fromtimestamp(
                    subscription_data["canceled_at"], tz=timezone.utc
                )
            
            # Update period dates
            subscription.current_period_start = datetime.fromtimestamp(
                subscription_data["current_period_start"], tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                subscription_data["current_period_end"], tz=timezone.utc
            )
            
            db.commit()
    
    @staticmethod
    def handle_subscription_deleted(event_data: Dict[str, Any], db: Session):
        """Handle subscription.deleted webhook event"""
        subscription_data = event_data["object"]
        
        # Find subscription by Stripe ID
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_data["id"]
        ).first()
        
        if subscription:
            # Downgrade to free tier
            subscription.tier = SubscriptionTier.FREE
            subscription.status = "cancelled"
            subscription.stripe_subscription_id = None
            subscription.cancelled_at = datetime.now(timezone.utc)
            
            # Reset to free tier features
            free_features = StripeService._get_plan_features_by_tier(SubscriptionTier.FREE)
            for key, value in free_features.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            db.commit()
    
    @staticmethod
    def handle_payment_succeeded(event_data: Dict[str, Any], db: Session):
        """Handle payment_intent.succeeded webhook event"""
        payment_intent = event_data["object"]
        
        # Check if this is an individual story payment
        if payment_intent.get("metadata", {}).get("type") == "individual_story":
            user_id = payment_intent["metadata"]["user_id"]
            
            # Find user's subscription
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if subscription:
                # Add credit for one story
                subscription.individual_story_credits = (
                    subscription.individual_story_credits or 0
                ) + 1
                db.commit()
    
    @staticmethod
    def handle_invoice_payment_failed(event_data: Dict[str, Any], db: Session):
        """Handle invoice.payment_failed webhook event"""
        invoice = event_data["object"]
        subscription_id = invoice["subscription"]
        
        # Find subscription
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if subscription:
            subscription.status = "payment_failed"
            db.commit()
    
    @staticmethod
    def _get_tier_from_price_id(price_id: str) -> SubscriptionTier:
        """Map Stripe price ID to subscription tier"""
        for plan_key, plan_config in SUBSCRIPTION_PLANS.items():
            if plan_config.get("stripe_price_id") == price_id:
                if plan_key == "plus":
                    return SubscriptionTier.BASIC
                elif plan_key == "unlimited":
                    return SubscriptionTier.PREMIUM
        return SubscriptionTier.FREE
    
    @staticmethod
    def _get_plan_features_by_tier(tier: SubscriptionTier) -> Dict[str, Any]:
        """Get plan features for a subscription tier"""
        if tier == SubscriptionTier.BASIC:
            return SUBSCRIPTION_PLANS["plus"]["features"]
        elif tier == SubscriptionTier.PREMIUM:
            return SUBSCRIPTION_PLANS["unlimited"]["features"]
        else:
            return {
                "stories_per_month": 3,
                "sunshines_limit": 1,
                "has_pdf_export": False,
                "has_image_generation": True,
                "has_custom_illustrations": False,
                "has_multi_language": False,
                "has_api_access": False
            }
    
    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        sig_header: str,
        webhook_secret: str
    ) -> Dict[str, Any]:
        """Verify Stripe webhook signature"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")
    
    @staticmethod
    def create_usage_record(
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[int] = None
    ) -> bool:
        """Create usage record for metered billing"""
        try:
            stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=timestamp or int(datetime.now().timestamp())
            )
            return True
        except stripe.error.StripeError as e:
            print(f"Failed to create usage record: {str(e)}")
            return False


# Global instance
stripe_service = StripeService()