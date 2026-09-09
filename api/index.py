from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel
from typing import Dict

app = FastAPI(
    title="Order Management API (RMM Level 3 - HATEOAS)",
    description="Implementasi REST API Level 3 dengan navigasi state transisi dinamis gaya PayPal.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Mock in-memory database
orders_db: Dict[str, dict] = {
    "ORD-001": {"id": "ORD-001", "item": "Keyboard Mechanical", "amount": 450000, "status": "CREATED"},
    "ORD-002": {"id": "ORD-002", "item": "Mouse Wireless", "amount": 150000, "status": "PAID"},
    "ORD-003": {"id": "ORD-003", "item": "Monitor 24 Inch", "amount": 1800000, "status": "CANCELLED"}
}

class OrderCreate(BaseModel):
    item: str
    amount: int

@app.get("/", tags=["General"])
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "message": "Order Management API is running (RMM Level 3).",
        "links": [
            {"rel": "docs", "href": f"{base_url}/docs", "method": "GET"},
            {"rel": "orders", "href": f"{base_url}/orders", "method": "GET"}
        ]
    }

# 1. READ ALL ORDERS
@app.get("/orders", tags=["Orders"])
def get_all_orders(request: Request):
    base_url = str(request.base_url).rstrip("/")
    orders_list = []

    for order_id, order in orders_db.items():
        orders_list.append({
            **order,
            "links": [
                {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"}
            ]
        })

    return {
        "total": len(orders_list),
        "data": orders_list,
        "links": [
            {"rel": "self", "href": f"{base_url}/orders", "method": "GET"},
            {"rel": "create", "href": f"{base_url}/orders", "method": "POST"}
        ]
    }

# 2. READ ONE ORDER (Fokus Utama Level 3 HATEOAS)
@app.get("/orders/{order_id}", tags=["Orders"])
def get_order(order_id: str, request: Request):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")

    base_url = str(request.base_url).rstrip("/")
    links = [
        {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"}
    ]

    # Hypermedia dinamis mengikuti status transaksi
    if order["status"] == "CREATED":
        links.append({"rel": "pay", "href": f"{base_url}/orders/{order_id}/pay", "method": "POST"})
        links.append({"rel": "cancel", "href": f"{base_url}/orders/{order_id}/cancel", "method": "POST"})
    elif order["status"] == "PAID":
        links.append({"rel": "refund", "href": f"{base_url}/orders/{order_id}/refund", "method": "POST"})

    links.append({"rel": "all_orders", "href": f"{base_url}/orders", "method": "GET"})

    return {
        **order,
        "links": links
    }

# 3. CREATE ORDER
@app.post("/orders", status_code=status.HTTP_201_CREATED, tags=["Orders"])
def create_order(body: OrderCreate, request: Request):
    new_id = f"ORD-{len(orders_db) + 1:03d}"
    new_order = {
        "id": new_id,
        "item": body.item,
        "amount": body.amount,
        "status": "CREATED"
    }
    orders_db[new_id] = new_order
    base_url = str(request.base_url).rstrip("/")

    return {
        **new_order,
        "links": [
            {"rel": "self", "href": f"{base_url}/orders/{new_id}", "method": "GET"},
            {"rel": "pay", "href": f"{base_url}/orders/{new_id}/pay", "method": "POST"},
            {"rel": "cancel", "href": f"{base_url}/orders/{new_id}/cancel", "method": "POST"}
        ]
    }

# 4. ACTION: PAY ORDER
@app.post("/orders/{order_id}/pay", tags=["Orders"])
def pay_order(order_id: str, request: Request):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    if order["status"] != "CREATED":
        raise HTTPException(status_code=400, detail=f"Order dengan status '{order['status']}' tidak bisa dibayar")

    order["status"] = "PAID"
    base_url = str(request.base_url).rstrip("/")

    return {
        "message": "Pembayaran berhasil diverifikasi",
        **order,
        "links": [
            {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"},
            {"rel": "refund", "href": f"{base_url}/orders/{order_id}/refund", "method": "POST"},
            {"rel": "all_orders", "href": f"{base_url}/orders", "method": "GET"}
        ]
    }

# 5. ACTION: CANCEL ORDER
@app.post("/orders/{order_id}/cancel", tags=["Orders"])
def cancel_order(order_id: str, request: Request):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    if order["status"] != "CREATED":
        raise HTTPException(status_code=400, detail=f"Order dengan status '{order['status']}' tidak bisa dibatalkan")

    order["status"] = "CANCELLED"
    base_url = str(request.base_url).rstrip("/")

    return {
        "message": "Order berhasil dibatalkan",
        **order,
        "links": [
            {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"},
            {"rel": "all_orders", "href": f"{base_url}/orders", "method": "GET"}
        ]
    }