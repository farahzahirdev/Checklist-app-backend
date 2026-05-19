from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.checklist import Checklist
from app.schemas.product_catalog import ProductDetailResponse, PublicProductCatalogResponse
from app.services.product_catalog import list_public_catalog, public_product_detail, sync_checklist_product

router = APIRouter(prefix="/products", tags=["products"])


def _sync_checklist_products(db: Session) -> None:
    for checklist in db.scalars(select(Checklist)).all():
        sync_checklist_product(db, checklist=checklist)
    db.commit()


@router.get("", response_model=PublicProductCatalogResponse)
def public_products(db: Session = Depends(get_db)) -> PublicProductCatalogResponse:
    _sync_checklist_products(db)
    return list_public_catalog(db)


@router.get("/{slug}", response_model=ProductDetailResponse)
def public_product_detail_route(slug: str, db: Session = Depends(get_db)) -> ProductDetailResponse:
    _sync_checklist_products(db)
    product = public_product_detail(db, slug)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product_not_found")
    return product
