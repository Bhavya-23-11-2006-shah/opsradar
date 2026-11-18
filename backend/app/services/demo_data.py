"""Seeded demo data with deliberately planted operational problems.

a) damaged-packaging complaints concentrate on one courier/route
b) one product's complaints spike in the last week
c) one product stocks out in about three days
d) one warehouse's late share rises and several open orders will miss their promise
e) duplicates, missing values and inconsistent rows for the quality step
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .. import db
from ..config import DATA_DIR, DEMO_DIR
from ..schemas import FileMapping, SchemaMapping, UploadResponse
from .schema_mapper import suggest_mappings

logger = logging.getLogger(__name__)

SEED = 20260211

WAREHOUSES = [
    {"warehouse": "WH-North", "city": "Leeds"},
    {"warehouse": "WH-Central", "city": "Birmingham"},
    {"warehouse": "WH-South", "city": "Bristol"},
]
CITIES = ["Leeds", "Manchester", "Birmingham", "Bristol", "London", "Glasgow"]
COURIERS = ["MetroDash", "ParcelOne", "SwiftShip", "CityFreight"]

FASHION_PRODUCTS = [
    "Linen Shirt",
    "Cotton Tee",
    "Oversized Hoodie",
    "Denim Jacket",
    "Slim Chinos",
    "Knit Sweater",
    "Pleated Skirt",
    "Wide-Leg Trousers",
    "Silk Blouse",
    "Cargo Pants",
    "Trench Coat",
    "Ribbed Cardigan",
    "Polo Shirt",
    "Track Jacket",
    "Maxi Dress",
    "Tailored Shorts",
    "Socks Pack",
    "Leather Belt",
    "Wool Scarf",
    "Sneakers",
    "Loafers",
    "Baseball Cap",
    "Tote Bag",
    "Lounge Set",
    "Sports Bra",
]

SKINCARE_PRODUCTS = [
    "Hydrating Serum",
    "Vitamin C Serum",
    "Gentle Cleanser",
    "Foaming Cleanser",
    "Night Cream",
    "Day Moisturiser",
    "SPF 50 Sunscreen",
    "Retinol Cream",
    "Niacinamide Toner",
    "Exfoliating Scrub",
    "Sheet Mask Pack",
    "Eye Cream",
    "Lip Balm",
    "Body Lotion",
    "Hair Oil",
    "Scalp Serum",
    "Clay Mask",
    "Rose Water Mist",
    "AHA Peel",
    "Collagen Cream",
    "Aloe Gel",
    "Charcoal Soap",
    "Foot Cream",
    "Hand Cream",
    "Spot Treatment",
]

CATEGORY_CYCLE = ["Tops", "Bottoms", "Outerwear", "Dresses", "Footwear", "Accessories", "Skincare", "Body"]

DAMAGED_TEXTS = [
    "The outer box arrived crushed and the packaging was torn.",
    "Item arrived with damaged packaging, the seal was already broken.",
    "Packaging was smashed in transit and the product box is dented.",
    "The parcel arrived damaged and the packaging had leaked inside.",
    "Box was crushed on one side and the packaging tape was torn open.",
]

LATE_TEXTS = [
    "Delivery was late again and arrived after the promised date.",
    "The order never arrived on time, I had to wait more than a week.",
    "Still waiting for delivery, it is past the promised date.",
    "Delivery was very slow this time and arrived late.",
]

WRONG_TEXTS = [
    "I received the wrong item in my order.",
    "The order contained the wrong product, not what I ordered.",
    "Wrong size was shipped, different from my order.",
    "An item is missing from the box, I received the wrong item count.",
]

QUALITY_TEXTS_FASHION = [
    "The product quality is poor, the fabric faded after one wash.",
    "Faulty stitching on the seam, the quality feels cheap.",
    "The colour ran in the wash and the fabric shrank.",
    "Defective zipper, the product broke after two uses.",
]

QUALITY_TEXTS_SKINCARE = [
    "The serum caused irritation and a rash after two uses.",
    "The product smells off and feels expired.",
    "This cream caused breakouts and redness on my skin.",
    "The texture is gritty, the quality is not what was advertised.",
]

SIZING_TEXTS = [
    "The size runs small, too tight to wear.",
    "Sizing is off, this is too big for the listed size.",
    "The fit is wrong, smaller than expected.",
]

OTHER_TEXTS = [
    "Not happy with this order overall.",
    "Disappointed with the experience, will think twice next time.",
    "The order took a lot of effort to sort out.",
]

REVIEW_TEXTS = [
    "Really pleased, would order again.",
    "Good value for the price.",
    "Exactly as described, fast delivery.",
    "Quality is fine but delivery took a while.",
    "Not impressed with the packaging.",
]


def _products(industry: str) -> list[dict]:
    names = FASHION_PRODUCTS if industry == "fashion" else SKINCARE_PRODUCTS
    prefix = "F" if industry == "fashion" else "S"
    rng = random.Random(SEED + (0 if industry == "fashion" else 1))
    products = []
    for index, name in enumerate(names, start=1):
        products.append(
            {
                "productId": f"{prefix}-P{index:03d}",
                "productName": name,
                "category": CATEGORY_CYCLE[(index - 1) % len(CATEGORY_CYCLE)],
                "price": round(rng.uniform(12, 120), 2),
                "dailyRate": round(rng.uniform(4, 18), 1),
            }
        )
    return products


def _late_probability(day_offset: int, warehouse: str, courier: str) -> float:
    if warehouse == "WH-South" and day_offset <= 14:
        return 0.62
    if warehouse == "WH-South":
        return 0.18
    if warehouse == "WH-North" and courier == "MetroDash":
        return 0.42
    return {"MetroDash": 0.3, "ParcelOne": 0.12, "SwiftShip": 0.16, "CityFreight": 0.2}[courier]


def build_frames(industry: str = "fashion") -> dict[str, pd.DataFrame]:
    rng = random.Random(SEED + (0 if industry == "fashion" else 1))
    today = date.today()
    products = _products(industry)
    spike_product = products[15]
    stockout_product = products[7]
    anomaly_product = products[11]
    weight_by_product = [rng.uniform(0.6, 1.5) for _ in products]

    orders: list[dict] = []
    deliveries: list[dict] = []
    complaints: list[dict] = []
    complaint_counter = 20001

    def add_complaint(order: dict, text: str) -> None:
        nonlocal complaint_counter
        complaints.append(
            {
                "complaintId": f"CMP-{complaint_counter}",
                "orderId": order["orderId"],
                "customerId": order["customerId"],
                "date": order["date"],
                "complaintText": text,
            }
        )
        complaint_counter += 1

    for index in range(800):
        day_offset = rng.randint(0, 55)
        order_date = today - timedelta(days=day_offset)
        product = rng.choices(products, weights=weight_by_product, k=1)[0]
        warehouse = rng.choices(WAREHOUSES, weights=[0.34, 0.36, 0.3], k=1)[0]
        city = warehouse["city"] if rng.random() < 0.55 else rng.choice(CITIES)
        courier = rng.choices(COURIERS, weights=[0.28, 0.25, 0.24, 0.23], k=1)[0]
        quantity = rng.choices([1, 2, 3, 4], weights=[0.5, 0.28, 0.14, 0.08], k=1)[0]
        amount = round(product["price"] * quantity * rng.uniform(0.95, 1.05), 2)
        promised = order_date + timedelta(days=rng.choice([3, 3, 4, 4, 5]))

        if day_offset >= 9:
            status = "delivered"
        elif day_offset >= 6:
            status = rng.choices(["delivered", "in_transit"], weights=[0.8, 0.2], k=1)[0]
        else:
            status = rng.choices(["in_transit", "pending", "shipped"], weights=[0.5, 0.3, 0.2], k=1)[0]

        order = {
            "orderId": f"ORD-{10001 + index}",
            "customerId": f"CUST-{rng.randint(1000, 4600)}",
            "productId": product["productId"],
            "productName": product["productName"],
            "date": order_date.isoformat(),
            "promisedDate": promised.isoformat(),
            "warehouse": warehouse["warehouse"],
            "city": city,
            "courier": courier,
            "status": status,
            "quantity": quantity,
            "amount": amount,
        }
        orders.append(order)

        shipped = order_date + timedelta(days=rng.choice([1, 1, 2]))
        if status == "delivered":
            late = rng.random() < _late_probability(day_offset, warehouse["warehouse"], courier)
            delivered = promised + timedelta(days=rng.randint(1, 4)) if late else promised - timedelta(days=rng.choice([0, 1]))
            delivered_iso = delivered.isoformat()
            if rng.random() < 0.004:
                delivered_iso = (shipped - timedelta(days=1)).isoformat()
            deliveries.append(
                {
                    "orderId": order["orderId"],
                    "shippedDate": shipped.isoformat(),
                    "deliveredDate": delivered_iso,
                    "promisedDate": promised.isoformat(),
                    "warehouse": warehouse["warehouse"],
                    "city": city,
                    "courier": courier,
                    "status": "delivered",
                }
            )
            order["_delivered"] = True
        else:
            deliveries.append(
                {
                    "orderId": order["orderId"],
                    "shippedDate": shipped.isoformat() if status in {"in_transit", "shipped"} else "",
                    "deliveredDate": "",
                    "promisedDate": promised.isoformat(),
                    "warehouse": warehouse["warehouse"],
                    "city": city,
                    "courier": courier,
                    "status": status,
                }
            )
            order["_delivered"] = False

    # Extra open orders on the rising warehouse so the delivery risk is visible today.
    for extra in range(12):
        order_date = today - timedelta(days=rng.randint(2, 6))
        promised = today + timedelta(days=rng.choice([-1, 0, 1, 2]))
        product = rng.choice(products)
        quantity = rng.randint(1, 3)
        order = {
            "orderId": f"ORD-{10001 + len(orders)}",
            "customerId": f"CUST-{rng.randint(1000, 4600)}",
            "productId": product["productId"],
            "productName": product["productName"],
            "date": order_date.isoformat(),
            "promisedDate": promised.isoformat(),
            "warehouse": "WH-South",
            "city": "Bristol" if extra % 2 == 0 else rng.choice(CITIES),
            "courier": rng.choice(COURIERS),
            "status": "in_transit",
            "quantity": quantity,
            "amount": round(product["price"] * quantity, 2),
        }
        orders.append(order)
        deliveries.append(
            {
                "orderId": order["orderId"],
                "shippedDate": (order_date + timedelta(days=1)).isoformat(),
                "deliveredDate": "",
                "promisedDate": promised.isoformat(),
                "warehouse": order["warehouse"],
                "city": order["city"],
                "courier": order["courier"],
                "status": "in_transit",
            }
        )

    delivered_orders = [order for order in orders if order.get("_delivered")]
    bad_route_orders = [
        order
        for order in delivered_orders
        if order["courier"] == "MetroDash" and order["warehouse"] == "WH-North"
    ] or delivered_orders

    # a) damaged packaging concentrated on one courier + route
    for order in bad_route_orders[:60]:
        add_complaint(order, rng.choice(DAMAGED_TEXTS))
    for order in rng.sample(delivered_orders, min(18, len(delivered_orders))):
        add_complaint(order, rng.choice(DAMAGED_TEXTS))

    # b) a sharp complaint spike on one product in the last week
    spike_orders = [order for order in delivered_orders if order["productId"] == spike_product["productId"]]
    if not spike_orders:
        spike_orders = delivered_orders
    for index in range(36):
        # Concentrated into four days so the spike is unmistakable in the trend.
        complaint_date = today - timedelta(days=index % 4)
        order = dict(spike_orders[index % len(spike_orders)])
        order["date"] = complaint_date.isoformat()
        text = (
            rng.choice(QUALITY_TEXTS_SKINCARE if industry == "skincare" else QUALITY_TEXTS_FASHION)
            if index % 4 != 3
            else rng.choice(DAMAGED_TEXTS)
        )
        add_complaint(order, text)

    # Remaining complaint mix
    remaining = 150 - len(complaints)
    for _ in range(max(remaining, 0)):
        order = rng.choice(delivered_orders)
        bucket = rng.choices(
            ["late", "wrong", "quality", "sizing", "other"], weights=[0.3, 0.2, 0.25, 0.15, 0.1], k=1
        )[0]
        if bucket == "late":
            text = rng.choice(LATE_TEXTS)
        elif bucket == "wrong":
            text = rng.choice(WRONG_TEXTS)
        elif bucket == "quality":
            text = rng.choice(QUALITY_TEXTS_SKINCARE if industry == "skincare" else QUALITY_TEXTS_FASHION)
        elif bucket == "sizing":
            text = rng.choice(SIZING_TEXTS)
        else:
            text = rng.choice(OTHER_TEXTS)
        add_complaint(order, text)

    # e) missing complaint text
    for index in rng.sample(range(len(complaints)), 3):
        complaints[index]["complaintText"] = ""

    inventory: list[dict] = []
    for product in products:
        rate = product["dailyRate"]
        if product is stockout_product:
            stock = max(1, round(rate * 3))
            reorder = round(rate * 10)
        else:
            stock = round(rate * rng.uniform(9, 24))
            reorder = round(rate * rng.uniform(5, 8))
        inventory.append(
            {
                "productId": product["productId"],
                "productName": product["productName"],
                "category": product["category"],
                "warehouse": WAREHOUSES[0]["warehouse"],
                "stock": stock,
                "dailySalesRate": rate,
                "reorderLevel": reorder,
            }
        )
    # e) negative stock
    inventory[3]["stock"] = -12
    inventory[9]["stock"] = -4

    sales: list[dict] = []
    for day_offset in range(56, -1, -1):
        sale_date = today - timedelta(days=day_offset)
        for product in products:
            base = product["dailyRate"]
            quantity = max(1, int(base * rng.uniform(0.7, 1.3)))
            if product is anomaly_product and day_offset <= 5:
                quantity = max(1, int(base * 0.15))
            sales.append(
                {
                    "date": sale_date.isoformat(),
                    "productId": product["productId"],
                    "productName": product["productName"],
                    "quantity": quantity,
                    "amount": round(quantity * product["price"], 2),
                }
            )

    reviews: list[dict] = []
    for index in range(40):
        order = rng.choice(delivered_orders)
        product_id = order["productId"]
        rating = (
            rng.choices([1, 2, 3, 4, 5], weights=[0.12, 0.1, 0.18, 0.3, 0.3], k=1)[0]
            if product_id != spike_product["productId"]
            else rng.choices([1, 2, 3, 4, 5], weights=[0.45, 0.25, 0.15, 0.1, 0.05], k=1)[0]
        )
        reviews.append(
            {
                "reviewId": f"REV-{30001 + index}",
                "orderId": order["orderId"],
                "productId": product_id,
                "date": order["date"],
                "rating": rating,
                "reviewText": rng.choice(REVIEW_TEXTS),
            }
        )
    reviews[0]["rating"] = 0  # e) impossible rating

    orders_frame = pd.DataFrame(orders).drop(columns=["_delivered"], errors="ignore")
    # e) exact duplicates
    orders_frame = pd.concat(
        [orders_frame, orders_frame.sample(n=8, random_state=7)], ignore_index=True
    )
    # e) unknown productIds and missing amounts/status
    for index in orders_frame.sample(n=5, random_state=11).index:
        orders_frame.at[index, "productId"] = "P-UNKNOWN"
    for index in orders_frame.sample(n=6, random_state=13).index:
        orders_frame.at[index, "amount"] = None
    for index in orders_frame.sample(n=5, random_state=17).index:
        orders_frame.at[index, "status"] = None

    deliveries_frame = pd.DataFrame(deliveries)
    for index in deliveries_frame.sample(n=3, random_state=19).index:
        order_date = today - timedelta(days=40)
        deliveries_frame.at[index, "deliveredDate"] = (order_date - timedelta(days=1)).isoformat()

    return {
        "orders.csv": orders_frame,
        "deliveries.csv": deliveries_frame,
        "complaints.csv": pd.DataFrame(complaints),
        "inventory.csv": pd.DataFrame(inventory),
        "sales.csv": pd.DataFrame(sales),
        "reviews.csv": pd.DataFrame(reviews),
    }


def write_demo_files(frames: dict[str, pd.DataFrame], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(target / name, index=False)


def _upload_files(frames: dict[str, pd.DataFrame]) -> list[dict]:
    mappings = suggest_mappings(frames)
    entries = []
    for mapping in mappings:
        frame = frames[mapping.file_name]
        entries.append(
            {
                "name": mapping.file_name,
                "detectedType": mapping.file_type,
                "rows": int(len(frame)),
                "columns": [str(column) for column in frame.columns],
                "suggestedMapping": mapping.model_dump(by_alias=True),
            }
        )
    return entries


def generate_dataset(industry: str = "fashion") -> dict:
    frames = build_frames(industry)
    write_demo_files(frames, DEMO_DIR)

    dataset_id = f"demo-{industry}-{uuid.uuid4().hex[:10]}"
    raw_dir = DATA_DIR / "datasets" / dataset_id / "raw"
    write_demo_files(frames, raw_dir)

    mappings: list[FileMapping] = suggest_mappings(frames)
    db.create_dataset(dataset_id, industry=industry, files=_upload_files(frames))
    db.update_dataset(
        dataset_id,
        mapping_json=SchemaMapping(files=mappings).model_dump_json(by_alias=True),
    )
    logger.info("demo dataset %s written with %s files", dataset_id, len(frames))

    response = UploadResponse(
        dataset_id=dataset_id,
        files=[_upload_files(frames)[index] for index in range(len(mappings))],  # type: ignore[arg-type]
    )
    return response.model_dump(by_alias=True)
