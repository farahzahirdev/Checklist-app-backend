from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.checklist import Checklist, ChecklistStatus, ChecklistType, ChecklistTranslation
from app.models.reference import Language
from app.services.stripe_products import get_stripe_price_for_checklist
from app.schemas.checklist import CustomerChecklistListResponse, CustomerChecklistResponse, ChecklistTypeInfo, ChecklistPricingInfo
from typing import List
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

router = APIRouter(prefix="/checklists", tags=["checklists"])

@router.get("/", response_model=CustomerChecklistListResponse, summary="List published checklists for customers")
def list_customer_checklists(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for titles"),
    db: Session = Depends(get_db),
):
    lang_code = get_language_code(request, db)
    query = db.query(Checklist).filter(Checklist.status_code_id == 2)

    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(ChecklistTranslation, ChecklistTranslation.checklist_id == Checklist.id).filter(
            or_(
                ChecklistTranslation.title.ilike(search_term),
                ChecklistTranslation.description.ilike(search_term),
            )
        )

    sort_column = Checklist.created_at
    if sort_by == "updated_at":
        sort_column = Checklist.updated_at
    elif sort_by == "version":
        sort_column = Checklist.version
    elif sort_by == "status":
        sort_column = Checklist.status

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    checklists = query.offset(skip).limit(limit).all()

    result = []
    for checklist in checklists:
        checklist_type = db.query(ChecklistType).filter(ChecklistType.id == checklist.checklist_type_id).first()
        # Get language record from lang_code
        language = db.query(Language).filter(Language.code == lang_code, Language.is_active == True).first()
        if language:
            translation = db.query(ChecklistTranslation).filter(
                ChecklistTranslation.checklist_id == checklist.id, 
                ChecklistTranslation.language_id == language.id
            ).first()
        else:
            translation = None
        title = translation.title if translation else f"Checklist v{checklist.version}"
        
        # Get pricing from Stripe - only include checklist if it has an active price above $0.50
        pricing_info = None
        has_valid_price = False
        try:
            price_data = get_stripe_price_for_checklist(db, checklist_id=checklist.id)
            if price_data:
                # Check if price meets minimum amount requirement ($0.50 USD = 50 cents)
                if price_data["currency"].upper() == "USD" and price_data["amount_cents"] >= 50:
                    pricing_info = ChecklistPricingInfo(
                        price_id=price_data["price_id"],
                        amount_cents=price_data["amount_cents"],
                        currency=price_data["currency"]
                    )
                    has_valid_price = True
                else:
                    # Price exists but is too low - skip this checklist
                    print(f"Checklist {checklist.id} price ${price_data['amount_cents']/100:.2f} is below minimum $0.50")
        except Exception as e:
            # Log error but don't fail the response
            print(f"Error fetching price for checklist {checklist.id}: {e}")
        
        # Skip this checklist if it doesn't have a valid price (above minimum)
        if not has_valid_price:
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

    return {"total": total, "checklists": result, "skip": skip, "limit": limit}
