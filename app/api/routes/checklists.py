from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.checklist import Checklist, ChecklistStatus, ChecklistType, ChecklistTranslation
from app.schemas.checklist import CustomerChecklistResponse, ChecklistTypeInfo, ChecklistPricingInfo
from app.services.stripe_products import get_stripe_price_for_checklist
from typing import List

router = APIRouter(prefix="/checklists", tags=["checklists"])

@router.get("/", response_model=List[CustomerChecklistResponse], summary="List published checklists for customers")
def list_customer_checklists(db: Session = Depends(get_db)):
    # Query all published checklists
    checklists = db.query(Checklist).filter(Checklist.status_code_id == 2).all()  # 2 = published
    result = []
    for checklist in checklists:
        # Get type
        checklist_type = db.query(ChecklistType).filter(ChecklistType.id == checklist.checklist_type_id).first()
        # Get translation for title (if any)
        translation = db.query(ChecklistTranslation).filter(ChecklistTranslation.checklist_id == checklist.id).first()
        title = translation.title if translation else f"Checklist v{checklist.version}"
        
        # Get pricing from Stripe - only include checklist if it has an active price
        pricing_info = None
        has_price = False
        try:
            price_data = get_stripe_price_for_checklist(db, checklist_id=checklist.id)
            if price_data:
                pricing_info = ChecklistPricingInfo(
                    price_id=price_data["price_id"],
                    amount_cents=price_data["amount_cents"],
                    currency=price_data["currency"]
                )
                has_price = True
        except Exception as e:
            # Log error but don't fail the response
            print(f"Error fetching price for checklist {checklist.id}: {e}")
        
        # Skip this checklist if it doesn't have an active price
        if not has_price:
            continue
        
        result.append(CustomerChecklistResponse(
            id=checklist.id,
            title=title,
            checklist_type=ChecklistTypeInfo(
                id=checklist_type.id,
                code=checklist_type.code,
                name=checklist_type.name,
                description=checklist_type.description,
            ),
            version=f"v{checklist.version}.0",
            status=checklist.status.value if checklist.status else "",
            created_at=checklist.created_at,
            updated_at=checklist.updated_at,
            pricing=pricing_info,
        ))
    return result
