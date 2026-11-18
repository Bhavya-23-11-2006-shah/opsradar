from __future__ import annotations

import pandas as pd

from app.services.schema_mapper import infer_file_mapping, normalise_name


def _orders_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Order No": ["ORD-1", "ORD-2"],
            "Customer ID": ["C1", "C2"],
            "SKU": ["P-1", "P-2"],
            "Order Date": ["2026-01-01", "2026-01-02"],
            "Promised Delivery": ["2026-01-04", "2026-01-05"],
            "Fulfilment Centre": ["WH-1", "WH-2"],
            "Delivery City": ["Leeds", "Bristol"],
            "Carrier": ["MetroDash", "ParcelOne"],
            "Order Status": ["delivered", "in transit"],
            "Qty": [1, 2],
            "Order Value": [49.5, 80.0],
        }
    )


def test_detects_orders_and_maps_columns():
    mapping = infer_file_mapping("orders_export.csv", _orders_frame())
    assert mapping.file_type == "orders"
    assert mapping.fields["orderId"] == "Order No"
    assert mapping.fields["productId"] == "SKU"
    assert mapping.fields["promisedDate"] == "Promised Delivery"
    assert mapping.fields["courier"] == "Carrier"
    assert mapping.fields["quantity"] == "Qty"
    assert 0.55 <= mapping.confidence["orderId"] <= 0.99


def test_detects_inventory_from_stock_columns():
    frame = pd.DataFrame(
        {
            "Item Code": ["P-1", "P-2"],
            "Item Name": ["Serum", "Cleanser"],
            "Available Stock": [12, 4],
            "Daily Sales Rate": [3.0, 2.0],
            "Reorder Point": [30, 20],
        }
    )
    mapping = infer_file_mapping("stock_levels.csv", frame)
    assert mapping.file_type == "inventory"
    assert mapping.fields["stock"] == "Available Stock"
    assert mapping.fields["dailySalesRate"] == "Daily Sales Rate"
    assert mapping.fields["reorderLevel"] == "Reorder Point"


def test_detects_complaints_and_reviews():
    complaints = pd.DataFrame(
        {
            "Order Number": ["ORD-1"],
            "Date": ["2026-01-03"],
            "Customer Complaint": ["The box arrived crushed and packaging was torn."],
        }
    )
    mapping = infer_file_mapping("complaints.csv", complaints)
    assert mapping.file_type == "complaints"
    assert mapping.fields["complaintText"] == "Customer Complaint"

    reviews = pd.DataFrame(
        {
            "Order Number": ["ORD-1"],
            "SKU": ["P-1"],
            "Date": ["2026-01-03"],
            "Star Rating": [2],
            "Review Text": ["Delivery was slow and the packaging was damaged."],
        }
    )
    review_mapping = infer_file_mapping("reviews.csv", reviews)
    assert review_mapping.file_type == "reviews"
    assert review_mapping.fields["rating"] == "Star Rating"


def test_fuzzy_and_unknown_columns():
    frame = pd.DataFrame(
        {
            "prodct id": ["P-1"],
            "promisd delivery": ["2026-01-04"],
            "totally unrelated": ["x"],
        }
    )
    mapping = infer_file_mapping("mystery.csv", frame)
    assert mapping.fields.get("productId") == "prodct id"
    assert mapping.fields.get("promisedDate") == "promisd delivery"
    assert "totally unrelated" not in mapping.fields.values()


def test_demo_files_round_trip():
    from app.services.demo_data import build_frames
    from app.services.schema_mapper import suggest_mappings

    frames = build_frames("fashion")
    mappings = {mapping.file_name: mapping for mapping in suggest_mappings(frames)}
    assert mappings["orders.csv"].file_type == "orders"
    assert mappings["deliveries.csv"].file_type == "deliveries"
    assert mappings["complaints.csv"].file_type == "complaints"
    assert mappings["inventory.csv"].file_type == "inventory"
    assert mappings["sales.csv"].file_type == "sales"
    assert mappings["reviews.csv"].file_type == "reviews"
    for mapping in mappings.values():
        assert mapping.file_name in frames
        assert mapping.fields
        assert set(mapping.fields) <= set(mapping.confidence)


def test_normalise_name():
    assert normalise_name("Order_ID (unique)") == "order id unique"
