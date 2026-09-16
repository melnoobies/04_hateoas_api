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
                    title VARCHAR(255) NOT NULL,
                    price FLOAT NOT NULL,
                    stock INT DEFAULT 0,
                    description TEXT
                );
            """)
            # Tambahkan kolom title jika sebelumnya bernama name
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='name') THEN
                        ALTER TABLE products RENAME COLUMN name TO title;
                    END IF;
                END $$;
            """)
            cur.execute("SELECT COUNT(*) FROM categories;")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO categories (id, name) VALUES 
                    (1, 'Electronics'),
                    (2, 'Accessories');
                    INSERT INTO products (title, price, stock, description, category_id) VALUES
                    ('Mechanical Keyboard', 750000, 15, 'RGB Blue Switch', 1),
                    ('Wireless Mouse', 250000, 30, 'Rechargeable Silent Click', 1),
                    ('Deskmat XXL', 120000, 50, 'Anti-slip 900x400mm', 2);
                """)
        conn.close()
    except Exception as e:
        print(f"DB Init Warning: {e}")

# ==========================================
# Definisi Types & Input Types
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
                cur.execute("SELECT * FROM products WHERE category_id = %s ORDER BY id ASC;", (self.id,))
                rows = cur.fetchall()
                return [Product(**row) for row in rows]
        finally:
            conn.close()

@strawberry.type
class Product:
    id: int
    title: str
    price: float
    stock: Optional[int] = 0
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

# Input Types untuk Mutation
@strawberry.input
class CreateProductInput:
    title: str
    price: float
    category_id: int

@strawberry.input
class UpdateProductInput:
    title: Optional[str] = None
    price: Optional[float] = None

# ==========================================
# Definisi Query (dengan Argumen Filter)
# ==========================================
@strawberry.type
class Query:
    @strawberry.field
    def products(self, category_id: Optional[int] = None) -> List[Product]:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if category_id is not None:
                    cur.execute("SELECT * FROM products WHERE category_id = %s ORDER BY id ASC;", (category_id,))
                else:
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

# ==========================================
# Definisi Mutation (Create, Update, Delete)
# ==========================================
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_product(self, input: CreateProductInput) -> Product:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO products (title, price, category_id) VALUES (%s, %s, %s) RETURNING *;",
                    (input.title, input.price, input.category_id)
                )
                new_row = cur.fetchone()
                return Product(**new_row)
        finally:
            conn.close()

    @strawberry.mutation
    def update_product(self, id: int, input: UpdateProductInput) -> Product:
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE products SET title = COALESCE(%s, title), price = COALESCE(%s, price) WHERE id = %s RETURNING *;",
                    (input.title, input.price, id)
                )
                updated_row = cur.fetchone()
                if not updated_row:
                    raise Exception(f"Product dengan id {id} tidak ditemukan.")
                return Product(**updated_row)
        finally:
            conn.close()

    @strawberry.mutation
    def delete_product(self, id: int) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM products WHERE id = %s;", (id,))
                return cur.rowcount > 0
        finally:
            conn.close()

# Inisialisasi Schema dengan Query & Mutation
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

# ==========================================
# FastAPI App & CORS Setup
# ==========================================
app = FastAPI(title="GraphQL Lab 05 API")

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
    return {"message": "GraphQL Lab 05 Server ready at /graphql"}