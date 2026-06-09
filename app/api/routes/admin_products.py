from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_admin_only
from app.db.session import get_db
from app.models.product_catalog import Product, ProductCategory
from app.schemas.product_catalog import (
    AdminProductListResponse,
    AdminProductResponse,
    ProductCategoryCreateRequest,
    ProductCategoryListResponse,
    ProductCategoryResponse,
    ProductCategoryUpdateRequest,
    ProductCreateRequest,
    ProductUpdateRequest,
)
from app.services.product_catalog import (
    create_product,
    ensure_default_product_categories,
    get_product_by_id,
    list_admin_products,
    list_product_categories,
    remove_product,
    remove_checklist_product,
    to_admin_product_response,
    update_product,
)

router = APIRouter(prefix="/admin/products", tags=["admin-products"])


@router.get("/categories", response_model=ProductCategoryListResponse)
def admin_list_product_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> ProductCategoryListResponse:
    total, categories = list_product_categories(db, skip=skip, limit=limit)
    return {"total": total, "categories": categories, "skip": skip, "limit": limit}


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
def admin_create_product_category(
    payload: ProductCategoryCreateRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> ProductCategoryResponse:
    ensure_default_product_categories(db)
    existing = db.scalar(select(ProductCategory).where(ProductCategory.code == payload.code))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_category_code_exists")
    category = ProductCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    count = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    return ProductCategoryResponse(
        id=category.id,
        code=category.code,
        name=category.name,
        description=category.description,
        display_order=category.display_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        product_count=count,
    )


@router.patch("/categories/{category_id}", response_model=ProductCategoryResponse)
def admin_update_product_category(
    category_id: UUID,
    payload: ProductCategoryUpdateRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> ProductCategoryResponse:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product_category_not_found")
    if payload.code is not None and payload.code != category.code:
        conflict = db.scalar(select(ProductCategory).where(ProductCategory.code == payload.code))
        if conflict is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_category_code_exists")
        category.code = payload.code
    if payload.name is not None:
        category.name = payload.name
    if payload.description is not None:
        category.description = payload.description
    if payload.display_order is not None:
        category.display_order = payload.display_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
    db.commit()
    db.refresh(category)
    count = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    return ProductCategoryResponse(
        id=category.id,
        code=category.code,
        name=category.name,
        description=category.description,
        display_order=category.display_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        product_count=count,
    )


@router.get("", response_model=AdminProductListResponse)
def admin_list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    category_code: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> AdminProductListResponse:
    total, products = list_admin_products(
        db,
        skip=skip,
        limit=limit,
        search=search,
        category_code=category_code,
        status=status_filter,
    )
    return {"total": total, "products": products, "skip": skip, "limit": limit}


@router.post("", response_model=AdminProductResponse, status_code=status.HTTP_201_CREATED)
def admin_create_product(
    payload: ProductCreateRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> AdminProductResponse:
    product = create_product(db, payload=payload, actor_id=_admin.id)
    db.commit()
    db.refresh(product)
    return to_admin_product_response(db, product)


@router.get("/{product_id}", response_model=AdminProductResponse)
def admin_get_product(
    product_id: UUID,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> AdminProductResponse:
    product = get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product_not_found")
    return to_admin_product_response(db, product)


@router.patch("/{product_id}", response_model=AdminProductResponse)
def admin_update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> AdminProductResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product_not_found")
    update_product(db, product, payload=payload)
    db.commit()
    db.refresh(product)
    return to_admin_product_response(db, product)


@router.delete("/checklist/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_checklist_product(
    checklist_id: UUID,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> None:
    remove_checklist_product(db, checklist_id=checklist_id)
    db.commit()


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_product(
    product_id: UUID,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> None:
    removed = remove_product(db, product_id=product_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product_not_found")
    db.commit()
