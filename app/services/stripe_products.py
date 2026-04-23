from __future__ import annotations

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import get_settings
from app.models.checklist import Checklist


def _stripe_required():
    """Initialize Stripe client with required settings."""
    settings = get_settings()
    if stripe is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_package_not_installed",
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_secret_key_missing",
        )
    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_stripe_product_for_checklist(
    db: Session, 
    *, 
    checklist_id: UUID,
    title: str,
    description: str | None = None,
) -> str:
    """
    Create a Stripe product for a checklist.
    
    Returns:
        str: product_id
    """
    stripe_client = _stripe_required()
    
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")
    
    # Create product
    product_data = {
        "name": title,
        "description": description or f"Access to {title} checklist",
        "metadata": {
            "checklist_id": str(checklist_id),
            "version": checklist.version
        }
    }
    
    product = stripe_client.Product.create(**product_data)
    
    # Update checklist with product ID
    checklist.stripe_product_id = product.id
    db.commit()
    db.refresh(checklist)
    
    return product.id


def get_stripe_price_for_checklist(
    db: Session,
    *,
    checklist_id: UUID
) -> dict | None:
    """
    Get the active price for a checklist from Stripe.
    
    Returns:
        dict with price information or None if not found
    """
    stripe_client = _stripe_required()
    
    checklist = db.get(Checklist, checklist_id)
    if checklist is None or not checklist.stripe_product_id:
        return None
    
    try:
        # List active prices for the product
        prices = stripe_client.Price.list(
            product=checklist.stripe_product_id,
            active=True,
            limit=1
        )
        
        if prices.data:
            price = prices.data[0]
            return {
                "price_id": price.id,
                "amount_cents": price.unit_amount,
                "currency": price.currency.upper(),
                "product_id": price.product
            }
    except Exception as e:
        # Log error but don't raise - we'll handle missing prices gracefully
        print(f"Error fetching price for checklist {checklist_id}: {e}")
    
    return None


def update_stripe_product_for_checklist(
    db: Session,
    *,
    checklist_id: UUID,
    title: str | None = None,
    description: str | None = None
) -> str | None:
    """
    Update Stripe product information for a checklist.
    
    Returns:
        Updated product ID or None if not found
    """
    stripe_client = _stripe_required()
    
    checklist = db.get(Checklist, checklist_id)
    if checklist is None or not checklist.stripe_product_id:
        return None
    
    try:
        update_data = {}
        if title:
            update_data["name"] = title
        if description:
            update_data["description"] = description
        
        if update_data:
            product = stripe_client.Product.modify(
                checklist.stripe_product_id,
                **update_data
            )
            return product.id
        
        return checklist.stripe_product_id
    except Exception as e:
        print(f"Error updating product for checklist {checklist_id}: {e}")
        return None
