import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import strawberry
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

# Setup tabel awal dan data dummy jika belum ada
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    price INT NOT NULL,
                    stock INT DEFAULT 0,
                    description TEXT
                );
            """)
            # Seed data kategori jika kosong
            cur.execute("SELECT COUNT(*) FROM categories;")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO categories (id, name) VALUES 
                    (1, 'Electronics'),
                    (2, 'Accessories');
                    INSERT INTO products (name, price, stock, description, category_id) VALUES
                    ('Mechanical Keyboard', 750000, 15, 'RGB Blue Switch', 1),
                    ('Wireless Mouse', 250000, 30, 'Rechargeable Silent Click', 1),
                    ('Deskmat XXL', 120000, 50, 'Anti-slip 900x400mm', 2);
                """)
        conn.close()
    except Exception as e:
        print(f"DB Init Warning: {e}")

# ==========================================
# Definisi GraphQL Types
# ==========================================
@strawberry.type
class Category:
    id: int
    name: str

    @strawberry.field
    def products(self) -> List["Product"]:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM products WHERE category_id = %s;", (self.id,))
                rows = cur.fetchall()
                return [Product(**row) for row in rows]
        finally:
            conn.close()

@strawberry.type
class Product:
    id: int
    name: str
    price: int
    stock: int
    description: Optional[str] = None
    category_id: int

    @strawberry.field
    def category(self) -> Optional[Category]:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM categories WHERE id = %s;", (self.category_id,))
                row = cur.fetchone()
                return Category(**row) if row else None
        finally:
            conn.close()

# ==========================================
# Definisi Query (Resolvers)
# ==========================================
@strawberry.type
class Query:
    @strawberry.field
    def products(self) -> List[Product]:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM products ORDER BY id ASC;")
                rows = cur.fetchall()
                return [Product(**row) for row in rows]
        finally:
            conn.close()

    @strawberry.field
    def categories(self) -> List[Category]:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM categories ORDER BY id ASC;")
                rows = cur.fetchall()
                return [Category(**row) for row in rows]
        finally:
            conn.close()

# Inisialisasi Schema dengan introspection aktif
schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

# ==========================================
# FastAPI App & CORS Setup
# ==========================================
app = FastAPI(title="GraphQL Lab 04 API")

# WAJIB: Izinkan domain Apollo Sandbox agar bisa connect tanpa CORS error
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://studio.apollographql.com",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_app, prefix="/graphql")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def root():
    return {"message": "GraphQL Server ready at /graphql"}