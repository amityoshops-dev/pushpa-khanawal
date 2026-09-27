import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="पुष्पा खानावळ ERP",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "khanawal_production.db"

# ----------------- DATABASE SETUP -----------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Raw Inventory Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id TEXT PRIMARY KEY,
                item_name TEXT NOT NULL,
                current_stock REAL DEFAULT 0.0,
                unit TEXT NOT NULL
            )
        """)
        # Stock Movements Audit
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT,
                movement_type TEXT,
                qty REAL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Orders / Invoices
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                table_name TEXT,
                subtotal REAL,
                tax REAL,
                grand_total REAL,
                payment_mode TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # General Accounting Ledger
        cur.execute("""
            CREATE TABLE IF NOT EXISTS general_ledger (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_id TEXT,
                account_head TEXT,
                direction TEXT,
                amount REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Seed Base Stock
        cur.execute("SELECT COUNT(*) FROM inventory")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)", [
                ("RAW_MUTTON", "Mutton (मटण)", 25.0, "KG"),
                ("RAW_CHICKEN", "Chicken (चिकन)", 30.0, "KG"),
                ("RAW_FLOUR", "Jowar/Bajra Flour (पीठ)", 50.0, "KG"),
                ("RAW_OIL", "Cooking Oil (तेल)", 20.0, "Liter")
            ])
        conn.commit()

init_db()

# ----------------- MENU & BOM CONFIG -----------------
MENU = {
    "Special Mutton Thali (मटण थाळी)": {
        "price": 380, "cat": "Thali",
        "bom": [("RAW_MUTTON", 0.25), ("RAW_FLOUR", 0.1)]
    },
    "Chicken Thali (चिकन थाळी)": {
        "price": 280, "cat": "Thali",
        "bom": [("RAW_CHICKEN", 0.25)]
    },
    "Special Veg Thali (व्हेज थाळी)": {
        "price": 200, "cat": "Thali",
        "bom": []
    },
    "Jowar Bhakri (गरम ज्वारी भाकरी)": {
        "price": 30, "cat": "Breads",
        "bom": [("RAW_FLOUR", 0.08)]
    },
    "Tambda/Pandhra Rassa Bowl": {
        "price": 50, "cat": "Curries",
        "bom": []
    },
    "Solkadhi (सोलकढी)": {
        "price": 40, "cat": "Beverages",
        "bom": []
    }
}

TABLES = ["Table 1", "Table 2", "Table 3", "Table 4", "Family Room", "Takeaway (पार्सल)"]

# ----------------- SESSION STATE -----------------
if "table_orders" not in st.session_state:
    st.session_state.table_orders = {t: {} for t in TABLES}

# Helper: Free Static UPI QR (Zero Gateway Fees)
def get_static_upi_qr(vpa="pushpakhanawal@upi", name="Pushpa Khanawal"):
    upi_payload = f"upi://pay?pa={vpa}&pn={name}"
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(upi_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ----------------- SIDEBAR & NAVIGATION -----------------
st.sidebar.title("🍲 पुष्पा खानावळ")
st.sidebar.caption("Pushpa Khanawal ERP v5.0 (Offline Engine)")
menu_choice = st.sidebar.radio(
    "Navigation",
    ["Counter POS & KOT", "Stock Inventory (Add/Sub)", "General Accounting Ledger", "Day-End MIS Summary"]
)

# ----------------- VIEW 1: COUNTER POS & KOT -----------------
if menu_choice == "Counter POS & KOT":
    col_tables, col_menu, col_bill = st.columns([1.2, 2.3, 1.8])

    with col_tables:
        st.subheader("Tables")
        selected_table = st.radio("Select Table/Room", TABLES)
        
        # Display occupied indicator
        active_items = st.session_state.table_orders[selected_table]
        if active_items:
            st.warning(f"Status: In Service ({sum(active_items.values())} items)")
        else:
            st.success("Status: Vacant")

    with col_menu:
        st.subheader("Menu Catalog")
        categories = ["All"] + list(set(item["cat"] for item in MENU.values()))
        cat_filter = st.selectbox("Category", categories)
        
        filtered_items = {k: v for k, v in MENU.items() if cat_filter == "All" or v["cat"] == cat_filter}
        
        for name, meta in filtered_items.items():
            m_col1, m_col2 = st.columns([3, 1])
            m_col1.write(f"**{name}** — ₹{meta['price']}")
            if m_col2.button("Add", key=f"add_{name}"):
                current_cart = st.session_state.table_orders[selected_table]
                current_cart[name] = current_cart.get(name, 0) + 1
                st.rerun()

    with col_bill:
        st.subheader(f"Bill: {selected_table}")
        cart = st.session_state.table_orders[selected_table]
        
        if not cart:
            st.info("No items added yet.")
        else:
            subtotal = 0
            for item_name, qty in list(cart.items()):
                price = MENU[item_name]["price"]
                line_total = price * qty
                subtotal += line_total
                
                b_c1, b_c2, b_c3 = st.columns([3, 1, 1])
                b_c1.write(f"{item_name}")
                b_c2.write(f"x{qty}")
                if b_c3.button("✖", key=f"del_{item_name}"):
                    del cart[item_name]
                    st.rerun()

            cgst = subtotal * 0.025
            sgst = subtotal * 0.025
            grand_total = subtotal + cgst + sgst

            st.divider()
            st.write(f"Subtotal: **₹{subtotal:.2f}**")
            st.write(f"GST (5%): **₹{cgst + sgst:.2f}**")
            st.markdown(f"### Total: ₹{grand_total:.2f}")

            # KOT Print simulation
            if st.button("🖨️ Fire Kitchen KOT", use_container_width=True):
                st.success(f"KOT fired for {selected_table} to Kitchen Display & Printer!")

            st.divider()
            pay_mode = st.radio("Settlement Mode", ["Cash (रोख)", "Static UPI (QR)"], horizontal=True)

            if pay_mode == "Static UPI (QR)":
                st.image(get_static_upi_qr(), caption="Permanent Merchant UPI (Zero Processing Fee)", width=150)
                st.caption(f"Instruct customer to scan and pay ₹{grand_total:.2f}")

            if st.button("✅ Settle & Close Table", type="primary", use_container_width=True):
                inv_id = f"PK-{datetime.now().strftime('%d%H%M%S')}"
                
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    # 1. Record Order
                    cur.execute("""
                        INSERT INTO orders (order_id, table_name, subtotal, tax, grand_total, payment_mode)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (inv_id, selected_table, subtotal, (cgst + sgst), grand_total, pay_mode))
                    
                    # 2. Financial Ledger Entries
                    debit_acc = "Cash Drawer" if "Cash" in pay_mode else "Bank UPI Account"
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'DEBIT', ?)",
                                (inv_id, debit_acc, grand_total))
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'CREDIT', ?)",
                                (inv_id, "Food Sales Revenue", subtotal))
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'CREDIT', ?)",
                                (inv_id, "Output GST", cgst + sgst))

                    # 3. Auto-deduct Raw Material via BOM
                    for item_name, qty in cart.items():
                        for raw_id, needed_per_dish in MENU[item_name]["bom"]:
                            total_consumed = needed_per_dish * qty
                            cur.execute("UPDATE inventory SET current_stock = MAX(0, current_stock - ?) WHERE item_id = ?",
                                        (total_consumed, raw_id))
                            cur.execute("INSERT INTO stock_audit (item_id, movement_type, qty, reason) VALUES (?, 'SALE_AUTO', ?, ?)",
                                        (raw_id, total_consumed, f"Order {inv_id}"))
                    conn.commit()

                st.session_state.table_orders[selected_table] = {}
                st.success(f"Order {inv_id} Settled Successfully!")
                st.rerun()

# ----------------- VIEW 2: MANUAL STOCK (ADD / SUB) -----------------
elif menu_choice == "Stock Inventory (Add/Sub)":
    st.header("Raw Material Inventory Ledger")
    
    with sqlite3.connect(DB_PATH) as conn:
        inv_df = pd.read_sql_query("SELECT item_id as 'ID', item_name as 'Ingredient', current_stock as 'Stock Available', unit as 'Unit' FROM inventory", conn)
    
    st.dataframe(inv_df, use_container_width=True)

    st.subheader("Manual Stock Adjustment (Purchase / Wastage)")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        selected_item = st.selectbox("Select Ingredient", inv_df["ID"].tolist())
    with col2:
        action_type = st.selectbox("Action", ["PURCHASE_ADD (+)", "MANUAL_SUBTRACT (-)"])
    with col3:
        adj_qty = st.number_input("Quantity", min_value=0.1, step=0.5)
    with col4:
        reason_note = st.text_input("Reason / Memo", "Market Purchase")

    if st.button("Commit Stock Adjustment", type="primary"):
        delta = adj_qty if "ADD" in action_type else -abs(adj_qty)
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE inventory SET current_stock = current_stock + ? WHERE item_id = ?", (delta, selected_item))
            cur.execute("INSERT INTO stock_audit (item_id, movement_type, qty, reason) VALUES (?, ?, ?, ?)",
                        (selected_item, action_type, abs(adj_qty), reason_note))
            conn.commit()
        st.success("Stock updated successfully!")
        st.rerun()

# ----------------- VIEW 3: GENERAL ACCOUNTING LEDGER -----------------
elif menu_choice == "General Accounting Ledger":
    st.header("General Ledger (Real-time Double Entry Audit)")
    with sqlite3.connect(DB_PATH) as conn:
        ledger_df = pd.read_sql_query("SELECT entry_id, timestamp, voucher_id, account_head, direction, amount FROM general_ledger ORDER BY entry_id DESC LIMIT 50", conn)
    
    st.dataframe(ledger_df, use_container_width=True)

# ----------------- VIEW 4: DAY-END MIS SUMMARY -----------------
elif menu_choice == "Day-End MIS Summary":
    st.header("Daily Business Intelligence & Collections MIS")
    with sqlite3.connect(DB_PATH) as conn:
        orders_df = pd.read_sql_query("SELECT * FROM orders", conn)

    if orders_df.empty:
        st.info("No orders processed yet today.")
    else:
        total_sales = orders_df["grand_total"].sum()
        total_cash = orders_df[orders_df["payment_mode"].str.contains("Cash")]["grand_total"].sum()
        total_upi = orders_df[orders_df["payment_mode"].str.contains("UPI")]["grand_total"].sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Gross Revenue", f"₹{total_sales:.2f}")
        m2.metric("Total Cash in Drawer", f"₹{total_cash:.2f}")
        m3.metric("Total Bank UPI Collections", f"₹{total_upi:.2f}")

        st.subheader("Sales Audit Log")
        st.dataframe(orders_df[["order_id", "timestamp", "table_name", "subtotal", "tax", "grand_total", "payment_mode"]], use_container_width=True)