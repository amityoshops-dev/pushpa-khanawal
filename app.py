import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO

st.set_page_config(page_title="पुष्पा खानावळ ERP", page_icon="🍲", layout="wide")
DB_PATH = "pushpa_khanawal.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS inventory (item_id TEXT PRIMARY KEY, name TEXT NOT NULL, stock REAL DEFAULT 0.0, unit TEXT NOT NULL)")
        cur.execute("CREATE TABLE IF NOT EXISTS stock_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, change_type TEXT, qty REAL, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, table_name TEXT, subtotal REAL, cgst REAL, sgst REAL, grand_total REAL, payment_mode TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS general_ledger (entry_id INTEGER PRIMARY KEY AUTOINCREMENT, voucher_id TEXT, account_head TEXT, direction TEXT, amount REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("SELECT COUNT(*) FROM inventory")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)", [
                ("RAW_MUTTON", "Mutton (मटण)", 25.0, "KG"),
                ("RAW_CHICKEN", "Chicken (चिकन)", 30.0, "KG"),
                ("RAW_FLOUR", "Jowar/Bajra Flour (पीठ)", 50.0, "KG"),
                ("RAW_OIL", "Cooking Oil (तेल)", 20.0, "Liter"),
                ("RAW_PANEER", "Paneer (पनीर)", 8.0, "KG")
            ])
        conn.commit()

init_db()

MENU = {
    "Special Mutton Thali (स्पेशल मटण थाळी)": {"price": 380, "cat": "Thali", "bom": [("RAW_MUTTON", 0.25), ("RAW_FLOUR", 0.1)]},
    "Chicken Thali (चिकन थाळी)": {"price": 280, "cat": "Thali", "bom": [("RAW_CHICKEN", 0.25)]},
    "Special Veg Thali (व्हेज थाळी)": {"price": 200, "cat": "Thali", "bom": [("RAW_PANEER", 0.1)]},
    "Jowar Bhakri (गरम ज्वारी भाकरी)": {"price": 30, "cat": "Breads", "bom": [("RAW_FLOUR", 0.08)]},
    "Bajra Bhakri with Butter (बाजरी भाकरी)": {"price": 35, "cat": "Breads", "bom": [("RAW_FLOUR", 0.08)]},
    "Tambda Rassa Bowl (तांबडा रस्सा)": {"price": 50, "cat": "Curries", "bom": []},
    "Pandhra Rassa Bowl (पांढरा रस्सा)": {"price": 50, "cat": "Curries", "bom": []},
    "Solkadhi Glass (सोलकढी)": {"price": 40, "cat": "Beverages", "bom": []}
}

TABLES = ["Table 1", "Table 2", "Table 3", "Table 4", "Family Room", "Takeaway Counter"]

if "active_orders" not in st.session_state:
    st.session_state.active_orders = {t: {} for t in TABLES}

def generate_free_upi_qr(vpa="pushpakhanawal@upi", name="Pushpa Khanawal"):
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(f"upi://pay?pa={vpa}&pn={name}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

st.sidebar.title("🍲 पुष्पा खानावळ")
st.sidebar.caption("Pushpa Khanawal Cloud-Ready ERP v5.2")
selected_view = st.sidebar.radio("Navigation", ["POS & Kitchen KOT", "Stock Inventory (Add/Sub)", "General Accounting Ledger", "Daily MIS Dashboard"])

if selected_view == "POS & Kitchen KOT":
    col_tables, col_menu, col_bill = st.columns([1.2, 2.3, 1.8])
    with col_tables:
        st.subheader("Tables")
        active_tbl = st.radio("Select Table/Room", TABLES)
        current_cart = st.session_state.active_orders[active_tbl]
        if current_cart:
            st.warning(f"In Service: {sum(current_cart.values())} items")
        else:
            st.success("Vacant")

    with col_menu:
        st.subheader("Menu")
        cats = ["All"] + sorted(list(set(m["cat"] for m in MENU.values())))
        cat_select = st.selectbox("Category", cats)
        filtered = {k: v for k, v in MENU.items() if cat_select == "All" or v["cat"] == cat_select}
        for name, meta in filtered.items():
            r1, r2 = st.columns([3, 1])
            r1.write(f"**{name}** — ₹{meta['price']}")
            if r2.button("Add", key=f"btn_{name}"):
                current_cart[name] = current_cart.get(name, 0) + 1
                st.rerun()

    with col_bill:
        st.subheader(f"Bill: {active_tbl}")
        if not current_cart:
            st.info("No running items.")
        else:
            subtotal = 0
            for item_name, qty in list(current_cart.items()):
                price = MENU[item_name]["price"]
                line = price * qty
                subtotal += line
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"{item_name}")
                c2.write(f"x{qty}")
                if c3.button("✖", key=f"del_{item_name}"):
                    del current_cart[item_name]
                    st.rerun()

            cgst = subtotal * 0.025
            sgst = subtotal * 0.025
            grand_total = subtotal + cgst + sgst
            st.divider()
            st.write(f"Subtotal: **₹{subtotal:.2f}**")
            st.write(f"GST (5%): **₹{cgst + sgst:.2f}**")
            st.markdown(f"### Total: ₹{grand_total:.2f}")

            if st.button("🖨️ Fire Kitchen KOT", use_container_width=True):
                st.toast(f"KOT Sent to Kitchen for {active_tbl}!")

            st.divider()
            settle_mode = st.radio("Payment Mode", ["Cash (रोख)", "Free Static UPI (QR)"], horizontal=True)
            if settle_mode == "Free Static UPI (QR)":
                st.image(generate_free_upi_qr(), caption="Permanent Free Merchant QR", width=140)
                st.caption(f"Ask customer to enter ₹{grand_total:.2f}")

            if st.button("✅ Settle & Clear Table", type="primary", use_container_width=True):
                order_id = f"PK-{datetime.now().strftime('%d%H%M%S')}"
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                                (order_id, active_tbl, subtotal, cgst, sgst, grand_total, settle_mode))
                    acc_head = "Cash Drawer" if "Cash" in settle_mode else "Bank Account"
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, ?, 'DEBIT', ?)", (order_id, acc_head, grand_total))
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, 'Food Sales Revenue', 'CREDIT', ?)", (order_id, subtotal))
                    cur.execute("INSERT INTO general_ledger (voucher_id, account_head, direction, amount) VALUES (?, 'Output GST (5%)', 'CREDIT', ?)", (order_id, cgst + sgst))
                    for item_name, qty in current_cart.items():
                        for raw_id, need in MENU[item_name]["bom"]:
                            cur.execute("UPDATE inventory SET stock = MAX(0, stock - ?) WHERE item_id = ?", (need * qty, raw_id))
                            cur.execute("INSERT INTO stock_audit (item_id, change_type, qty, reason) VALUES (?, 'SALE_AUTO', ?, ?)", (raw_id, need * qty, f"Order {order_id}"))
                    conn.commit()
                st.session_state.active_orders[active_tbl] = {}
                st.success(f"Order {order_id} Settled Successfully!")
                st.rerun()

elif selected_view == "Stock Inventory (Add/Sub)":
    st.header("Raw Material Inventory Ledger")
    with sqlite3.connect(DB_PATH) as conn:
        inv_df = pd.read_sql_query("SELECT item_id as 'Code', name as 'Raw Material', stock as 'Current Stock', unit as 'Unit' FROM inventory", conn)
    st.dataframe(inv_df, use_container_width=True)
    st.subheader("Manual Stock Adjustment")
    c1, c2, c3, c4 = st.columns(4)
    with c1: chosen_id = st.selectbox("Ingredient", inv_df["Code"].tolist())
    with c2: action = st.selectbox("Action Type", ["PURCHASE_ADD (+)", "MANUAL_DEDUCT (-)"])
    with c3: val = st.number_input("Quantity", min_value=0.1, step=0.5)
    with c4: note = st.text_input("Reason / Note", "Direct Mandi Purchase")
    if st.button("Commit Stock Adjustment", type="primary"):
        delta = val if "ADD" in action else -abs(val)
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE inventory SET stock = stock + ? WHERE item_id = ?", (delta, chosen_id))
            cur.execute("INSERT INTO stock_audit (item_id, change_type, qty, reason) VALUES (?, ?, ?, ?)", (chosen_id, action, abs(val), note))
            conn.commit()
        st.success("Stock adjustment successfully posted!")
        st.rerun()

elif selected_view == "General Accounting Ledger":
    st.header("General Ledger (Real-time Double-Entry Audit)")
    with sqlite3.connect(DB_PATH) as conn:
        ledger_df = pd.read_sql_query("SELECT entry_id, timestamp, voucher_id, account_head, direction, amount FROM general_ledger ORDER BY entry_id DESC LIMIT 50", conn)
    st.dataframe(ledger_df, use_container_width=True)

elif selected_view == "Daily MIS Dashboard":
    st.header("Business Performance & Collections MIS")
    with sqlite3.connect(DB_PATH) as conn:
        orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
    if orders_df.empty:
        st.info("No orders processed today.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Gross Revenue", f"₹{orders_df['grand_total'].sum():.2f}")
        m2.metric("Cash In Hand", f"₹{orders_df[orders_df['payment_mode'].str.contains('Cash')]['grand_total'].sum():.2f}")
        m3.metric("Bank UPI Collections", f"₹{orders_df[orders_df['payment_mode'].str.contains('UPI')]['grand_total'].sum():.2f}")
        st.dataframe(orders_df, use_container_width=True)
