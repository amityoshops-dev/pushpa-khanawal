"""
Pushpa Khanawal - Core ERP Engine
Dependencies: pip install fastapi uvicorn pydantic
Run Command: uvicorn engine:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import sqlite3
import json

app = FastAPI(title="Pushpa Khanawal Core ERP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "khanawal_erp.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. Raw Stock Ledger (Manual adjustments + consumption)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_inventory (
                ingredient_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                current_stock REAL DEFAULT 0.0,
                cost_per_unit REAL DEFAULT 0.0
            )
        """)
        
        # 2. Stock Audit Trail (Additions/Subtractions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_id TEXT,
                movement_type TEXT, -- 'PURCHASE_ADD', 'MANUAL_DEDUCT', 'WASTAGE', 'SALE_AUTO'
                quantity REAL NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ingredient_id) REFERENCES raw_inventory(ingredient_id)
            )
        """)
        
        # 3. Financial General Ledger
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS general_ledger (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_id TEXT NOT NULL,
                account_head TEXT NOT NULL, -- 'Cash Drawer', 'Bank UPI', 'Food Sales', 'Tax Payable'
                direction TEXT NOT NULL,    -- 'DEBIT', 'CREDIT'
                amount REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Master Invoices
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                table_name TEXT NOT NULL,
                subtotal REAL NOT NULL,
                cgst REAL NOT NULL,
                sgst REAL NOT NULL,
                grand_total REAL NOT NULL,
                payment_mode TEXT NOT NULL, -- 'CASH', 'STATIC_UPI', 'CARD'
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed initial raw materials if not present
        cursor.execute("SELECT COUNT(*) FROM raw_inventory")
        if cursor.fetchone()[0] == 0:
            initial_stock = [
                ("RAW_MUTTON", "Mutton (मटण)", "KG", 25.0, 600.0),
                ("RAW_CHICKEN", "Chicken (चिकन)", "KG", 30.0, 220.0),
                ("RAW_BHAKRI_FLOUR", "Jowar/Bajra Flour (पीठ)", "KG", 50.0, 45.0),
                ("RAW_OIL", "Cooking Oil (तेल)", "LITER", 30.0, 140.0)
            ]
            cursor.executemany("INSERT INTO raw_inventory VALUES (?, ?, ?, ?, ?)", initial_stock)
        conn.commit()

init_db()

# --- Schemas ---
class StockAdjustmentPayload(BaseModel):
    ingredient_id: str
    quantity: float
    movement_type: str  # "PURCHASE_ADD", "MANUAL_SUBTRACT", "WASTAGE"
    reason: str

class SettlementPayload(BaseModel):
    order_id: str
    table_name: str
    subtotal: float
    cgst: float
    sgst: float
    grand_total: float
    payment_mode: str # "CASH", "STATIC_UPI"
    consumed_stock: List[dict] # [{"ingredient_id": "RAW_MUTTON", "qty": 0.5}]

# --- Endpoints ---

@app.get("/api/inventory")
def get_inventory():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM raw_inventory")
        return [dict(row) for row in cur.fetchall()]

@app.post("/api/inventory/adjust")
def adjust_inventory(payload: StockAdjustmentPayload):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        
        # Calculate delta
        delta = payload.quantity if payload.movement_type == "PURCHASE_ADD" else -abs(payload.quantity)
        
        cur.execute("SELECT current_stock FROM raw_inventory WHERE ingredient_id = ?", (payload.ingredient_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ingredient not found")
            
        new_stock = row[0] + delta
        if new_stock < 0:
            raise HTTPException(status_code=400, detail="Cannot deduct more than existing stock balance")
            
        cur.execute("UPDATE raw_inventory SET current_stock = ? WHERE ingredient_id = ?", (new_stock, payload.ingredient_id))
        cur.execute("""
            INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reason)
            VALUES (?, ?, ?, ?)
        """, (payload.ingredient_id, payload.movement_type, abs(payload.quantity), payload.reason))
        
        conn.commit()
    return {"status": "SUCCESS", "new_stock": new_stock}

@app.post("/api/billing/settle")
def settle_bill(payload: SettlementPayload):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        
        # 1. Record Order
        cur.execute("""
            INSERT INTO orders (order_id, table_name, subtotal, cgst, sgst, grand_total, payment_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (payload.order_id, payload.table_name, payload.subtotal, payload.cgst, payload.sgst, payload.grand_total, payload.payment_mode))
        
        # 2. Financial Ledger Postings (Double-Entry)
        asset_account = "Cash Drawer" if payload.payment_mode == "CASH" else "Bank Current Account"
        # Debit Settlement Account
        cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'DEBIT', ?)",
                    (payload.order_id, asset_account, payload.grand_total))
        # Credit Food Revenue
        cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'CREDIT', ?)",
                    (payload.order_id, "Food Sales Revenue", payload.subtotal))
        # Credit Taxes
        cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'CREDIT', ?)",
                    (payload.order_id, "Output CGST (2.5%)", payload.cgst))
        cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'CREDIT', ?)",
                    (payload.order_id, "Output SGST (2.5%)", payload.sgst))
        
        # 3. Deduct linked BOM stock automatically
        for stock_item in payload.consumed_stock:
            cur.execute("""
                UPDATE raw_inventory 
                SET current_stock = MAX(0, current_stock - ?) 
                WHERE ingredient_id = ?
            """, (stock_item["qty"], stock_item["ingredient_id"]))
            
            cur.execute("""
                INSERT INTO stock_movements (ingredient_id, movement_type, quantity, reason)
                VALUES (?, 'SALE_AUTO', ?, ?)
            """, (stock_item["ingredient_id"], stock_item["qty"], f"Bill: {payload.order_id}"))

        conn.commit()
    return {"status": "SETTLED", "order_id": payload.order_id}

@app.get("/api/reports/ledger")
def get_ledger():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM general_ledger ORDER BY timestamp DESC LIMIT 50")
        return [dict(row) for row in cur.fetchall()]