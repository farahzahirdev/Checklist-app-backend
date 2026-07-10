from app.models.checklist import ChecklistStatus
from app.models.media import Media, MediaType, MalwareScanStatus


API_PREFIX = "/api/api/v1"


def _admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


def _publish_checklist(sample_checklist, db) -> None:
    sample_checklist.status = ChecklistStatus.published
    db.commit()
    db.refresh(sample_checklist)


def test_public_products_catalog_and_detail(client, db, sample_checklist):
    _publish_checklist(sample_checklist, db)

    catalog_response = client.get(f"{API_PREFIX}/products")
    assert catalog_response.status_code == 200
    payload = catalog_response.json()

    assert "categories" in payload
    checklist_category = next((c for c in payload["categories"] if c["category"]["code"] == "checklist"), None)
    assert checklist_category is not None
    assert len(checklist_category["products"]) >= 1

    product = next(
        p for p in checklist_category["products"]
        if p["checklist"] and p["checklist"]["checklist_id"] == str(sample_checklist.id)
    )
    assert product["checklist_type"]["checklist_type_id"] == str(sample_checklist.checklist_type_id)

    detail_response = client.get(f"{API_PREFIX}/products/{product['slug']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["id"] == product["id"]
    assert detail["checklist"]["checklist_id"] == str(sample_checklist.id)
    assert detail["checklist_type"]["checklist_type_id"] == str(sample_checklist.checklist_type_id)


def test_admin_sync_and_list_products(client, db, admin_token, sample_checklist):
    _publish_checklist(sample_checklist, db)

    sync_response = client.post(f"{API_PREFIX}/admin/products/sync-checklists", headers=_admin_headers(admin_token))
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()

    synced = next(
        p for p in sync_payload["products"]
        if p["checklist"] and p["checklist"]["checklist_id"] == str(sample_checklist.id)
    )
    assert synced["product_kind"] == "checklist"
    assert synced["checklist_type"]["checklist_type_id"] == str(sample_checklist.checklist_type_id)

    list_response = client.get(f"{API_PREFIX}/admin/products", headers=_admin_headers(admin_token))
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] >= 1


def test_admin_category_create_and_update(client, admin_token):
    create_response = client.post(
            f"{API_PREFIX}/admin/products/categories",
        headers=_admin_headers(admin_token),
        json={
            "code": "future_tools",
            "name": "Future Tools",
            "description": "Upcoming tools",
            "display_order": 50,
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    update_response = client.patch(
        f"{API_PREFIX}/admin/products/categories/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"name": "Future Tooling", "display_order": 55},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Future Tooling"
    assert updated["display_order"] == 55



def test_admin_create_update_get_documentation_product_with_checklist_type(client, db, admin_token, sample_checklist):
    create_response = client.post(
        f"{API_PREFIX}/admin/products",
        headers=_admin_headers(admin_token),
        json={
            "category_code": "documentation",
            "name": "Document Template YX1",
            "product_kind": "documentation",
            "status": "coming_soon",
            "checklist_type_code": sample_checklist.checklist_type.code,
            "short_description": "Template set",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    assert created["checklist_type"]["checklist_type_id"] == str(sample_checklist.checklist_type_id)
    assert created["checklist_type"]["checklist_type_code"] == sample_checklist.checklist_type.code
    assert created["short_description"] == "Template set"

    get_response = client.get(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
    )
    assert get_response.status_code == 200

    update_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"status": "published", "is_featured": True, "short_description": "Updated template set"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "published"
    assert updated["is_featured"] is True
    assert updated["short_description"] == "Updated template set"

    clear_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"short_description": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["short_description"] is None


def test_admin_product_documentation_files_external_url_and_cta(client, db, admin_token, admin_user):
    media = Media(
        filename="doc.pdf",
        original_filename="policy.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        file_path="uploads/media/doc.pdf",
        media_type=MediaType.document,
        sha256="abc123",
        scan_status=MalwareScanStatus.clean,
        encryption_status="unencrypted",
        uploaded_by=admin_user.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    create_response = client.post(
        f"{API_PREFIX}/admin/products",
        headers=_admin_headers(admin_token),
        json={
            "category_code": "documentation",
            "name": "Policy Pack",
            "product_kind": "documentation",
            "status": "published",
            "external_url": "https://example.com/buy",
            "cta_label": "Purchase now",
            "documentation_files": [
                {
                    "url": f"/media/{media.id}/direct",
                    "filename": "policy.pdf",
                    "file_type": "pdf",
                }
            ],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["external_url"] == "https://example.com/buy"
    assert created["cta_label"] == "Purchase now"
    assert len(created["documentation_files"]) == 1
    assert created["documentation_files"][0]["filename"] == "policy.pdf"

    get_response = client.get(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
    )
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert len(fetched["documentation_files"]) == 1

    update_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={
            "external_url": "https://example.com/updated",
            "cta_label": "Buy updated",
            "documentation_files": [],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["external_url"] == "https://example.com/updated"
    assert updated["cta_label"] == "Buy updated"
    assert updated["documentation_files"] == []

    public_response = client.get(f"{API_PREFIX}/products/{created['slug']}")
    assert public_response.status_code == 200
    public_detail = public_response.json()
    assert public_detail["external_url"] == "https://example.com/updated"
    assert public_detail["cta_label"] == "Buy updated"
    assert public_detail["documentation_files"] == []


def test_admin_delete_checklist_product(client, db, admin_token, sample_checklist):
    _publish_checklist(sample_checklist, db)

    sync_response = client.post(f"{API_PREFIX}/admin/products/sync-checklists", headers=_admin_headers(admin_token))
    assert sync_response.status_code == 200

    delete_response = client.delete(
        f"{API_PREFIX}/admin/products/checklist/{sample_checklist.id}",
        headers=_admin_headers(admin_token),
    )
    assert delete_response.status_code == 204

    list_response = client.get(f"{API_PREFIX}/admin/products", headers=_admin_headers(admin_token))
    assert list_response.status_code == 200
    products = list_response.json()["products"]

    checklist_product_ids = [p["checklist"]["checklist_id"] for p in products if p["checklist"]]
    assert str(sample_checklist.id) not in checklist_product_ids


def test_admin_update_product_kind_links_checklist(client, db, admin_token):
    create_response = client.post(
        f"{API_PREFIX}/admin/products",
        headers=_admin_headers(admin_token),
        json={
            "category_code": "documentation",
            "name": "Kind Switch Doc",
            "product_kind": "documentation",
            "status": "published",
            "short_description": "Starts as documentation",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["checklist"] is None

    to_checklist_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"product_kind": "checklist", "category_code": "checklist"},
    )
    assert to_checklist_response.status_code == 200
    checklist_product = to_checklist_response.json()
    assert checklist_product["product_kind"] == "checklist"
    assert checklist_product["checklist"] is not None
    assert checklist_product["checklist"]["checklist_id"] is not None

    catalog_response = client.get(f"{API_PREFIX}/products")
    assert catalog_response.status_code == 200
    checklist_products = [
        p
        for group in catalog_response.json()["categories"]
        for p in group["products"]
        if p["product_kind"] == "checklist"
    ]
    assert any(p["id"] == checklist_product["id"] for p in checklist_products)

    to_documentation_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"product_kind": "documentation", "category_code": "documentation"},
    )
    assert to_documentation_response.status_code == 200
    documentation_product = to_documentation_response.json()
    assert documentation_product["product_kind"] == "documentation"
    assert documentation_product["checklist"] is None


def test_admin_update_existing_checklist_product_without_link_auto_creates_checklist(
    client, db, admin_token
):
    from app.models.product_catalog import Product

    create_response = client.post(
        f"{API_PREFIX}/admin/products",
        headers=_admin_headers(admin_token),
        json={
            "category_code": "checklist",
            "name": "Orphan Checklist Product",
            "product_kind": "checklist",
            "status": "published",
            "short_description": "Will lose checklist link in DB",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    product = db.get(Product, created["id"])
    assert product is not None
    product.checklist_id = None
    db.commit()

    update_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"short_description": "Re-linked on save"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["checklist"] is not None
    assert updated["checklist"]["checklist_id"] is not None
