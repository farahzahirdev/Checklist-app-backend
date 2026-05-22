from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.checklist import Checklist, ChecklistStatus, ChecklistTranslation, ChecklistType
from app.models.reference import Language
from app.models.product_catalog import Product, ProductCategory, ProductKind, ProductStatus
from app.schemas.product_catalog import (
    AdminProductResponse,
    ProductBaseResponse,
    ProductCategoryResponse,
    ProductCategoryWithProductsResponse,
    ProductChecklistLinkResponse,
    ProductChecklistTypeLinkResponse,
    ProductDetailResponse,
    ProductPricingInfo,
    PublicProductCatalogResponse,
)
from app.services.stripe_products import get_stripe_price_for_checklist


DEFAULT_CATEGORY_SEED = (
    ("checklist", "Checklist", "Audit and checklist products", 10),
    ("documentation", "Documentation", "Ready-made documentation templates", 20),
    ("module", "Modules", "Future product modules and builders", 30),
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or f"product-{uuid.uuid4().hex[:8]}"


def _ensure_unique_slug(db: Session, base_slug: str, *, exclude_product_id: uuid.UUID | None = None) -> str:
    candidate = base_slug
    index = 2
    while True:
        query = select(Product.id).where(Product.slug == candidate)
        if exclude_product_id is not None:
            query = query.where(Product.id != exclude_product_id)
        if db.scalar(query) is None:
            return candidate
        candidate = f"{base_slug}-{index}"
        index += 1


def ensure_default_product_categories(db: Session) -> None:
    for code, name, description, display_order in DEFAULT_CATEGORY_SEED:
        category = db.scalar(select(ProductCategory).where(ProductCategory.code == code))
        if category is None:
            db.add(
                ProductCategory(
                    code=code,
                    name=name,
                    description=description,
                    display_order=display_order,
                    is_active=True,
                )
            )
    db.flush()


def _get_category(db: Session, *, category_code: str) -> ProductCategory | None:
    ensure_default_product_categories(db)
    return db.scalar(select(ProductCategory).where(ProductCategory.code == category_code))


def _checklist_product_name(db: Session, checklist: Checklist) -> tuple[str, str | None]:
    translation = db.scalar(
        select(ChecklistTranslation)
        .where(ChecklistTranslation.checklist_id == checklist.id)
        .order_by(ChecklistTranslation.created_at.asc())
        .limit(1)
    )
    if translation and translation.title:
        return translation.title, translation.description
    if checklist.checklist_type:
        return checklist.checklist_type.name, checklist.checklist_type.description
    return f"Checklist {checklist.version}", None


def _checklist_type_link(db: Session, checklist_type_id: uuid.UUID | None) -> ProductChecklistTypeLinkResponse | None:
    if checklist_type_id is None:
        return None
    checklist_type = db.get(ChecklistType, checklist_type_id)
    if checklist_type is None:
        return ProductChecklistTypeLinkResponse(checklist_type_id=checklist_type_id)
    return ProductChecklistTypeLinkResponse(
        checklist_type_id=checklist_type.id,
        checklist_type_code=checklist_type.code,
        checklist_type_name=checklist_type.name,
    )


def _checklist_type_link(db: Session, checklist_type_id: uuid.UUID | None) -> ProductChecklistTypeLinkResponse | None:
    if checklist_type_id is None:
        return None
    checklist_type = db.get(ChecklistType, checklist_type_id)
    if checklist_type is None:
        return ProductChecklistTypeLinkResponse(checklist_type_id=checklist_type_id)
    return ProductChecklistTypeLinkResponse(
        checklist_type_id=checklist_type.id,
        checklist_type_code=checklist_type.code,
        checklist_type_name=checklist_type.name,
    )


def _checklist_product_status(checklist: Checklist) -> str:
    if checklist.status == ChecklistStatus.published:
        return ProductStatus.published.value
    if checklist.status == ChecklistStatus.archived:
        return ProductStatus.archived.value
    return ProductStatus.draft.value


def sync_checklist_product(db: Session, *, checklist: Checklist) -> Product:
    ensure_default_product_categories(db)
    category = _get_category(db, category_code="checklist")
    if category is None:
        raise ValueError("checklist_product_category_missing")

    product = db.scalar(select(Product).where(Product.checklist_id == checklist.id))
    name, description = _checklist_product_name(db, checklist)
    status = _checklist_product_status(checklist)
    base_slug = _slugify(name)

    if product is None:
        product = Product(
            category_id=category.id,
            checklist_id=checklist.id,
            checklist_type_id=checklist.checklist_type_id,
            slug=_ensure_unique_slug(db, base_slug),
            name=name,
            short_description=description,
            description=description,
            product_kind=ProductKind.checklist.value,
            status=status,
        )
        db.add(product)
        db.flush()
        return product

    product.category_id = category.id
    product.checklist_id = checklist.id
    product.checklist_type_id = checklist.checklist_type_id
    product.product_kind = ProductKind.checklist.value
    product.status = status
    product.name = name
    product.short_description = description
    product.description = description
    if not product.slug:
        product.slug = _ensure_unique_slug(db, base_slug, exclude_product_id=product.id)
    return product


def remove_checklist_product(db: Session, *, checklist_id: uuid.UUID) -> None:
    product = db.scalar(select(Product).where(Product.checklist_id == checklist_id))
    if product is not None:
        db.delete(product)


def remove_product(db: Session, *, product_id: uuid.UUID) -> bool:
    product = db.get(Product, product_id)
    if product is None:
        return False
    db.delete(product)
    return True


def _category_response(category: ProductCategory, product_count: int = 0) -> ProductCategoryResponse:
    return ProductCategoryResponse(
        id=category.id,
        code=category.code,
        name=category.name,
        description=category.description,
        display_order=category.display_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        product_count=product_count,
    )


def _product_checklist_link(db: Session, product: Product) -> ProductChecklistLinkResponse | None:
    if product.checklist_id is None:
        return None
    checklist = db.get(Checklist, product.checklist_id)
    if checklist is None:
        return ProductChecklistLinkResponse(checklist_id=product.checklist_id)
    translation = db.scalar(
        select(ChecklistTranslation)
        .where(ChecklistTranslation.checklist_id == checklist.id)
        .order_by(ChecklistTranslation.created_at.asc())
        .limit(1)
    )
    title = translation.title if translation is not None else (checklist.checklist_type.name if checklist.checklist_type else None)
    return ProductChecklistLinkResponse(checklist_id=checklist.id, checklist_title=title, checklist_version=checklist.version)


def _pricing_for_product(db: Session, product: Product) -> ProductPricingInfo | None:
    if product.product_kind != ProductKind.checklist.value or product.checklist_id is None:
        return None
    try:
        price_data = get_stripe_price_for_checklist(db, checklist_id=product.checklist_id)
    except Exception:
        return None
    if not price_data:
        return None
    return ProductPricingInfo(
        price_id=price_data.get("price_id"),
        amount_cents=price_data.get("amount_cents"),
        currency=price_data.get("currency"),
        available=price_data.get("amount_cents") is not None,
    )


def to_admin_product_response(db: Session, product: Product) -> AdminProductResponse:
    category = _category_response(product.category) if product.category is not None else None
    return AdminProductResponse(
        id=product.id,
        category=category,
        parent_product_id=product.parent_product_id,
        checklist=_product_checklist_link(db, product),
        checklist_type=_checklist_type_link(db, product.checklist_type_id),
        slug=product.slug,
        name=product.name,
        short_description=product.short_description,
        description=product.description,
        product_kind=product.product_kind,  # type: ignore[arg-type]
        status=product.status,  # type: ignore[arg-type]
        display_order=product.display_order,
        is_featured=product.is_featured,
        brochure_pdf_url=product.brochure_pdf_url,
        hero_image_url=product.hero_image_url,
        external_url=product.external_url,
        cta_label=product.cta_label,
        created_at=product.created_at,
        updated_at=product.updated_at,
        stripe_product_id=product.stripe_product_id,
        pricing=_pricing_for_product(db, product),
    )


def to_public_product_response(db: Session, product: Product) -> ProductBaseResponse:
    category = _category_response(product.category) if product.category is not None else None
    pricing = _pricing_for_product(db, product)
    return ProductBaseResponse(
        id=product.id,
        category=category,
        parent_product_id=product.parent_product_id,
        checklist=_product_checklist_link(db, product),
        checklist_type=_checklist_type_link(db, product.checklist_type_id),
        slug=product.slug,
        name=product.name,
        short_description=product.short_description,
        description=product.description,
        product_kind=product.product_kind,  # type: ignore[arg-type]
        status=product.status,  # type: ignore[arg-type]
        display_order=product.display_order,
        is_featured=product.is_featured,
        brochure_pdf_url=product.brochure_pdf_url,
        hero_image_url=product.hero_image_url,
        external_url=product.external_url,
        cta_label=product.cta_label,
        created_at=product.created_at,
        updated_at=product.updated_at,
        pricing=pricing,
    )


def list_admin_products(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    category_code: str | None = None,
    status: str | None = None,
) -> tuple[int, list[AdminProductResponse]]:
    ensure_default_product_categories(db)
    query = select(Product).options(joinedload(Product.category), joinedload(Product.checklist), joinedload(Product.checklist_type))
    count_query = select(func.count(Product.id))

    if category_code:
        query = query.join(ProductCategory, Product.category_id == ProductCategory.id).where(ProductCategory.code == category_code)
        count_query = count_query.join(ProductCategory, Product.category_id == ProductCategory.id).where(ProductCategory.code == category_code)
    if status:
        query = query.where(Product.status == status)
        count_query = count_query.where(Product.status == status)
    if search:
        search_term = f"%{search}%"
        search_filter = or_(Product.name.ilike(search_term), Product.slug.ilike(search_term), Product.short_description.ilike(search_term))
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    products = db.scalars(query.order_by(Product.display_order.asc(), Product.created_at.desc()).offset(skip).limit(limit)).all()
    total = db.scalar(count_query) or 0
    return total, [to_admin_product_response(db, product) for product in products]


def list_product_categories(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[ProductCategoryResponse]]:
    ensure_default_product_categories(db)
    categories = db.scalars(
        select(ProductCategory).order_by(ProductCategory.display_order.asc(), ProductCategory.name.asc()).offset(skip).limit(limit)
    ).all()
    total = db.scalar(select(func.count(ProductCategory.id))) or 0
    category_ids = [category.id for category in categories]
    counts: dict[uuid.UUID, int] = {}
    if category_ids:
        rows = db.execute(
            select(Product.category_id, func.count(Product.id)).where(Product.category_id.in_(category_ids)).group_by(Product.category_id)
        ).all()
        counts = {category_id: count for category_id, count in rows}
    return total, [_category_response(category, int(counts.get(category.id, 0))) for category in categories]


def _resolve_category(db: Session, category_code: str) -> ProductCategory | None:
    ensure_default_product_categories(db)
    return db.scalar(select(ProductCategory).where(ProductCategory.code == category_code))


def _auto_create_checklist_for_product(
    db: Session, *, name: str, description: str | None, actor_id: uuid.UUID
) -> Checklist:
    """Create a ChecklistType + Checklist for a new checklist-kind product."""
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", name).strip()
    words = clean_name.split()
    base_code = "_".join(words[:3]).lower() if words else "checklist"
    suffix = uuid.uuid4().hex[:6]
    type_code = f"{base_code}_{suffix}"

    checklist_type = ChecklistType(
        code=type_code,
        name=name,
        description=description,
        is_active=True,
    )
    db.add(checklist_type)
    db.flush()

    checklist = Checklist(
        checklist_type_id=checklist_type.id,
        version="1.0",
        created_by=actor_id,
        updated_by=actor_id,
    )
    checklist.status = ChecklistStatus.draft
    db.add(checklist)
    db.flush()

    language = db.scalar(select(Language).where(Language.is_default.is_(True)).limit(1)) or db.scalar(
        select(Language).limit(1)
    )
    if language is not None:
        db.add(
            ChecklistTranslation(
                checklist_id=checklist.id,
                language_id=language.id,
                title=name,
                description=description or "",
            )
        )
        db.flush()

    return checklist


def create_product(db: Session, *, payload, actor_id: uuid.UUID | None = None) -> Product:
    category = _resolve_category(db, payload.category_code)
    if category is None:
        raise ValueError("product_category_not_found")

    checklist_id = getattr(payload, "checklist_id", None)
    checklist_type_id = payload.checklist_type_id

    # When creating a checklist-kind product with no linked checklist, auto-create one.
    if (
        payload.product_kind == ProductKind.checklist
        and checklist_id is None
        and actor_id is not None
    ):
        auto_checklist = _auto_create_checklist_for_product(
            db,
            name=payload.name,
            description=payload.short_description or payload.description,
            actor_id=actor_id,
        )
        checklist_id = auto_checklist.id
        checklist_type_id = auto_checklist.checklist_type_id

    if checklist_type_id is None and getattr(payload, "checklist_type_code", None):
        checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == payload.checklist_type_code))
        if checklist_type is None:
            raise ValueError("checklist_type_not_found")
        checklist_type_id = checklist_type.id
    if checklist_type_id is None and checklist_id is not None:
        checklist = db.get(Checklist, checklist_id)
        if checklist is not None:
            checklist_type_id = checklist.checklist_type_id
    slug_source = payload.slug if payload.slug else payload.name
    slug = _ensure_unique_slug(db, _slugify(slug_source))
    product = Product(
        category_id=category.id,
        parent_product_id=payload.parent_product_id,
        checklist_id=checklist_id,
        checklist_type_id=checklist_type_id,
        slug=slug,
        name=payload.name,
        short_description=payload.short_description,
        description=payload.description,
        product_kind=payload.product_kind,
        status=payload.status,
        display_order=payload.display_order,
        is_featured=payload.is_featured,
        brochure_pdf_url=payload.brochure_pdf_url,
        hero_image_url=payload.hero_image_url,
        external_url=payload.external_url,
        cta_label=payload.cta_label,
    )
    db.add(product)
    db.flush()
    return product


def update_product(db: Session, product: Product, *, payload) -> Product:
    if payload.category_code is not None:
        category = _resolve_category(db, payload.category_code)
        if category is None:
            raise ValueError("product_category_not_found")
        product.category_id = category.id
    if payload.slug is not None:
        slug_source = payload.slug.strip() or payload.name or product.name
        product.slug = _ensure_unique_slug(db, _slugify(slug_source), exclude_product_id=product.id)
    if payload.checklist_type_id is not None:
        product.checklist_type_id = payload.checklist_type_id
    elif getattr(payload, "checklist_type_code", None) is not None:
        checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == payload.checklist_type_code))
        if checklist_type is None:
            raise ValueError("checklist_type_not_found")
        product.checklist_type_id = checklist_type.id
    elif getattr(payload, "checklist_id", None) is not None:
        checklist = db.get(Checklist, payload.checklist_id)
        if checklist is not None:
            product.checklist_type_id = checklist.checklist_type_id
    if payload.name is not None:
        product.name = payload.name
    if payload.short_description is not None:
        product.short_description = payload.short_description
    if payload.description is not None:
        product.description = payload.description
    if payload.product_kind is not None:
        product.product_kind = payload.product_kind
    if payload.status is not None:
        product.status = payload.status
    if payload.parent_product_id is not None:
        product.parent_product_id = payload.parent_product_id
    if payload.display_order is not None:
        product.display_order = payload.display_order
    if payload.is_featured is not None:
        product.is_featured = payload.is_featured
    if payload.brochure_pdf_url is not None:
        product.brochure_pdf_url = payload.brochure_pdf_url
    if payload.hero_image_url is not None:
        product.hero_image_url = payload.hero_image_url
    if payload.external_url is not None:
        product.external_url = payload.external_url
    if payload.cta_label is not None:
        product.cta_label = payload.cta_label
    return product


def get_product_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
    ensure_default_product_categories(db)
    return db.scalar(select(Product).where(Product.id == product_id).options(joinedload(Product.category), joinedload(Product.checklist), joinedload(Product.checklist_type)))


def get_product_by_slug(db: Session, slug: str) -> Product | None:
    ensure_default_product_categories(db)
    return db.scalar(select(Product).where(Product.slug == slug).options(joinedload(Product.category), joinedload(Product.checklist), joinedload(Product.checklist_type)))


def list_public_catalog(db: Session) -> PublicProductCatalogResponse:
    ensure_default_product_categories(db)
    categories = db.scalars(
        select(ProductCategory)
        .where(ProductCategory.is_active == True)  # noqa: E712
        .order_by(ProductCategory.display_order.asc(), ProductCategory.name.asc())
    ).all()
    products = db.scalars(
        select(Product)
        .options(joinedload(Product.category), joinedload(Product.checklist), joinedload(Product.checklist_type))
        .where(Product.status.in_([ProductStatus.published.value, ProductStatus.coming_soon.value]))
        .order_by(Product.display_order.asc(), Product.created_at.asc())
    ).all()

    # Filter products: exclude checklist products where the underlying checklist is not published
    filtered_products = []
    for product in products:
        if product.product_kind == ProductKind.checklist.value and product.checklist_id is not None:
            checklist = product.checklist
            if checklist is None or checklist.status != ChecklistStatus.published:
                continue
        filtered_products.append(product)

    grouped: list[ProductCategoryWithProductsResponse] = []
    total = 0
    for category in categories:
        category_products = [product for product in filtered_products if product.category_id == category.id]
        total += len(category_products)
        grouped.append(
            ProductCategoryWithProductsResponse(
                category=_category_response(category, len(category_products)),
                products=[to_public_product_response(db, product) for product in category_products],
            )
        )

    return PublicProductCatalogResponse(total=total, categories=grouped)


def public_product_detail(db: Session, slug: str) -> ProductDetailResponse | None:
    product = get_product_by_slug(db, slug)
    if product is None or product.status not in {ProductStatus.published.value, ProductStatus.coming_soon.value}:
        return None
    # Exclude unpublished checklists from public access
    if product.product_kind == ProductKind.checklist.value and product.checklist_id is not None:
        checklist = product.checklist
        if checklist is None or checklist.status != ChecklistStatus.published:
            return None
    pricing = _pricing_for_product(db, product)
    checkout_available = bool(pricing and pricing.available and product.status == ProductStatus.published.value)
    base = to_public_product_response(db, product)
    base_dict = base.model_dump()
    # Remove 'pricing' if present to avoid double-injection
    base_dict.pop('pricing', None)
    return ProductDetailResponse(**base_dict, pricing=pricing, checkout_available=checkout_available)
