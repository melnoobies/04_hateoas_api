import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(
    title="Order Management API (PostgreSQL + RMM Level 3)",
    description="REST API Level 3 dengan state transition dinamis gaya PayPal berbasis Neon PostgreSQL.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DATABASE_URL belum diatur di environment variables."
        )
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal terhubung ke PostgreSQL: {str(e)}"
        )

# Inisialisasi tabel orders otomatis jika belum ada
@app.on_event("startup")
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    item VARCHAR(255) NOT NULL,
                    amount INT NOT NULL,
                    status VARCHAR(50) DEFAULT 'CREATED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.close()
    except Exception as e:
        print(f"Warning saat inisialisasi tabel: {e}")

class OrderCreate(BaseModel):
    item: str
    amount: int

@app.get("/", tags=["General"])
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "message": "Order Management API is running on PostgreSQL (RMM Level 3).",
        "links": [
            {"rel": "docs", "href": f"{base_url}/docs", "method": "GET"},
            {"rel": "orders", "href": f"{base_url}/orders", "method": "GET"}
        ]
    }

# 1. READ ALL ORDERS
@app.get("/orders", tags=["Orders"])
def get_all_orders(request: Request):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM orders ORDER BY id ASC;")
            orders = cur.fetchall()

        base_url = str(request.base_url).rstrip("/")
        orders_list = []
        for order in orders:
            order_id = order["id"]
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
    finally:
        conn.close()

# 2. READ ONE ORDER (Fokus Utama Level 3 HATEOAS)
@app.get("/orders/{order_id}", tags=["Orders"])
def get_order(order_id: int, request: Request):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s;", (order_id,))
            order = cur.fetchone()

        if not order:
            raise HTTPException(status_code=404, detail="Order tidak ditemukan")

        base_url = str(request.base_url).rstrip("/")
        links = [
            {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"}
        ]

        # Hypermedia dinamis mengikuti status transaksi di database
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
    finally:
        conn.close()

# 3. CREATE ORDER
@app.post("/orders", status_code=status.HTTP_201_CREATED, tags=["Orders"])
def create_order(body: OrderCreate, request: Request):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO orders (item, amount, status) VALUES (%s, %s, 'CREATED') RETURNING *;",
                (body.item, body.amount)
            )
            new_order = cur.fetchone()

        base_url = str(request.base_url).rstrip("/")
        order_id = new_order["id"]

        return {
            **new_order,
            "links": [
                {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"},
                {"rel": "pay", "href": f"{base_url}/orders/{order_id}/pay", "method": "POST"},
                {"rel": "cancel", "href": f"{base_url}/orders/{order_id}/cancel", "method": "POST"}
            ]
        }
    finally:
        conn.close()

# 4. ACTION: PAY ORDER
@app.post("/orders/{order_id}/pay", tags=["Orders"])
def pay_order(order_id: int, request: Request):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            if order["status"] != "CREATED":
                raise HTTPException(status_code=400, detail=f"Order status '{order['status']}' tidak dapat dibayar")

            cur.execute("UPDATE orders SET status = 'PAID' WHERE id = %s RETURNING *;", (order_id,))
            updated = cur.fetchone()

        base_url = str(request.base_url).rstrip("/")
        return {
            "message": "Pembayaran berhasil diverifikasi",
            **updated,
            "links": [
                {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"},
                {"rel": "refund", "href": f"{base_url}/orders/{order_id}/refund", "method": "POST"},
                {"rel": "all_orders", "href": f"{base_url}/orders", "method": "GET"}
            ]
        }
    finally:
        conn.close()

# 5. ACTION: CANCEL ORDER
@app.post("/orders/{order_id}/cancel", tags=["Orders"])
def cancel_order(order_id: int, request: Request):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Order tidak ditemukan")
            if order["status"] != "CREATED":
                raise HTTPException(status_code=400, detail=f"Order status '{order['status']}' tidak dapat dibatalkan")

            cur.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = %s RETURNING *;", (order_id,))
            updated = cur.fetchone()

        base_url = str(request.base_url).rstrip("/")
        return {
            "message": "Order berhasil dibatalkan",
            **updated,
            "links": [
                {"rel": "self", "href": f"{base_url}/orders/{order_id}", "method": "GET"},
                {"rel": "all_orders", "href": f"{base_url}/orders", "method": "GET"}
            ]
        }
    finally:
        conn.close()