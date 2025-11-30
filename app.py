# enterprise_app_pro_full.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import io
import re
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import plotly.express as px

DB_PATH = "enterprise.db"

# -------------------------
# DATABASE INITIALIZATION (UNCHANGED)
# -------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()
        # Employees
        cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT UNIQUE,
            name TEXT,
            department TEXT,
            role TEXT,
            hire_date TEXT,
            email TEXT,
            phone TEXT
        )""")
        # Attendance
        cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER,
            date TEXT,
            status TEXT,
            note TEXT,
            FOREIGN KEY(emp_id) REFERENCES employees(id) ON DELETE CASCADE
        )""")
        # Customers
        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cust_code TEXT UNIQUE,
            name TEXT,
            email TEXT,
            phone TEXT,
            company TEXT,
            notes TEXT
        )""")
        # Suppliers
        cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            contact TEXT,
            email TEXT,
            address TEXT
        )""")
        # Purchase Orders
        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_no TEXT UNIQUE,
            supplier_id INTEGER,
            created_on TEXT,
            due_date TEXT,
            items TEXT,
            total_amount REAL,
            status TEXT DEFAULT 'Pending',
            notes TEXT,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        )""")
        # Transactions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT,
            tx_type TEXT,
            category TEXT,
            amount REAL,
            reference TEXT,
            notes TEXT
        )""")
        # Tickets
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            subject TEXT,
            description TEXT,
            created_on TEXT,
            status TEXT DEFAULT 'Open',
            assigned_to TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL
        )""")
        # Sales Orders
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE,
            customer_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            status TEXT DEFAULT 'New',
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE SET NULL
        )""")
        conn.commit()

init_db()

# -------------------------
# DATABASE HELPERS (UNCHANGED)
# -------------------------
def query_df(q, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        return pd.read_sql_query(q, conn, params=params)

def insert_commit(q, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cur = conn.cursor()
            cur.execute(q, params)
            conn.commit()
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        st.error(f"Database Integrity Error: {e}")
        return None
    except sqlite3.OperationalError as e:
        st.error(f"Database Operational Error: {e}")
        return None

def to_csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')

def make_pdf(title, sections):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    for h, txt in sections:
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 8, h)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, txt)
        pdf.ln(3)
    bio = io.BytesIO()
    pdf.output(bio)
    bio.seek(0)
    return bio.read()

def display_aggrid(df):
    if df is None or df.empty:
        st.info("No records to display.")
        return
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(enabled=True)
    gb.configure_side_bar()
    gb.configure_default_column(editable=False, groupable=True, filter=True, sortable=True)
    gridOptions = gb.build()
    AgGrid(df, gridOptions=gridOptions, update_mode=GridUpdateMode.NO_UPDATE, fit_columns_on_grid_load=True)

# -------------------------
# VALIDATION HELPERS (FRONTEND ONLY)
# -------------------------
def validate_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return True if re.match(pattern, email.strip()) else False

def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    p = re.sub(r'\s+|\-|\(|\)', '', phone)  # allow separators visually but validate digits
    return p.isdigit() and (10 <= len(p) <= 14)

# -------------------------
# UI THEME & STYLING (FRONTEND ONLY)
# -------------------------
st.set_page_config(page_title="Bareera International", layout="wide", page_icon="🏢", initial_sidebar_state="expanded")

custom_css = """
<style>
/* GLOBAL FONT + NICE BACKGROUND */
html, body, [class*="css"]  {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #0b2948;
}

/* Login Card */
.login-card {
    max-width: 560px;
    margin: 10px auto;
    padding: 22px;
    border-radius: 12px;
    background: linear-gradient(180deg,#ffffff,#f7fbff);
    box-shadow: 0 10px 30px rgba(2,6,23,0.08);
    text-align: left;
}

/* HERO / FEATURE CARDS */
.feature-card {
    padding: 14px;
    border-radius: 10px;
    background: white;
    box-shadow: 0 6px 18px rgba(3,9,23,0.06);
    text-align: left;
}
.feature-title { font-weight:700; margin-bottom:6px; }
.feature-desc { font-size:13px; color:#475569; }

/* METRIC CARD */
.metric-card {
    padding: 14px;
    border-radius: 12px;
    background: linear-gradient(180deg,#ffffff,#f8fafc);
    box-shadow: 0 6px 22px rgba(3,9,23,0.06);
    text-align: center;
}

/* INPUTS & BUTTONS */
div[data-baseweb="input"] > div > input, textarea {
    border-radius: 10px !important;
    border: 1px solid #e6eefc !important;
    padding: 8px !important;
}
.stButton > button {
    border-radius: 10px;
    padding: 8px 18px;
    background: linear-gradient(90deg,#2563eb,#1e40af);
    color: white;
    font-weight: 600;
    border: none;
}
.small-muted { color:#6b7280; font-size:13px; }

/* Footer badge */
.badge {
    display:inline-block;
    padding:6px 10px;
    border-radius:999px;
    font-size:12px;
    color:#06325a;
    background:#dbeafe;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# -------------------------
# SESSION DEFAULTS
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Keep track of last login attempt result to only show error when submitted wrong credentials
if "last_login_failed" not in st.session_state:
    st.session_state.last_login_failed = False

# -------------------------
# LOGIN PAGE (Shows ONLY when not logged in) - nice centered card
# -------------------------
 # ← stops showing dashboard when not logged in
 # -------------------------
# SESSION DEFAULTS
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------------
# LOGIN PAGE (Shows ONLY when not logged in) - nice centered card
# -------------------------
if not st.session_state.logged_in:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    cols = st.columns([1, 2, 1])
    with cols[1]:
       
        st.markdown("<h2 style='margin-top:0;'>🔐 Bareera International</h2>", unsafe_allow_html=True)
        st.markdown("<p class='small-muted'>Sign in to access the Bareera International Dashboard </p>", unsafe_allow_html=True)

        # --- LOGIN FORM ---
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="admin123")
            submitted = st.form_submit_button("Sign in")

        # --- LOGIN VALIDATION ---
        if submitted:
            if username.strip() == "admin" and password.strip() == "admin123":
                st.session_state.logged_in = True
                st.success("✅ Login successful! Redirecting…")
                st.rerun()  # Reloads app to show dashboard
            else:
                st.error("❌ Invalid credentials")

    st.stop()  # Stops showing dashboard when not logged in



# -------------------------
# LOGOUT SECTION (ONLY after login)
# -------------------------
col1, col2 = st.columns([9,1])
with col2:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()   # ← FIX: Logs out in ONE click
# -------------------------
# MAIN DASHBOARD HEADER + MID FEATURE CARDS
# -------------------------
st.title("🏢 Bareera International Dashboard")
st.markdown("**Professional dashboard for HR, Finance, Procurement & CRM**")
st.markdown("")

# Mid hero: show feature cards (pure UI)
fc1, fc2 = st.columns([2,1])
with fc1:
    st.markdown("""
    <div class="feature-card">
      <div class="feature-title">Welcome to Bareera International</div>
      <div class="feature-desc">A clean professional UI for HR, Finance, Procurement, CRM and Analytics. This front-end layer provides validation, exports, imports and quick snapshots while leaving your database/backend logic unchanged.</div>
      <div style="height:10px"></div>
      <div style="display:flex;gap:10px;">
        <div class="metric-card"><div style="font-size:14px">👥 Employees</div><div style="font-size:18px;font-weight:700">Manage staff</div></div>
        <div class="metric-card"><div style="font-size:14px">💰 Finance</div><div style="font-size:18px;font-weight:700">Transactions & reports</div></div>
        <div class="metric-card"><div style="font-size:14px">📦 Procurement</div><div style="font-size:18px;font-weight:700">Suppliers & POs</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with fc2:
    st.markdown("""
    <div class="feature-card">
      <div class="feature-title">Quick Actions</div>
      <div class="feature-desc">Use sidebar to jump between modules. Export CSVs, generate PDF snapshots, or upload CSV data safely.</div>
      <div style="height:8px"></div>
      <ul style="margin:0 0 0 18px;">
        <li class="small-muted">Client-side validation for email & phone</li>
        <li class="small-muted">Ag-Grid powered tables with pagination</li>
        <li class="small-muted">Stylish forms and responsive layout</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# -------------------------
# SIDEBAR NAVIGATION (with emojis)
# -------------------------
st.sidebar.title("Navigation")
module = st.sidebar.radio("Select Module", [
    "🏠 Dashboard",
    "👥 HR",
    "💰 Finance",
    "📦 Procurement",
    "🤝 CRM",
    "📊 Analytics",
    "⬆️⬇️ Data Import/Export",
    "📄 PDF Snapshot"
])

# -------------------------
# DASHBOARD MODULE (with professional color visuals)
# -------------------------
if module == "🏠 Dashboard":
    st.subheader("🏠 Overview")
    emp_count = query_df("SELECT COUNT(*) as cnt FROM employees").iloc[0]['cnt']
    cust_count = query_df("SELECT COUNT(*) as cnt FROM customers").iloc[0]['cnt']
    pending_pos = query_df("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='Pending'").iloc[0]['cnt']
    open_tickets = query_df("SELECT COUNT(*) as cnt FROM tickets WHERE status='Open'").iloc[0]['cnt']

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card"><h4>👥 Employees</h4><h2>{emp_count}</h2></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card"><h4>🏢 Customers</h4><h2>{cust_count}</h2></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card"><h4>📦 Pending POs</h4><h2>{pending_pos}</h2></div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card"><h4>🎫 Open Tickets</h4><h2>{open_tickets}</h2></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Employees by Department - colored professional bars
    dept_df = query_df("SELECT department, COUNT(*) as count FROM employees GROUP BY department")
    if not dept_df.empty:
        # Use a professional palette; ensure deterministic mapping if many categories
        colors = px.colors.qualitative.T10  # professional discrete palette
        fig = px.bar(
            dept_df,
            x="department",
            y="count",
            text="count",
            title="👥 Employees by Department",
            color="department",
            color_discrete_sequence=colors,
            template="plotly_white"
        )
        fig.update_traces(textposition='outside', marker_line_width=1)
        fig.update_layout(
            title=dict(x=0.5, xanchor='center', font=dict(size=18)),
            xaxis_title="Department",
            yaxis_title="Employees",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=60, b=40, l=40, r=20),
            legend_title_text='Department'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No employee department data yet.")

    # Transactions over time - colored by type
    tx_df = query_df("SELECT tx_date, tx_type, amount FROM transactions")
    if not tx_df.empty:
        tx_df['tx_date'] = pd.to_datetime(tx_df['tx_date'])
        colors_tx = {"Income": "#10b981", "Expense": "#ef4444"}  # green/red
        fig2 = px.line(
            tx_df,
            x='tx_date',
            y='amount',
            color='tx_type',
            markers=True,
            title="💰 Transactions Over Time",
            color_discrete_map=colors_tx,
            template="plotly_white"
        )
        fig2.update_traces(mode="lines+markers", hovertemplate='%{x}<br>%{y:$,.2f}<extra>%{legendgroup}</extra>')
        fig2.update_layout(
            title=dict(x=0.5, xanchor='center', font=dict(size=18)),
            xaxis_title="Date",
            yaxis_title="Amount",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=60, b=40, l=40, r=20),
            legend_title_text='Transaction Type'
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No transactions yet.")

# -------------------------
# HR MODULE
# -------------------------
elif module == "👥 HR":
    st.subheader("👥 Human Resources")
    hr_tab = st.tabs(["Employees","Attendance","Reports"])

    # -- Employees tab
    with hr_tab[0]:
        st.markdown("### 🔧 Add Employee")
        st.markdown("Fields marked with * are required.")
        with st.form("add_emp"):
            emp_code = st.text_input("Employee Code *")
            name = st.text_input("Full Name *")
            dept = st.text_input("Department")
            role = st.text_input("Role")
            hire = st.date_input("Hire Date", value=datetime.date.today())
            email = st.text_input("Email *")
            phone = st.text_input("Phone *")
            submitted = st.form_submit_button("Add Employee")

        if submitted:
            # Frontend validation only (backend unchanged)
            if not emp_code.strip() or not name.strip():
                st.error("Employee Code and Full Name are required.")
            elif not validate_email(email):
                st.error("Invalid Email format.")
            elif not validate_phone(phone):
                st.error("Invalid Phone number. Use digits (10–14 chars).")
            else:
                res = insert_commit(
                    "INSERT INTO employees(emp_code,name,department,role,hire_date,email,phone) VALUES (?,?,?,?,?,?,?)",
                    (emp_code.strip(), name.strip(), dept.strip(), role.strip(), hire.isoformat(), email.strip(), phone.strip())
                )
                if res:
                    st.success("Employee added successfully.")
                    st.balloons()

        st.markdown("#### Employees List")
        # Search and quick export
        df_emp = query_df("SELECT * FROM employees ORDER BY id DESC")
        cols = st.columns([3,1])
        with cols[0]:
            q = st.text_input("Search employee by name or code")
        with cols[1]:
            if st.button("Export Employees CSV"):
                st.download_button("Download employees.csv", data=to_csv_bytes(df_emp), file_name="employees.csv", mime="text/csv")
        if q:
            df_emp = df_emp[df_emp.apply(lambda r: q.lower() in str(r['name']).lower() or q.lower() in str(r['emp_code']).lower(), axis=1)]
        display_aggrid(df_emp)

    # -- Attendance tab
    with hr_tab[1]:
        st.markdown("### 📝 Mark Attendance")
        emps = query_df("SELECT id, name FROM employees")
        if not emps.empty:
            sel = st.selectbox("Select Employee", emps.apply(lambda r: f"{r['id']} - {r['name']}", axis=1))
            emp_id = int(sel.split(" - ")[0])
            date = st.date_input("Date", value=datetime.date.today())
            status = st.selectbox("Status", ["Present","Absent","Leave"])
            note = st.text_input("Note")
            if st.button("Save Attendance"):
                insert_commit("INSERT INTO attendance(emp_id,date,status,note) VALUES (?,?,?,?)",
                              (emp_id,date.isoformat(),status,note))
                st.success("Attendance recorded.")
        else:
            st.info("No employees available. Add employees first.")

        st.markdown("#### Attendance Records")
        df_att = query_df("SELECT a.id, e.name, a.date, a.status FROM attendance a JOIN employees e ON a.emp_id=e.id ORDER BY a.date DESC")
        display_aggrid(df_att)

    # -- Reports tab
    with hr_tab[2]:
        st.markdown("### 📋 HR Reports")
        if st.button("Export Employees CSV (Reports)"):
            df = query_df("SELECT * FROM employees")
            st.download_button("Download employees.csv", data=to_csv_bytes(df), file_name="employees.csv", mime="text/csv")
        st.markdown("You can export HR tables as CSV from any listing.")

# -------------------------
# FINANCE MODULE
# -------------------------
elif module == "💰 Finance":
    st.subheader("💰 Finance")
    fin_tab = st.tabs(["Add Transaction","Transactions Summary"])

    with fin_tab[0]:
        st.markdown("### ➕ Add Transaction")
        with st.form("add_tx"):
            tx_date = st.date_input("Date", value=datetime.date.today())
            tx_type = st.selectbox("Type", ["Income","Expense"])
            category = st.text_input("Category")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            add = st.form_submit_button("Add Transaction")
        if add:
            if amount <= 0:
                st.error("Amount must be greater than 0.")
            else:
                insert_commit("INSERT INTO transactions(tx_date,tx_type,category,amount) VALUES (?,?,?,?)",
                              (tx_date.isoformat(),tx_type,category,float(amount)))
                st.success("Transaction added.")
                st.balloons()

    with fin_tab[1]:
        st.markdown("### 📈 Transactions")
        df_tx = query_df("SELECT * FROM transactions ORDER BY tx_date DESC")
        display_aggrid(df_tx)
        if not df_tx.empty:
            summary = df_tx.groupby("tx_type")["amount"].sum().reset_index()
            colors = px.colors.qualitative.Plotly
            fig4 = px.bar(summary, x="tx_type", y="amount", text="amount", title="Transaction Summary by Type",
                          color="tx_type", color_discrete_sequence=["#10b981", "#ef4444"])
            fig4.update_traces(textposition='outside', marker_line_width=1)
            fig4.update_layout(template="plotly_white", title=dict(x=0.5))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No transactions to show.")

# -------------------------
# PROCUREMENT MODULE
# -------------------------
elif module == "📦 Procurement":
    st.subheader("📦 Procurement")
    proc_tab = st.tabs(["Suppliers","Purchase Orders"])

    with proc_tab[0]:
        st.markdown("### ➕ Add Supplier")
        with st.form("add_sup"):
            s_name = st.text_input("Name *")
            contact = st.text_input("Contact")
            s_email = st.text_input("Email")
            addr = st.text_area("Address")
            add = st.form_submit_button("Add Supplier")
        if add:
            if not s_name.strip():
                st.error("Supplier name is required.")
            elif s_email and not validate_email(s_email):
                st.error("Invalid supplier email.")
            else:
                insert_commit("INSERT INTO suppliers(name,contact,email,address) VALUES (?,?,?,?)",
                              (s_name.strip(),contact.strip(),s_email.strip(),addr.strip()))
                st.success("Supplier added.")
                st.balloons()

        st.markdown("#### Suppliers")
        df_sup = query_df("SELECT * FROM suppliers ORDER BY id DESC")
        display_aggrid(df_sup)

    with proc_tab[1]:
        st.markdown("### 🧾 Create Purchase Order")
        with st.form("add_po"):
            po_no = st.text_input("PO Number *")
            supplier_id = st.number_input("Supplier ID *", min_value=1, step=1)
            created_on = st.date_input("Created On", value=datetime.date.today())
            due_date = st.date_input("Due Date", value=datetime.date.today() + datetime.timedelta(days=7))
            total = st.number_input("Total Amount", min_value=0.0, format="%.2f")
            add = st.form_submit_button("Create PO")
        if add:
            if not po_no.strip():
                st.error("PO Number is required.")
            elif total <= 0:
                st.error("Total must be greater than 0.")
            else:
                insert_commit("INSERT INTO purchase_orders(po_no,supplier_id,created_on,due_date,total_amount) VALUES (?,?,?,?,?)",
                              (po_no.strip(),int(supplier_id),created_on.isoformat(),due_date.isoformat(),float(total)))
                st.success("PO created.")
                st.balloons()

        st.markdown("#### Purchase Orders")
        df_po = query_df("SELECT * FROM purchase_orders ORDER BY id DESC")
        display_aggrid(df_po)

# -------------------------
# CRM MODULE
# -------------------------
elif module == "🤝 CRM":
    st.subheader("🤝 CRM")
    crm_tab = st.tabs(["Customers","Tickets","Sales Orders"])

    with crm_tab[0]:
        st.markdown("### ➕ Add Customer")
        with st.form("add_cust"):
            cust_code = st.text_input("Customer Code *")
            name = st.text_input("Name *")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            add = st.form_submit_button("Add Customer")
        if add:
            if not cust_code.strip() or not name.strip():
                st.error("Customer Code and Name are required.")
            elif email and not validate_email(email):
                st.error("Invalid email format.")
            elif phone and not validate_phone(phone):
                st.error("Invalid phone number.")
            else:
                insert_commit("INSERT INTO customers(cust_code,name,email,phone) VALUES (?,?,?,?)",
                              (cust_code.strip(),name.strip(),email.strip(),phone.strip()))
                st.success("Customer added.")
                st.balloons()

        st.markdown("#### Customers")
        df_cust = query_df("SELECT * FROM customers ORDER BY id DESC")
        display_aggrid(df_cust)

    with crm_tab[1]:
        st.markdown("### 📨 Create Ticket")
        with st.form("add_ticket"):
            cust_id = st.number_input("Customer ID", min_value=1, step=1)
            subject = st.text_input("Subject *")
            desc = st.text_area("Description")
            add = st.form_submit_button("Add Ticket")
        if add:
            if not subject.strip():
                st.error("Subject is required.")
            else:
                insert_commit("INSERT INTO tickets(customer_id,subject,description,created_on) VALUES (?,?,?,?)",
                              (int(cust_id),subject.strip(),desc.strip(),datetime.date.today().isoformat()))
                st.success("Ticket added.")
                st.balloons()

        st.markdown("#### Tickets")
        df_tickets = query_df("SELECT * FROM tickets ORDER BY id DESC")
        display_aggrid(df_tickets)

    with crm_tab[2]:
        st.markdown("### 🧾 Sales Orders")
        if st.button("Create Demo Sales Order (example)"):
            insert_commit("INSERT INTO sales_orders(order_no,customer_id,order_date,total_amount,status) VALUES (?,?,?,?,?)",
                          (f"SO-{int(datetime.datetime.now().timestamp())}", 1, datetime.date.today().isoformat(), 0.0, "New"))
            st.success("Demo sales order created.")
            st.balloons()
        df_sales = query_df("SELECT * FROM sales_orders ORDER BY id DESC")
        display_aggrid(df_sales)

# -------------------------
# ANALYTICS MODULE
# -------------------------
elif module == "📊 Analytics":
    st.subheader("📊 Analytics")
    st.markdown("Quick charts and CSV exports.")
    table = st.selectbox("Choose table to view/export", ["employees","customers","transactions","purchase_orders","tickets"])
    df_view = query_df(f"SELECT * FROM {table} ORDER BY id DESC")
    display_aggrid(df_view)
    if not df_view.empty:
        st.download_button("Export CSV", data=to_csv_bytes(df_view), file_name=f"{table}.csv", mime="text/csv")

# -------------------------
# DATA IMPORT / EXPORT
# -------------------------
elif module == "⬆️⬇️ Data Import/Export":
    st.subheader("⬆️⬇️ Data Import & Export")
    st.markdown("Export any table as CSV, or upload a CSV to append rows (frontend validation will show errors).")
    export_table = st.selectbox("Export table", ["employees","customers","suppliers","transactions","purchase_orders","tickets"])
    if st.button("Export Selected Table CSV"):
        df = query_df(f"SELECT * FROM {export_table}")
        st.download_button("Download CSV", data=to_csv_bytes(df), file_name=f"{export_table}.csv", mime="text/csv")

    st.markdown("---")
    st.markdown("### Import CSV (Append)")
    upload_table = st.selectbox("Append to table", ["employees","customers","suppliers","transactions"], index=0)
    uploaded_file = st.file_uploader("Choose CSV file to upload", type=["csv"])
    if uploaded_file is not None:
        try:
            df_up = pd.read_csv(uploaded_file)
            st.write("Preview:")
            st.dataframe(df_up.head())
            if st.button("Append CSV to DB"):
                inserted = 0
                for _, row in df_up.iterrows():
                    try:
                        if upload_table == "employees":
                            insert_commit("INSERT INTO employees(emp_code,name,department,role,hire_date,email,phone) VALUES (?,?,?,?,?,?,?)",
                                          (str(row.get('emp_code','')).strip(), str(row.get('name','')).strip(),
                                           str(row.get('department','')).strip(), str(row.get('role','')).strip(),
                                           str(row.get('hire_date', datetime.date.today().isoformat())),
                                           str(row.get('email','')).strip(), str(row.get('phone','')).strip()))
                        elif upload_table == "customers":
                            insert_commit("INSERT INTO customers(cust_code,name,email,phone) VALUES (?,?,?,?)",
                                          (str(row.get('cust_code','')).strip(), str(row.get('name','')).strip(),
                                           str(row.get('email','')).strip(), str(row.get('phone','')).strip()))
                        elif upload_table == "suppliers":
                            insert_commit("INSERT INTO suppliers(name,contact,email,address) VALUES (?,?,?,?)",
                                          (str(row.get('name','')).strip(), str(row.get('contact','')).strip(),
                                           str(row.get('email','')).strip(), str(row.get('address','')).strip()))
                        elif upload_table == "transactions":
                            insert_commit("INSERT INTO transactions(tx_date,tx_type,category,amount) VALUES (?,?,?,?)",
                                          (str(row.get('tx_date', datetime.date.today().isoformat())),
                                           str(row.get('tx_type','')).strip(), str(row.get('category','')).strip(),
                                           float(row.get('amount',0.0))))
                        inserted += 1
                    except Exception:
                        continue
                st.success(f"Append finished. Rows processed: {len(df_up)}. (Inserted ~{inserted})")
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")

# -------------------------
# PDF SNAPSHOT MODULE
# -------------------------
elif module == "📄 PDF Snapshot":
    st.subheader("📄 Generate PDF Summary")
    title = st.text_input("Report Title", "Bareera International Project Snapshot")
    if st.button("Generate PDF"):
        sections = [
            ("Employees", str(query_df("SELECT COUNT(*) as cnt FROM employees").iloc[0]['cnt'])),
            ("Customers", str(query_df("SELECT COUNT(*) as cnt FROM customers").iloc[0]['cnt'])),
            ("Pending POs", str(query_df("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='Pending'").iloc[0]['cnt'])),
            ("Open Tickets", str(query_df("SELECT COUNT(*) as cnt FROM tickets WHERE status='Open'").iloc[0]['cnt']))
        ]
        pdf_bytes = make_pdf(title, sections)
        st.download_button("Download PDF", data=pdf_bytes, file_name="Bareera International.pdf", mime="application/pdf")

# -------------------------
# Footer / small tips
# -------------------------
st.markdown("---")
st.markdown("<span class='badge'>Pro UI</span>  Frontend-only upgrades — database schema and backend queries remained unchanged.", unsafe_allow_html=True)
