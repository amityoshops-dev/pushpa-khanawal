import sqlite3
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

app = FastAPI(title="Pushpa Khanawal Core ERP")
DB_PATH = "khanawal_core.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # 1. System Config / Settings Store
        c.execute("""CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")

        # 2. Master Menu Catalog
        c.execute("""CREATE TABLE IF NOT EXISTS menu (
            id TEXT PRIMARY KEY,
            name_mr TEXT NOT NULL,
            name_en TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            station TEXT NOT NULL,          -- 'BHAKRI', 'HOT_CURRY', 'BAR'
            diet TEXT NOT NULL,             -- 'VEG', 'NON_VEG'
            is_active INTEGER DEFAULT 1,
            bom_json TEXT DEFAULT '[]'
        )""")

        # 3. Raw Materials Inventory
        c.execute("""CREATE TABLE IF NOT EXISTS raw_inventory (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            stock REAL DEFAULT 0.0,
            unit TEXT NOT NULL,
            cost_per_unit REAL DEFAULT 0.0,
            min_reorder_level REAL DEFAULT 5.0
        )""")

        # 4. Stock Audits & Procurements with TDS
        c.execute("""CREATE TABLE IF NOT EXISTS stock_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            movement_type TEXT,
            qty REAL NOT NULL,
            unit_rate REAL DEFAULT 0.0,
            tds_section TEXT,
            tds_rate REAL DEFAULT 0.0,
            tds_amount REAL DEFAULT 0.0,
            vendor_name TEXT,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        # 5. Orders & Financial Billing
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            table_or_target TEXT NOT NULL,
            customer_name TEXT DEFAULT 'Walk-in',
            customer_phone TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            packaging_charge REAL DEFAULT 0.0,
            discount_amount REAL DEFAULT 0.0,
            discount_reason TEXT DEFAULT '',
            taxable_amount REAL NOT NULL,
            cgst REAL NOT NULL,
            sgst REAL NOT NULL,
            grand_total REAL NOT NULL,
            payment_mode TEXT NOT NULL,
            items_json TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        # 6. Double-Entry General Ledger
        c.execute("""CREATE TABLE IF NOT EXISTS general_ledger (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id TEXT NOT NULL,
            account_head TEXT NOT NULL,
            direction TEXT NOT NULL,
            amount REAL NOT NULL,
            notes TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        # Seed Settings if fresh
        default_settings = {
            "restaurant_name": "पुष्पा खानावळ (Pushpa Khanawal)",
            "gstin": "27AABCP1234F1Z8",
            "fssai": "11521034000123",
            "address": "Opp. Main Bus Stand, Pune-Solapur Highway, Pune, Maharashtra",
            "phone": "+91 98220 00000",
            "upi_vpa": "pushpakhanawal@upi",
            "footer_note": "अस्सल गावरान आणि कोल्हापुरी चव! पुन्हा भेट द्या."
        }
        for k, v in default_settings.items():
            c.execute("INSERT OR IGNORE INTO system_settings VALUES (?, ?)", (k, v))

        # Seed Initial Starter Menu
        c.execute("SELECT COUNT(*) FROM menu")
        if c.fetchone()[0] == 0:
            c.executemany("INSERT INTO menu VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                ("PK01", "पुष्पा स्पेशल मटण थाळी", "Special Mutton Thali", "थाळी", 420.0, "HOT_CURRY", "NON_VEG", 1, json.dumps([{"id":"RAW_MUTTON","qty":0.30},{"id":"RAW_FLOUR","qty":0.10}])),
                ("PK02", "गावरान चिकन थाळी", "Gavran Chicken Thali", "थाळी", 320.0, "HOT_CURRY", "NON_VEG", 1, json.dumps([{"id":"RAW_CHICKEN","qty":0.30},{"id":"RAW_FLOUR","qty":0.10}])),
                ("PK03", "स्पेशल व्हेज थाळी (पिठलं-भाकरी)", "Special Veg Pithla Bhakri Thali", "थाळी", 220.0, "HOT_CURRY", "VEG", 1, json.dumps([{"id":"RAW_FLOUR","qty":0.12}])),
                ("PK04", "मटण सुक्का फ्राय", "Mutton Sukka Masala", "मटण", 340.0, "HOT_CURRY", "NON_VEG", 1, json.dumps([{"id":"RAW_MUTTON","qty":0.22}])),
                ("PK05", "चिकन खर्डा रोस्ट", "Chicken Kharda Roast", "चिकन", 270.0, "HOT_CURRY", "NON_VEG", 1, json.dumps([{"id":"RAW_CHICKEN","qty":0.25}])),
                ("PK06", "तांबडा रस्सा वाटी", "Tambda Rassa Bowl", "रस्सा", 50.0, "HOT_CURRY", "NON_VEG", 1, "[]"),
                ("PK07", "पांढरा रस्सा वाटी", "Pandhra Rassa Bowl", "रस्सा", 50.0, "HOT_CURRY", "NON_VEG", 1, "[]"),
                ("PK08", "गरम ज्वारी भाकरी", "Hot Jowar Bhakri", "भाकरी/रोटी", 30.0, "BHAKRI", "VEG", 1, json.dumps([{"id":"RAW_FLOUR","qty":0.08}])),
                ("PK09", "बाजरी भाकरी लोणी", "Bajra Bhakri with Butter", "भाकरी/रोटी", 40.0, "BHAKRI", "VEG", 1, json.dumps([{"id":"RAW_FLOUR","qty":0.08}])),
                ("PK10", "इंद्रायणी सुवासिक भात", "Steamed Indrayani Rice", "भात", 80.0, "HOT_CURRY", "VEG", 1, "[]"),
                ("PK11", "कोकम सोलकढी ग्लास", "Chilled Solkadhi", "पेये", 40.0, "BAR", "VEG", 1, "[]")
            ])

        # Seed Raw Inventory
        c.execute("SELECT COUNT(*) FROM raw_inventory")
        if c.fetchone()[0] == 0:
            c.executemany("INSERT INTO raw_inventory VALUES (?, ?, ?, ?, ?, ?)", [
                ("RAW_MUTTON", "Mutton Fresh (मटण)", 35.0, "KG", 620.0, 10.0),
                ("RAW_CHICKEN", "Broiler Chicken (चिकन)", 40.0, "KG", 210.0, 10.0),
                ("RAW_FLOUR", "Jowar / Bajra Flour (पीठ)", 80.0, "KG", 45.0, 15.0),
                ("RAW_OIL", "Refined Cooking Oil (तेल)", 50.0, "Liter", 140.0, 10.0),
                ("RAW_PANEER", "Fresh Paneer (पनीर)", 15.0, "KG", 340.0, 4.0)
            ])
        conn.commit()

init_db()

# --- Request Models ---
class MenuSaveReq(BaseModel):
    id: str
    name_mr: str
    name_en: str
    category: str
    price: float
    station: str
    diet: str
    is_active: int
    bom_json: Optional[str] = "[]"

class SettleReq(BaseModel):
    order_id: str
    channel: str
    table_or_target: str
    customer_name: Optional[str] = "Walk-in"
    customer_phone: Optional[str] = ""
    subtotal: float
    packaging_charge: float
    discount_amount: float
    discount_reason: Optional[str] = ""
    taxable_amount: float
    cgst: float
    sgst: float
    grand_total: float
    payment_mode: str
    items: List[Dict]
    bom_deductions: List[Dict]

class InwardReq(BaseModel):
    item_id: str
    qty: float
    unit_rate: float
    vendor_name: str
    tds_section: str
    memo: str

# --- API Endpoints ---
@app.get("/api/settings")
def get_settings():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.cursor().execute("SELECT key, value FROM system_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

@app.post("/api/settings")
def save_settings(data: Dict[str, str]):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        for k, v in data.items():
            c.execute("INSERT INTO system_settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
        conn.commit()
    return {"status": "SAVED"}

@app.get("/api/menu")
def get_menu():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.cursor().execute("SELECT * FROM menu").fetchall()]

@app.post("/api/menu/save")
def save_menu(p: MenuSaveReq):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO menu (id, name_mr, name_en, category, price, station, diet, is_active, bom_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name_mr=excluded.name_mr, name_en=excluded.name_en, category=excluded.category,
                price=excluded.price, station=excluded.station, diet=excluded.diet,
                is_active=excluded.is_active, bom_json=excluded.bom_json
        """, (p.id, p.name_mr, p.name_en, p.category, p.price, p.station, p.diet, p.is_active, p.bom_json))
        conn.commit()
    return {"status": "SUCCESS"}

@app.delete("/api/menu/{item_id}")
def delete_menu(item_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.cursor().execute("DELETE FROM menu WHERE id = ?", (item_id,))
        conn.commit()
    return {"status": "DELETED"}

@app.get("/api/inventory")
def get_inventory():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.cursor().execute("SELECT * FROM raw_inventory").fetchall()]

@app.post("/api/inventory/inward")
def post_inward(p: InwardReq):
    gross = p.qty * p.unit_rate
    rates = {"194C_INDIV": 0.01, "194C_CORP": 0.02, "194Q": 0.001, "194J": 0.10}
    tds_rate = rates.get(p.tds_section, 0.0)
    tds = gross * tds_rate
    net = gross - tds
    voucher = f"PUR-{datetime.now().strftime('%y%m%d%H%M%S')}"

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE raw_inventory SET stock = stock + ? WHERE id = ?", (p.qty, p.item_id))
        c.execute("""INSERT INTO stock_audit (item_id, movement_type, qty, unit_rate, tds_section, tds_rate, tds_amount, vendor_name, reason)
                     VALUES (?, 'PURCHASE_INWARD', ?, ?, ?, ?, ?, ?, ?)""",
                  (p.item_id, p.qty, p.unit_rate, p.tds_section, tds_rate * 100, tds, p.vendor_name, p.memo))
        c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Raw Materials Inventory', 'DEBIT', ?, ?)", (voucher, gross, f"Inward from {p.vendor_name}"))
        c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Vendor Accounts Payable', 'CREDIT', ?, ?)", (voucher, net, f"Net payable {p.vendor_name}"))
        if tds > 0:
            c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'TDS Withheld Payable', 'CREDIT', ?, ?)", (voucher, tds, f"TDS Sec {p.tds_section}"))
        conn.commit()
    return {"status": "SUCCESS", "gross": gross, "tds": tds, "net": net}

@app.post("/api/orders/settle")
def post_settle(p: SettleReq):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                  (p.order_id, p.channel, p.table_or_target, p.customer_name, p.customer_phone,
                   p.subtotal, p.packaging_charge, p.discount_amount, p.discount_reason,
                   p.taxable_amount, p.cgst, p.sgst, p.grand_total, p.payment_mode, json.dumps(p.items)))

        debit_map = {"CASH": "Cash Drawer", "STATIC_UPI": "Bank Current Account", "SPLIT_CASH_UPI": "Cash & Bank Clearing"}
        debit_head = debit_map.get(p.payment_mode, "Cash Drawer")

        c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, ?, 'DEBIT', ?, ?)", (p.order_id, debit_head, p.grand_total, f"Order {p.channel}"))
        c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Food Sales Revenue', 'CREDIT', ?, ?)", (p.order_id, p.taxable_amount - p.packaging_charge, "Net Sales"))
        if p.packaging_charge > 0:
            c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Packaging Fees', 'CREDIT', ?, ?)", (p.order_id, p.packaging_charge, "Parcel Fee"))
        if p.cgst > 0:
            c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Output CGST (2.5%)', 'CREDIT', ?, ?)", (p.order_id, p.cgst, "GST"))
            c.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount, notes) VALUES (?, 'Output SGST (2.5%)', 'CREDIT', ?, ?)", (p.order_id, p.sgst, "GST"))

        for b in p.bom_deductions:
            c.execute("UPDATE raw_inventory SET stock = MAX(0, stock - ?) WHERE id = ?", (b["qty"], b["item_id"]))
            c.execute("INSERT INTO stock_audit (item_id, movement_type, qty, reason) VALUES (?, 'AUTO_BOM', ?, ?)", (b["item_id"], b["qty"], f"Order {p.order_id}"))
        conn.commit()
    return {"status": "SETTLED"}

@app.get("/api/reports/ledger")
def get_ledger():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.cursor().execute("SELECT * FROM general_ledger ORDER BY entry_id DESC LIMIT 80").fetchall()]

@app.get("/api/reports/analytics")
def get_analytics():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        orders = [dict(r) for r in c.execute("SELECT * FROM orders").fetchall()]
        audits = [dict(r) for r in c.execute("SELECT * FROM stock_audit WHERE movement_type='PURCHASE_INWARD'").fetchall()]
        return {"orders": orders, "inward_audits": audits}

# SINGLE-FILE INLINED WORKSTATION HTML
ENTERPRISE_UI = """<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<title>पुष्पा खानावळ - Core Restaurant ERP</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>
  :root {
    --brand: #e65100; --brand-dark: #b23c00; --dark: #0f172a; --surface: #ffffff; --bg: #f1f5f9;
    --border: #cbd5e1; --text: #0f172a; --muted: #64748b;
    --veg: #15803d; --nonveg: #b91c1c; --vacant: #16a34a; --occupied: #ea580c;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

  header { height: 48px; background: var(--dark); color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; border-bottom: 2px solid var(--brand); }
  .logo { font-size: 16px; font-weight: 800; color: #fb923c; display: flex; align-items: center; gap: 8px; }
  .nav-tabs { display: flex; gap: 4px; }
  .nav-btn { background: #1e293b; border: 1px solid #334155; color: #cbd5e1; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 700; }
  .nav-btn.active, .nav-btn:hover { background: var(--brand); color: #fff; border-color: var(--brand); }

  /* 3-Column POS Grid */
  .workspace { display: grid; grid-template-columns: 280px 1fr 420px; height: calc(100vh - 48px); }

  /* Left Panel: Tables */
  .col-tables { background: var(--surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
  .channel-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; padding: 4px; background: #e2e8f0; border-bottom: 1px solid var(--border); }
  .ch-btn { padding: 6px 2px; text-align: center; font-size: 10px; font-weight: 700; border-radius: 3px; cursor: pointer; background: #fff; border: 1px solid var(--border); }
  .ch-btn.active { background: var(--dark); color: #fff; border-color: var(--dark); }
  .table-grid { padding: 8px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; overflow-y: auto; flex: 1; align-content: start; }
  .tbl-card { border: 1.5px solid var(--border); border-radius: 6px; padding: 8px; cursor: pointer; background: #fff; }
  .tbl-card.active { border-color: var(--brand); box-shadow: 0 0 0 2px rgba(230, 81, 0, 0.2); }
  .tbl-card.vacant { border-left: 5px solid var(--vacant); }
  .tbl-card.occupied { border-left: 5px solid var(--occupied); }
  .tbl-ops { padding: 6px; background: #f8fafc; border-top: 1px solid var(--border); display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
  .tbl-ops button { padding: 5px; font-size: 10px; font-weight: 700; border: 1px solid var(--border); background: #fff; border-radius: 3px; cursor: pointer; }

  /* Center Panel: Catalog */
  .col-menu { display: flex; flex-direction: column; background: var(--bg); overflow: hidden; }
  .search-strip { padding: 6px 10px; background: #fff; border-bottom: 1px solid var(--border); display: flex; gap: 6px; }
  .search-strip input { flex: 1; padding: 6px 10px; border: 1px solid var(--border); border-radius: 4px; font-size: 12px; }
  .cat-strip { background: #fff; padding: 6px 10px; border-bottom: 1px solid var(--border); display: flex; gap: 6px; overflow-x: auto; }
  .chip { padding: 4px 12px; background: #f1f5f9; border-radius: 14px; font-size: 11px; font-weight: 700; cursor: pointer; white-space: nowrap; border: 1px solid var(--border); }
  .chip.active { background: var(--brand); color: #fff; border-color: var(--brand); }
  .menu-grid { padding: 10px; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px; overflow-y: auto; flex: 1; }
  .food-card { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 10px; cursor: pointer; display: flex; flex-direction: column; justify-content: space-between; height: 105px; }
  .food-card:hover { border-color: var(--brand); }
  .diet-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; margin-right: 4px; }

  /* Right Panel: Settlement Desk */
  .col-bill { background: #fff; border-left: 1px solid var(--border); display: flex; flex-direction: column; justify-content: space-between; }
  .bill-top { padding: 8px 12px; background: #f8fafc; border-bottom: 1px solid var(--border); }
  .crm-row { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 4px; }
  .crm-row input { padding: 4px 6px; font-size: 11px; border: 1px solid var(--border); border-radius: 3px; }
  .cart-wrap { flex: 1; overflow-y: auto; }
  .cart-table { width: 100%; border-collapse: collapse; font-size: 11px; }
  .cart-table th { background: #f8fafc; padding: 6px 8px; text-align: left; font-size: 10px; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--border); }
  .cart-table td { padding: 6px 8px; border-bottom: 1px solid #f1f5f9; }
  .qty-box { display: flex; align-items: center; gap: 4px; }
  .qty-btn { width: 18px; height: 18px; border: 1px solid var(--border); background: #fff; border-radius: 2px; cursor: pointer; font-weight: 700; }

  /* Summary & Command */
  .bill-summary { padding: 8px 12px; background: #f8fafc; border-top: 1px solid var(--border); }
  .sum-row { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px; }
  .sum-row.total { font-size: 15px; font-weight: 800; border-top: 1.5px dashed var(--border); padding-top: 4px; margin-top: 4px; color: #000; }
  .action-deck { padding: 8px 12px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; background: #fff; border-top: 1px solid var(--border); }
  .act-btn { border: none; padding: 9px 4px; border-radius: 4px; font-size: 11px; font-weight: 700; cursor: pointer; text-align: center; color: #fff; }
  .btn-kot { background: #0284c7; }
  .btn-upi { background: #475569; }
  .btn-split { background: #d97706; }
  .btn-settle { background: #15803d; grid-column: span 3; font-size: 13px; padding: 11px; }

  /* Overlays */
  .view-panel { display: none; position: fixed; top: 48px; left: 0; width: 100%; height: calc(100vh - 48px); background: #fff; z-index: 50; padding: 18px; overflow-y: auto; }
  .data-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 11px; }
  .data-table th, .data-table td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
  .data-table th { background: #f8fafc; font-weight: 700; }
  .form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; max-width: 800px; margin-top: 10px; }
  .form-grid label { font-size: 11px; font-weight: 700; display: block; margin-bottom: 2px; }
  .form-grid input, .form-grid select { width: 100%; padding: 6px; border: 1px solid var(--border); border-radius: 4px; font-size: 12px; }
  .modal-shade { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 100; justify-content: center; align-items: center; }
  .modal-box { background: #fff; border-radius: 6px; width: 360px; padding: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); font-size: 11px; }

  /* Thermal Print Slip Media */
  @media print {
    body * { visibility: hidden; }
    #thermalPrintSlip, #thermalPrintSlip * { visibility: visible; }
    #thermalPrintSlip { position: fixed; left: 0; top: 0; width: 72mm; margin: 0; padding: 0; font-family: monospace; font-size: 11px; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">
    <span>🍲 पुष्पा खानावळ (Pushpa Khanawal ERP)</span>
  </div>
  <div class="nav-tabs">
    <button class="nav-btn active" id="tabPos" onclick="switchTab('POS')">POS Terminal</button>
    <button class="nav-btn" id="tabMenuEditor" onclick="switchTab('MENU_EDITOR')">Menu & Pricing</button>
    <button class="nav-btn" id="tabAnalytics" onclick="switchTab('ANALYTICS')">Operations & Reports</button>
    <button class="nav-btn" id="tabInventory" onclick="switchTab('INVENTORY')">Stock & TDS</button>
    <button class="nav-btn" id="tabLedger" onclick="switchTab('LEDGER')">General Ledger</button>
    <button class="nav-btn" id="tabSettings" onclick="switchTab('SETTINGS')">Settings</button>
  </div>
</header>

<!-- VIEW 1: POS WORKSPACE -->
<div class="workspace" id="viewPOS">
  <div class="col-tables">
    <div class="channel-bar">
      <div class="ch-btn active" onclick="setChannel('DINE_IN', this)">Dine-In</div>
      <div class="ch-btn" onclick="setChannel('TAKEAWAY', this)">Parcel</div>
      <div class="ch-btn" onclick="setChannel('DELIVERY', this)">Delivery</div>
      <div class="ch-btn" onclick="setChannel('ALL', this)">All</div>
    </div>
    <div class="table-grid" id="tableDeck"></div>
    <div class="tbl-ops">
      <button onclick="mergeTable()">🔗 Merge Table</button>
      <button onclick="addCustomItem()">➕ Open Item</button>
    </div>
  </div>

  <div class="col-menu">
    <div class="search-strip">
      <input type="text" id="menuSearch" placeholder="🔍 Search menu item or code..." oninput="filterCatalog()">
    </div>
    <div class="cat-strip" id="catStrip"></div>
    <div class="menu-grid" id="menuGrid"></div>
  </div>

  <div class="col-bill">
    <div>
      <div class="bill-top">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <b id="lblDeskTable" style="font-size:13px;">Table 1 (Dine-In)</b>
          <button onclick="voidCart()" style="border:none; background:none; color:var(--nonveg); font-size:10px; font-weight:700; cursor:pointer;">Void All</button>
        </div>
        <div class="crm-row">
          <input type="text" id="custName" placeholder="Guest Name" value="Walk-in">
          <input type="text" id="custPhone" placeholder="Mobile (Loyalty/SMS)">
        </div>
      </div>
      <div class="cart-wrap">
        <table class="cart-table">
          <thead><tr><th>Item</th><th style="width:60px;">Qty</th><th>Rate</th><th>Total</th></tr></thead>
          <tbody id="cartTbody"></tbody>
        </table>
      </div>
    </div>

    <div>
      <div class="bill-summary">
        <div class="sum-row"><span>Item Subtotal:</span><span id="txtSub">₹0.00</span></div>
        <div style="display:flex; gap:4px; margin:2px 0;">
          <input type="number" id="txtDisc" placeholder="Discount ₹" style="width:80px; padding:3px; font-size:10px; border:1px solid var(--border); border-radius:2px;" oninput="recomputeTotals()">
          <input type="text" id="txtDiscReason" placeholder="Reason (e.g. Regular/Friend)" style="flex:1; padding:3px; font-size:10px; border:1px solid var(--border); border-radius:2px;">
        </div>
        <div class="sum-row"><span>Packaging Charge:</span><span id="txtPackaging">₹0.00</span></div>
        <div class="sum-row"><span>Restaurant GST (5%):</span><span id="txtGST">₹0.00</span></div>
        <div class="sum-row total"><span>Net Payable:</span><span id="txtGrand">₹0.00</span></div>
      </div>
      <div class="action-deck">
        <button class="act-btn btn-kot" onclick="fireKOT()">Fire Station KOT</button>
        <button class="act-btn btn-upi" onclick="openUpiModal()">Static UPI</button>
        <button class="act-btn btn-split" onclick="openSplitModal()">Split Bill</button>
        <button class="act-btn btn-settle" onclick="settleBill('CASH')">SETTLE CASH & PRINT 80MM BILL</button>
      </div>
    </div>
  </div>
</div>

<!-- VIEW 2: MENU & PRICING MASTER (CATALOG TOOL) -->
<div class="view-panel" id="viewMENU_EDITOR">
  <h2>Menu & Price Management</h2>
  <div style="display:grid; grid-template-columns: 1fr 360px; gap:16px; margin-top:10px;">
    <div>
      <table class="data-table">
        <thead><tr><th>Code</th><th>Marathi Name</th><th>English Name</th><th>Category</th><th>Station</th><th>Price (₹)</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="menuEditorTbody"></tbody>
      </table>
    </div>
    <div style="background:#f8fafc; border:1px solid var(--border); border-radius:6px; padding:14px; font-size:11px;">
      <h3 id="lblMenuFormTitle">Add / Edit Dish</h3>
      <label style="margin-top:6px; display:block;">Item Code / SKU:</label>
      <input type="text" id="mId" style="width:100%; padding:5px;" placeholder="PK12">
      <label style="margin-top:6px; display:block;">Name (मराठी):</label>
      <input type="text" id="mNameMr" style="width:100%; padding:5px;" placeholder="मटण खिमा फ्राय">
      <label style="margin-top:6px; display:block;">Name (English):</label>
      <input type="text" id="mNameEn" style="width:100%; padding:5px;" placeholder="Mutton Kheema Fry">
      <label style="margin-top:6px; display:block;">Category:</label>
      <input type="text" id="mCat" style="width:100%; padding:5px;" placeholder="मटण / थाळी">
      <label style="margin-top:6px; display:block;">Price (₹):</label>
      <input type="number" id="mPrice" style="width:100%; padding:5px;" placeholder="280">
      <label style="margin-top:6px; display:block;">Kitchen Station:</label>
      <select id="mStation" style="width:100%; padding:5px;">
        <option value="HOT_CURRY">Main Kitchen (Hot Curry/Thali)</option>
        <option value="BHAKRI">Bhakri Chul Station</option>
        <option value="BAR">Beverage Bar</option>
      </select>
      <label style="margin-top:6px; display:block;">Diet:</label>
      <select id="mDiet" style="width:100%; padding:5px;">
        <option value="NON_VEG">Non-Veg (Red Dot)</option>
        <option value="VEG">Pure Veg (Green Dot)</option>
      </select>
      <label style="margin-top:6px; display:block;">BOM Recipe Deduction (JSON):</label>
      <input type="text" id="mBom" style="width:100%; padding:5px;" value="[]">
      <button class="act-btn" style="background:var(--brand); width:100%; margin-top:10px; padding:8px;" onclick="saveMenuItem()">Save to Master Catalog</button>
    </div>
  </div>
</div>

<!-- VIEW 3: OPERATIONS & REPORTS DASHBOARD -->
<div class="view-panel" id="viewANALYTICS">
  <h2>Operations & Financial Reports Dashboard</h2>
  <div style="display:flex; gap:12px; margin:12px 0;" id="reportStats"></div>
  <h3>Daily Sales & Tax Settlement Journal</h3>
  <table class="data-table">
    <thead><tr><th>Invoice ID</th><th>Timestamp</th><th>Channel</th><th>Target</th><th>Subtotal</th><th>CGST</th><th>SGST</th><th>Net Amount</th><th>Payment Mode</th></tr></thead>
    <tbody id="salesJournalTbody"></tbody>
  </table>
</div>

<!-- VIEW 4: RAW STOCK & TDS -->
<div class="view-panel" id="viewINVENTORY">
  <h2>Raw Material Inventory & TDS Compliance Hub</h2>
  <div style="display:grid; grid-template-columns: 1fr 360px; gap:16px; margin-top:10px;">
    <div>
      <table class="data-table">
        <thead><tr><th>Code</th><th>Material</th><th>Current Stock</th><th>Unit</th><th>Rate</th></tr></thead>
        <tbody id="rawStockTbody"></tbody>
      </table>
    </div>
    <div style="background:#f8fafc; border:1px solid var(--border); border-radius:6px; padding:12px; font-size:11px;">
      <h3>Supplier Inward + Section 194 TDS</h3>
      <label style="margin-top:6px; display:block;">Material:</label>
      <select id="pItem" style="width:100%; padding:5px;"></select>
      <label style="margin-top:6px; display:block;">Quantity:</label>
      <input type="number" id="pQty" style="width:100%; padding:5px;" oninput="calcTdsPreview()">
      <label style="margin-top:6px; display:block;">Unit Rate (₹):</label>
      <input type="number" id="pRate" style="width:100%; padding:5px;" oninput="calcTdsPreview()">
      <label style="margin-top:6px; display:block;">Vendor Name:</label>
      <input type="text" id="pVendor" style="width:100%; padding:5px;" placeholder="Kailash Meat Supplies">
      <label style="margin-top:6px; display:block;">TDS Section:</label>
      <select id="pTdsSec" style="width:100%; padding:5px;" onchange="calcTdsPreview()">
        <option value="NONE">None (Exempt)</option>
        <option value="194C_INDIV">Sec 194C Indiv/HUF (1%)</option>
        <option value="194C_CORP">Sec 194C Company/Firm (2%)</option>
        <option value="194Q">Sec 194Q Purchase of Goods (0.1%)</option>
        <option value="194J">Sec 194J Professional/Technical (10%)</option>
      </select>
      <div style="background:#fff; border:1px dashed var(--border); padding:6px; margin-top:8px;">
        <div>Gross: <b id="lblGross">₹0.00</b></div>
        <div>TDS: <b id="lblTds" style="color:var(--nonveg);">₹0.00</b></div>
        <div>Net: <b id="lblNet" style="color:var(--veg);">₹0.00</b></div>
      </div>
      <button class="act-btn" style="background:var(--veg); width:100%; margin-top:8px; padding:8px;" onclick="commitInward()">Post Inward to Ledger</button>
    </div>
  </div>
</div>

<!-- VIEW 5: GENERAL LEDGER -->
<div class="view-panel" id="viewLEDGER">
  <h2>Double-Entry General Accounting Ledger (ACID Audit)</h2>
  <table class="data-table">
    <thead><tr><th>Entry ID</th><th>Timestamp</th><th>Voucher ID</th><th>Account Head</th><th>Direction</th><th>Amount</th><th>Memo</th></tr></thead>
    <tbody id="ledgerTbody"></tbody>
  </table>
</div>

<!-- VIEW 6: SETTINGS -->
<div class="view-panel" id="viewSETTINGS">
  <h2>Enterprise Profile & System Settings</h2>
  <div class="form-grid">
    <div>
      <label>Restaurant Legal / Trade Name:</label>
      <input type="text" id="cfgName">
    </div>
    <div>
      <label>GSTIN Registration Number:</label>
      <input type="text" id="cfgGst">
    </div>
    <div>
      <label>FSSAI Food License Number:</label>
      <input type="text" id="cfgFssai">
    </div>
    <div>
      <label>Contact Phone Number:</label>
      <input type="text" id="cfgPhone">
    </div>
    <div style="grid-column: span 2;">
      <label>Full Address / Location:</label>
      <input type="text" id="cfgAddress">
    </div>
    <div>
      <label>Default Merchant UPI VPA (for QR printing):</label>
      <input type="text" id="cfgUpi">
    </div>
    <div style="grid-column: span 2;">
      <label>Receipt Footer Note:</label>
      <input type="text" id="cfgFooter">
    </div>
  </div>
  <button class="act-btn" style="background:var(--brand); padding:10px 24px; margin-top:14px;" onclick="saveSystemSettings()">Save System Settings</button>
</div>

<!-- MODAL: KOT -->
<div class="modal-shade" id="kotModal">
  <div class="modal-box">
    <div id="kotContent" style="font-family:monospace; font-size:11px;"></div>
    <button class="act-btn btn-kot" style="width:100%; margin-top:10px;" onclick="closeModal('kotModal')">Dispatch to Kitchen</button>
  </div>
</div>

<!-- MODAL: STATIC UPI -->
<div class="modal-shade" id="upiModal">
  <div class="modal-box" style="text-align:center;">
    <h3 id="lblUpiTitle">Merchant UPI QR</h3>
    <div style="font-size:10px; color:var(--muted); margin:4px 0;">Permanent Free Bharat-UPI (Zero Processing Fees)</div>
    <div id="upiTargetHolder" style="display:flex; justify-content:center; margin:8px 0;"></div>
    <div style="font-size:15px; font-weight:800;" id="upiModalAmount">₹0.00</div>
    <button class="act-btn btn-settle" style="width:100%; margin-top:8px;" onclick="settleBill('STATIC_UPI')">Confirm Received & Settle</button>
    <button class="act-btn btn-upi" style="width:100%; margin-top:4px;" onclick="closeModal('upiModal')">Cancel</button>
  </div>
</div>

<!-- MODAL: SPLIT -->
<div class="modal-shade" id="splitModal">
  <div class="modal-box">
    <h3>Split Bill Desk</h3>
    <div style="margin:8px 0;">
      <label>Split between covers (persons):</label>
      <input type="number" id="splitCovers" value="2" min="2" style="width:100%; padding:5px; margin-top:4px;" oninput="calcSplit()">
    </div>
    <div style="background:#f1f5f9; padding:8px; border-radius:4px; font-weight:700; margin-bottom:8px;" id="splitPerHead">Per person: ₹0.00</div>
    <button class="act-btn btn-settle" style="width:100%;" onclick="settleBill('SPLIT_CASH_UPI')">Settle Split Bill</button>
    <button class="act-btn btn-upi" style="width:100%; margin-top:4px;" onclick="closeModal('splitModal')">Cancel</button>
  </div>
</div>

<!-- THERMAL 80MM PRINT SLIP -->
<div id="thermalPrintSlip" style="display:none;"></div>

<script>
  let MASTER_MENU = [], RAW_STOCK = [], SETTINGS = {}, currentTableId = "T1", activeCat = "All", activeChannel = "DINE_IN";

  const TABLES = [
    { id: "T1", name: "Table 1", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "T2", name: "Table 2", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "T3", name: "Table 3", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "T4", name: "Table 4", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "T5", name: "Table 5", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "T6", name: "Family Hall 1", channel: "DINE_IN", cart: [], kotIter: 1 },
    { id: "P1", name: "Parcel Counter 1", channel: "TAKEAWAY", cart: [], kotIter: 1 },
    { id: "P2", name: "Parcel Counter 2", channel: "TAKEAWAY", cart: [], kotIter: 1 },
    { id: "D1", name: "Delivery Express", channel: "DELIVERY", cart: [], kotIter: 1 }
  ];

  window.onload = async () => {
    await fetchSettings();
    await fetchMenu();
    await fetchInventory();
    renderTables();
    renderCategories();
    renderMenu();
    selectTable("T1");
    initUpiQr();
  };

  async function fetchSettings() {
    const res = await fetch("/api/settings");
    SETTINGS = await res.json();
    document.getElementById("cfgName").value = SETTINGS.restaurant_name || "";
    document.getElementById("cfgGst").value = SETTINGS.gstin || "";
    document.getElementById("cfgFssai").value = SETTINGS.fssai || "";
    document.getElementById("cfgPhone").value = SETTINGS.phone || "";
    document.getElementById("cfgAddress").value = SETTINGS.address || "";
    document.getElementById("cfgUpi").value = SETTINGS.upi_vpa || "";
    document.getElementById("cfgFooter").value = SETTINGS.footer_note || "";
  }

  async function saveSystemSettings() {
    const payload = {
      restaurant_name: document.getElementById("cfgName").value,
      gstin: document.getElementById("cfgGst").value,
      fssai: document.getElementById("cfgFssai").value,
      phone: document.getElementById("cfgPhone").value,
      address: document.getElementById("cfgAddress").value,
      upi_vpa: document.getElementById("cfgUpi").value,
      footer_note: document.getElementById("cfgFooter").value
    };
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    alert("System Settings Saved Successfully!");
    await fetchSettings();
    initUpiQr();
  }

  function initUpiQr() {
    const holder = document.getElementById("upiTargetHolder");
    holder.innerHTML = "";
    new QRCode(holder, {
      text: `upi://pay?pa=${SETTINGS.upi_vpa || 'pushpakhanawal@upi'}&pn=${encodeURIComponent(SETTINGS.restaurant_name || 'Pushpa Khanawal')}`,
      width: 130, height: 130
    });
  }

  async function fetchMenu() {
    const res = await fetch("/api/menu");
    MASTER_MENU = await res.json();
  }

  async function fetchInventory() {
    const res = await fetch("/api/inventory");
    RAW_STOCK = await res.json();
    const pSel = document.getElementById("pItem");
    pSel.innerHTML = "";
    RAW_STOCK.forEach(r => pSel.innerHTML += `<option value="${r.id}">${r.name} (${r.unit})</option>`);
  }

  function setChannel(ch, el) {
    activeChannel = ch;
    document.querySelectorAll(".ch-btn").forEach(b => b.classList.remove("active"));
    el.classList.add("active");
    renderTables();
  }

  function renderTables() {
    const deck = document.getElementById("tableDeck");
    deck.innerHTML = "";
    TABLES.filter(t => activeChannel === "ALL" || t.channel === activeChannel).forEach(tbl => {
      const sum = tbl.cart.reduce((a, c) => a + (c.price * c.qty), 0);
      const isOcc = tbl.cart.length > 0;
      deck.innerHTML += `
        <div class="tbl-card ${tbl.id === currentTableId ? 'active' : ''} ${isOcc ? 'occupied' : 'vacant'}" onclick="selectTable('${tbl.id}')">
          <div style="font-weight:700; font-size:12px;">${tbl.name}</div>
          <div style="font-size:10px; color:var(--muted);">${tbl.channel}</div>
          <div style="font-size:12px; font-weight:800; margin-top:2px;">${sum > 0 ? '₹' + sum.toFixed(2) : '-'}</div>
        </div>
      `;
    });
  }

  function selectTable(id) {
    currentTableId = id;
    const t = TABLES.find(x => x.id === id);
    document.getElementById("lblDeskTable").innerText = `${t.name} (${t.channel})`;
    renderTables();
    renderCart();
  }

  function renderCategories() {
    const cats = ["All", ...new Set(MASTER_MENU.filter(m => m.is_active).map(m => m.category))];
    const strip = document.getElementById("catStrip");
    strip.innerHTML = "";
    cats.forEach(c => strip.innerHTML += `<div class="chip ${c === activeCat ? 'active' : ''}" onclick="setCategory('${c}')">${c}</div>`);
  }

  function setCategory(c) {
    activeCat = c;
    renderCategories();
    renderMenu();
  }

  function filterCatalog() {
    const q = document.getElementById("menuSearch").value.toLowerCase();
    renderMenu(q);
  }

  function renderMenu(query = "") {
    const grid = document.getElementById("menuGrid");
    grid.innerHTML = "";
    MASTER_MENU.filter(m => {
      const matchCat = (activeCat === "All" || m.category === activeCat);
      const matchQ = (!query || m.name_mr.toLowerCase().includes(query) || m.name_en.toLowerCase().includes(query) || m.id.toLowerCase().includes(query));
      return m.is_active && matchCat && matchQ;
    }).forEach(m => {
      grid.innerHTML += `
        <div class="food-card" onclick="addToCart('${m.id}')">
          <div>
            <span class="diet-dot" style="background:${m.diet==='VEG'?'var(--veg)':'var(--nonveg)'};"></span>
            <span style="font-size:9px; color:var(--muted);">${m.category}</span>
            <div style="font-weight:700; font-size:11px; margin-top:2px;">${m.name_mr}</div>
            <div style="font-size:10px; color:var(--muted);">${m.name_en}</div>
          </div>
          <div style="font-weight:800; color:var(--brand); font-size:12px;">₹${m.price.toFixed(2)}</div>
        </div>
      `;
    });
  }

  function addToCart(id) {
    const t = TABLES.find(x => x.id === currentTableId);
    const m = MASTER_MENU.find(x => x.id === id);
    const exist = t.cart.find(c => c.id === id);
    if(exist) exist.qty += 1;
    else t.cart.push({ id: m.id, name: m.name_mr, en: m.name_en, price: m.price, station: m.station, bom: JSON.parse(m.bom_json || '[]'), qty: 1 });
    renderCart();
    renderTables();
  }

  function updateQty(id, delta) {
    const t = TABLES.find(x => x.id === currentTableId);
    const item = t.cart.find(c => c.id === id);
    if(!item) return;
    item.qty += delta;
    if(item.qty <= 0) t.cart = t.cart.filter(c => c.id !== id);
    renderCart();
    renderTables();
  }

  function renderCart() {
    const t = TABLES.find(x => x.id === currentTableId);
    const tbody = document.getElementById("cartTbody");
    tbody.innerHTML = "";
    t.cart.forEach(i => {
      const line = i.price * i.qty;
      tbody.innerHTML += `
        <tr>
          <td><b>${i.name}</b><br><span style="font-size:9px; color:var(--muted);">${i.en}</span></td>
          <td>
            <div class="qty-box">
              <button class="qty-btn" onclick="updateQty('${i.id}', -1)">-</button>
              <span>${i.qty}</span>
              <button class="qty-btn" onclick="updateQty('${i.id}', 1)">+</button>
            </div>
          </td>
          <td>₹${i.price}</td>
          <td>₹${line.toFixed(2)}</td>
        </tr>
      `;
    });
    recomputeTotals();
  }

  function recomputeTotals() {
    const t = TABLES.find(x => x.id === currentTableId);
    const sub = t.cart.reduce((a, c) => a + (c.price * c.qty), 0);
    const disc = parseFloat(document.getElementById("txtDisc").value) || 0.0;
    const isParcel = (t.channel === "TAKEAWAY" || t.channel === "DELIVERY");
    const packaging = (isParcel && sub > 0) ? 25.0 : 0.0;

    const taxable = Math.max(0, sub - disc + packaging);
    const gst = taxable * 0.05;
    const grand = taxable + gst;

    document.getElementById("txtSub").innerText = `₹${sub.toFixed(2)}`;
    document.getElementById("txtPackaging").innerText = `₹${packaging.toFixed(2)}`;
    document.getElementById("txtGST").innerText = `₹${gst.toFixed(2)}`;
    document.getElementById("txtGrand").innerText = `₹${grand.toFixed(2)}`;
  }

  function voidCart() {
    if(!confirm("Void running items on this table?")) return;
    const t = TABLES.find(x => x.id === currentTableId);
    t.cart = [];
    renderCart();
    renderTables();
  }

  function fireKOT() {
    const t = TABLES.find(x => x.id === currentTableId);
    if(t.cart.length === 0) return alert("Select dishes first!");

    let slip = `
      <div style="text-align:center;">
        <b>** KOT #${t.kotIter} - ${SETTINGS.restaurant_name || 'PUSHPA KHANAWAL'} **</b><br>
        Target: ${t.name} (${t.channel}) | Time: ${new Date().toLocaleTimeString()}
      </div>
      <hr style="margin:6px 0; border:0; border-top:1px dashed #000;">
    `;
    t.cart.forEach(i => slip += `<div style="display:flex; justify-content:space-between;"><span>• ${i.name} [${i.station}]</span><b>x${i.qty}</b></div>`);

    document.getElementById("kotContent").innerHTML = slip;
    document.getElementById("kotModal").style.display = "flex";
    t.kotIter += 1;
  }

  function openUpiModal() {
    const t = TABLES.find(x => x.id === currentTableId);
    if(t.cart.length === 0) return alert("Cart is empty!");
    document.getElementById("upiModalAmount").innerText = document.getElementById("txtGrand").innerText;
    document.getElementById("upiModal").style.display = "flex";
  }

  function openSplitModal() {
    const t = TABLES.find(x => x.id === currentTableId);
    if(t.cart.length === 0) return alert("Cart is empty!");
    calcSplit();
    document.getElementById("splitModal").style.display = "flex";
  }

  function calcSplit() {
    const total = parseFloat(document.getElementById("txtGrand").innerText.replace("₹", "")) || 0;
    const covers = parseInt(document.getElementById("splitCovers").value) || 2;
    document.getElementById("splitPerHead").innerText = `Per Person (${covers} guests): ₹${(total / covers).toFixed(2)}`;
  }

  async function settleBill(mode) {
    const t = TABLES.find(x => x.id === currentTableId);
    if(t.cart.length === 0) return alert("Cart is empty!");

    const sub = t.cart.reduce((a, c) => a + (c.price * c.qty), 0);
    const disc = parseFloat(document.getElementById("txtDisc").value) || 0.0;
    const isParcel = (t.channel === "TAKEAWAY" || t.channel === "DELIVERY");
    const packaging = (isParcel && sub > 0) ? 25.0 : 0.0;
    const taxable = Math.max(0, sub - disc + packaging);
    const halfTax = (taxable * 0.05) / 2;
    const grand = taxable + (taxable * 0.05);

    let bom = [];
    t.cart.forEach(c => c.bom.forEach(b => bom.push({ item_id: b.id, qty: b.qty * c.qty })));

    const payload = {
      order_id: `PK-${Date.now().toString().slice(-6)}`,
      channel: t.channel,
      table_or_target: t.name,
      customer_name: document.getElementById("custName").value || "Walk-in",
      customer_phone: document.getElementById("custPhone").value || "",
      subtotal: sub,
      packaging_charge: packaging,
      discount_amount: disc,
      discount_reason: document.getElementById("txtDiscReason").value || "",
      taxable_amount: taxable,
      cgst: halfTax,
      sgst: halfTax,
      grand_total: grand,
      payment_mode: mode,
      items: t.cart,
      bom_deductions: bom
    };

    const res = await fetch("/api/orders/settle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if(res.ok) {
      printThermalBillWithQR(payload);
      closeModal('upiModal');
      closeModal('splitModal');
      t.cart = [];
      document.getElementById("txtDisc").value = "";
      document.getElementById("txtDiscReason").value = "";
      renderCart();
      renderTables();
    }
  }

  function printThermalBillWithQR(inv) {
    const slip = document.getElementById("thermalPrintSlip");
    slip.style.display = "block";
    slip.innerHTML = `
      <div style="text-align:center;">
        <h2 style="margin:0;">${SETTINGS.restaurant_name || 'पुष्पा खानावळ'}</h2>
        <div>${SETTINGS.address || ''}</div>
        <div>GSTIN: ${SETTINGS.gstin || '-'} | FSSAI: ${SETTINGS.fssai || '-'}</div>
        <hr style="margin:4px 0;">
        <div><b>TAX INVOICE: ${inv.order_id}</b></div>
        <div>Date: ${new Date().toLocaleString()}</div>
        <div>Target: ${inv.table_or_target} | Mode: ${inv.payment_mode}</div>
        <hr style="margin:4px 0;">
      </div>
      <table style="width:100%; border-collapse:collapse; font-size:11px;">
        ${inv.items.map(i => `<tr><td>${i.name} x${i.qty}</td><td style="text-align:right;">₹${(i.price*i.qty).toFixed(2)}</td></tr>`).join('')}
      </table>
      <hr style="margin:4px 0;">
      <div style="display:flex; justify-content:space-between;"><span>Subtotal:</span><span>₹${inv.subtotal.toFixed(2)}</span></div>
      ${inv.discount_amount > 0 ? `<div style="display:flex; justify-content:space-between;"><span>Discount:</span><span>-₹${inv.discount_amount.toFixed(2)}</span></div>` : ''}
      ${inv.packaging_charge > 0 ? `<div style="display:flex; justify-content:space-between;"><span>Packaging:</span><span>₹${inv.packaging_charge.toFixed(2)}</span></div>` : ''}
      <div style="display:flex; justify-content:space-between;"><span>CGST (2.5%):</span><span>₹${inv.cgst.toFixed(2)}</span></div>
      <div style="display:flex; justify-content:space-between;"><span>SGST (2.5%):</span><span>₹${inv.sgst.toFixed(2)}</span></div>
      <hr style="margin:4px 0;">
      <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:bold;">
        <span>NET PAYABLE:</span><span>₹${inv.grand_total.toFixed(2)}</span>
      </div>
      <div style="text-align:center; margin-top:8px;">
        <div id="billQrSlot" style="display:inline-block;"></div>
        <div style="font-size:10px; margin-top:2px;">Scan & Pay via any UPI App</div>
        <div style="margin-top:4px;">${SETTINGS.footer_note || 'Thank You! Visit Again'}</div>
      </div>
    `;

    new QRCode(document.getElementById("billQrSlot"), {
      text: `upi://pay?pa=${SETTINGS.upi_vpa || 'pushpakhanawal@upi'}&pn=${encodeURIComponent(SETTINGS.restaurant_name || 'Pushpa Khanawal')}&am=${inv.grand_total.toFixed(2)}`,
      width: 100, height: 100
    });

    setTimeout(() => {
      window.print();
      slip.style.display = "none";
    }, 250);
  }

  function addCustomItem() {
    const name = prompt("Dish Name (मराठी/English):", "Extra Special Bowl");
    if(!name) return;
    const price = parseFloat(prompt("Price (₹):", "50"));
    if(!price) return;
    const t = TABLES.find(x => x.id === currentTableId);
    t.cart.push({ id: `OPEN-${Date.now().toString().slice(-4)}`, name: name, en: "Open Item", price: price, station: "HOT_CURRY", bom: [], qty: 1 });
    renderCart();
    renderTables();
  }

  function mergeTable() {
    const dest = prompt("Enter Target Table to merge into (e.g. Table 2):");
    if(!dest) return;
    const destTbl = TABLES.find(t => t.name.toLowerCase() === dest.toLowerCase());
    const srcTbl = TABLES.find(t => t.id === currentTableId);
    if(!destTbl) return alert("Target table not found!");
    destTbl.cart = [...destTbl.cart, ...srcTbl.cart];
    srcTbl.cart = [];
    alert(`Merged ${srcTbl.name} into ${destTbl.name}!`);
    renderCart();
    renderTables();
  }

  // --- CATALOG MASTER TOOL ---
  function loadMenuEditor() {
    const tbody = document.getElementById("menuEditorTbody");
    tbody.innerHTML = "";
    MASTER_MENU.forEach(m => {
      tbody.innerHTML += `
        <tr>
          <td><b>${m.id}</b></td>
          <td>${m.name_mr}</td>
          <td>${m.name_en}</td>
          <td>${m.category}</td>
          <td>${m.station}</td>
          <td><b>₹${m.price.toFixed(2)}</b></td>
          <td><span style="color:${m.is_active?'green':'red'}; font-weight:700;">${m.is_active?'Active':'86ed'}</span></td>
          <td>
            <button onclick="editMenuItem('${m.id}')" style="cursor:pointer; padding:2px 6px;">Edit</button>
            <button onclick="toggleItemStock('${m.id}')" style="cursor:pointer; padding:2px 6px;">${m.is_active?'86 Off':'Turn On'}</button>
          </td>
        </tr>
      `;
    });
  }

  function editMenuItem(id) {
    const m = MASTER_MENU.find(x => x.id === id);
    document.getElementById("mId").value = m.id;
    document.getElementById("mNameMr").value = m.name_mr;
    document.getElementById("mNameEn").value = m.name_en;
    document.getElementById("mCat").value = m.category;
    document.getElementById("mPrice").value = m.price;
    document.getElementById("mStation").value = m.station;
    document.getElementById("mDiet").value = m.diet;
    document.getElementById("mBom").value = m.bom_json;
    document.getElementById("lblMenuFormTitle").innerText = `Edit: ${m.name_en}`;
  }

  async function toggleItemStock(id) {
    const m = MASTER_MENU.find(x => x.id === id);
    m.is_active = m.is_active ? 0 : 1;
    await fetch("/api/menu/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(m)
    });
    await fetchMenu();
    loadMenuEditor();
    renderCategories();
    renderMenu();
  }

  async function saveMenuItem() {
    const payload = {
      id: document.getElementById("mId").value,
      name_mr: document.getElementById("mNameMr").value,
      name_en: document.getElementById("mNameEn").value,
      category: document.getElementById("mCat").value,
      price: parseFloat(document.getElementById("mPrice").value),
      station: document.getElementById("mStation").value,
      diet: document.getElementById("mDiet").value,
      is_active: 1,
      bom_json: document.getElementById("mBom").value || "[]"
    };
    if(!payload.id || !payload.name_mr || isNaN(payload.price)) return alert("Fill code, Marathi name, and price!");
    await fetch("/api/menu/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    alert("Dish Catalog Updated!");
    await fetchMenu();
    loadMenuEditor();
    renderCategories();
    renderMenu();
  }

  // --- OPERATIONS & REPORTS ---
  async function loadAnalytics() {
    const res = await fetch("/api/reports/analytics");
    const data = await res.json();
    const orders = data.orders;
    const rev = orders.reduce((s, o) => s + o.grand_total, 0);
    const cash = orders.filter(o => o.payment_mode === "CASH").reduce((s, o) => s + o.grand_total, 0);
    const upi = orders.filter(o => o.payment_mode === "STATIC_UPI").reduce((s, o) => s + o.grand_total, 0);
    const gst = orders.reduce((s, o) => s + (o.cgst + o.sgst), 0);

    document.getElementById("reportStats").innerHTML = `
      <div style="background:#f8fafc; border:1px solid var(--border); padding:10px; border-radius:6px; flex:1;">Gross Revenue: <b>₹${rev.toFixed(2)}</b></div>
      <div style="background:#f8fafc; border:1px solid var(--border); padding:10px; border-radius:6px; flex:1;">Cash Drawer: <b>₹${cash.toFixed(2)}</b></div>
      <div style="background:#f8fafc; border:1px solid var(--border); padding:10px; border-radius:6px; flex:1;">Bank UPI: <b>₹${upi.toFixed(2)}</b></div>
      <div style="background:#f8fafc; border:1px solid var(--border); padding:10px; border-radius:6px; flex:1;">GST Liability (5%): <b>₹${gst.toFixed(2)}</b></div>
    `;

    const tbody = document.getElementById("salesJournalTbody");
    tbody.innerHTML = "";
    orders.forEach(o => {
      tbody.innerHTML += `<tr><td>${o.order_id}</td><td>${o.timestamp}</td><td>${o.channel}</td><td>${o.table_or_target}</td><td>₹${o.subtotal.toFixed(2)}</td><td>₹${o.cgst.toFixed(2)}</td><td>₹${o.sgst.toFixed(2)}</td><td><b>₹${o.grand_total.toFixed(2)}</b></td><td>${o.payment_mode}</td></tr>`;
    });
  }

  // --- TDS & INVENTORY ---
  function calcTdsPreview() {
    const qty = parseFloat(document.getElementById("pQty").value) || 0;
    const rate = parseFloat(document.getElementById("pRate").value) || 0;
    const sec = document.getElementById("pTdsSec").value;
    const gross = qty * rate;
    const rates = { "194C_INDIV": 0.01, "194C_CORP": 0.02, "194Q": 0.001, "194J": 0.10 };
    const tds = gross * (rates[sec] || 0.0);
    document.getElementById("lblGross").innerText = `₹${gross.toFixed(2)}`;
    document.getElementById("lblTds").innerText = `₹${tds.toFixed(2)}`;
    document.getElementById("lblNet").innerText = `₹${(gross - tds).toFixed(2)}`;
  }

  async function commitInward() {
    const payload = {
      item_id: document.getElementById("pItem").value,
      qty: parseFloat(document.getElementById("pQty").value),
      unit_rate: parseFloat(document.getElementById("pRate").value),
      vendor_name: document.getElementById("pVendor").value || "General Mandi Vendor",
      tds_section: document.getElementById("pTdsSec").value,
      memo: "Raw Material Purchase"
    };
    if(!payload.qty || !payload.unit_rate) return alert("Fill quantity and rate!");
    await fetch("/api/inventory/inward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    alert("Inward committed & TDS posted!");
    await fetchInventory();
    loadInventoryView();
  }

  function loadInventoryView() {
    const tbody = document.getElementById("rawStockTbody");
    tbody.innerHTML = "";
    RAW_STOCK.forEach(r => tbody.innerHTML += `<tr><td><b>${r.id}</b></td><td>${r.name}</td><td>${r.stock.toFixed(2)}</td><td>${r.unit}</td><td>₹${r.cost_per_unit}</td></tr>`);
  }

  async function loadLedgerView() {
    const res = await fetch("/api/reports/ledger");
    const data = await res.json();
    const tbody = document.getElementById("ledgerTbody");
    tbody.innerHTML = "";
    data.forEach(r => tbody.innerHTML += `<tr><td>${r.entry_id}</td><td>${r.timestamp}</td><td><b>${r.voucher_id}</b></td><td>${r.account_head}</td><td style="color:${r.direction==='DEBIT'?'green':'#ea580c'}; font-weight:700;">${r.direction}</td><td>₹${r.amount.toFixed(2)}</td><td>${r.notes || '-'}</td></tr>`);
  }

  // --- TAB CONTROLLER ---
  function switchTab(tab) {
    document.querySelectorAll(".view-panel").forEach(p => p.style.display = "none");
    document.getElementById("viewPOS").style.display = tab === "POS" ? "grid" : "none";
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(`tab${tab.charAt(0) + tab.slice(1).toLowerCase()}`).classList.add("active");

    if(tab === "MENU_EDITOR") { document.getElementById("viewMENU_EDITOR").style.display = "block"; loadMenuEditor(); }
    if(tab === "ANALYTICS") { document.getElementById("viewANALYTICS").style.display = "block"; loadAnalytics(); }
    if(tab === "INVENTORY") { document.getElementById("viewINVENTORY").style.display = "block"; loadInventoryView(); }
    if(tab === "LEDGER") { document.getElementById("viewLEDGER").style.display = "block"; loadLedgerView(); }
    if(tab === "SETTINGS") { document.getElementById("viewSETTINGS").style.display = "block"; fetchSettings(); }
  }

  function closeModal(id) { document.getElementById(id).style.display = "none"; }
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return ENTERPRISE_UI
