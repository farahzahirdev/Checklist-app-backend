from app.models.checklist import ChecklistStatus


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

    get_response = client.get(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
    )
    assert get_response.status_code == 200

    update_response = client.patch(
        f"{API_PREFIX}/admin/products/{created['id']}",
        headers=_admin_headers(admin_token),
        json={"status": "published", "is_featured": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "published"
    assert updated["is_featured"] is True


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
