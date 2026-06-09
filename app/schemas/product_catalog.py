from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductDocumentationFile(BaseModel):
    id: str
    url: str
    filename: str
    file_type: Literal["pdf", "docx"]
    uploaded_at: datetime


ProductKind = Literal["checklist", "documentation", "module"]
ProductStatus = Literal["draft", "published", "coming_soon", "archived"]


class ProductPricingInfo(BaseModel):
    price_id: str | None = None
    amount_cents: int | None = None
    currency: str | None = None
    available: bool = False


class ProductCategoryBase(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    display_order: int = 0
    is_active: bool = True


class ProductCategoryCreateRequest(ProductCategoryBase):
    pass


class ProductCategoryUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


class ProductCategoryResponse(ProductCategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    product_count: int = 0


class ProductCreateRequest(BaseModel):
    category_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    short_description: str | None = None
    description: str | None = None
    benefits: str | None = None
    product_kind: ProductKind = "documentation"
    status: ProductStatus = "draft"
    checklist_id: UUID | None = None
    checklist_type_id: UUID | None = None
    checklist_type_code: str | None = Field(default=None, max_length=80)
    parent_product_id: UUID | None = None
    display_order: int = 0
    is_featured: bool = False
    brochure_pdf_url: str | None = None
    hero_image_url: str | None = None
    external_url: str | None = None
    cta_label: str | None = None


class ProductUpdateRequest(BaseModel):
    category_code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    short_description: str | None = None
    description: str | None = None
    benefits: str | None = None
    product_kind: ProductKind | None = None
    status: ProductStatus | None = None
    parent_product_id: UUID | None = None
    checklist_type_id: UUID | None = None
    checklist_type_code: str | None = Field(default=None, max_length=80)
    display_order: int | None = None
    is_featured: bool | None = None
    brochure_pdf_url: str | None = None
    hero_image_url: str | None = None
    external_url: str | None = None
    cta_label: str | None = None


class ProductChecklistLinkResponse(BaseModel):
    checklist_id: UUID | None = None
    checklist_title: str | None = None
    checklist_version: str | None = None


class ProductChecklistTypeLinkResponse(BaseModel):
    checklist_type_id: UUID | None = None
    checklist_type_code: str | None = None
    checklist_type_name: str | None = None


class ProductBaseResponse(BaseModel):
    id: UUID
    category: ProductCategoryResponse | None = None
    parent_product_id: UUID | None = None
    checklist: ProductChecklistLinkResponse | None = None
    checklist_type: ProductChecklistTypeLinkResponse | None = None
    slug: str
    name: str
    short_description: str | None = None
    description: str | None = None
    benefits: str | None = None
    product_kind: ProductKind
    status: ProductStatus
    display_order: int
    is_featured: bool
    brochure_pdf_url: str | None = None
    documentation_files: list[ProductDocumentationFile] = []
    hero_image_url: str | None = None
    external_url: str | None = None
    cta_label: str | None = None
    created_at: datetime
    updated_at: datetime
    pricing: ProductPricingInfo | None = None


class AdminProductResponse(ProductBaseResponse):
    stripe_product_id: str | None = None
    pricing: ProductPricingInfo | None = None


class AdminProductListResponse(BaseModel):
    total: int
    products: list[AdminProductResponse]
    skip: int
    limit: int


class ProductDetailResponse(ProductBaseResponse):
    pricing: ProductPricingInfo | None = None
    checkout_available: bool = False


class ProductCategoryWithProductsResponse(BaseModel):
    category: ProductCategoryResponse
    products: list[ProductBaseResponse]


class PublicProductCatalogResponse(BaseModel):
    total: int
    categories: list[ProductCategoryWithProductsResponse]


class ProductCategoryListResponse(BaseModel):
    total: int
    categories: list[ProductCategoryResponse]
    skip: int
    limit: int
