# enterprise_app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import io
from fpdf import FPDF
import os

DB_PATH = "enterprise.db"

# -------------------------
# Database init / helpers
# -------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # HR: employees, attendance, leaves
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER,
        date TEXT,
        status TEXT, -- Present/Absent/Leave
        note TEXT,
        FOREIGN KEY(emp_id) REFERENCES employees(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER,
        leave_type TEXT,
        start_date TEXT,
        end_date TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Pending',
        applied_on TEXT,
        FOREIGN KEY(emp_id) REFERENCES employees(id)
    )""")
    # Finance: transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_date TEXT,
        tx_type TEXT, -- Income/Expense
        category TEXT,
        amount REAL,
        reference TEXT,
        notes TEXT
    )""")
    # Procurement / Pending: suppliers, purchase_orders
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        contact TEXT,
        email TEXT,
        address TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_no TEXT UNIQUE,
        supplier_id INTEGER,
        created_on TEXT,
        due_date TEXT,
        items TEXT, -- small json/string list
        total_amount REAL,
        status TEXT DEFAULT 'Pending', -- Pending/Approved/Received
        notes TEXT,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
    )""")
    # CRM: customers, tickets, sales_orders
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        subject TEXT,
        description TEXT,
        created_on TEXT,
        status TEXT DEFAULT 'Open', -- Open/Closed
        assigned_to TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE,
        customer_id INTEGER,
        order_date TEXT,
        total_amount REAL,
        status TEXT DEFAULT 'New',
        notes TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    conn.commit()
    return conn

# Init DB on start
conn = init_db()

# -------------------------
# Utility helpers
# -------------------------
def to_csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')

def query_df(q, params=()):
    return pd.read_sql_query(q, conn, params=params)

def insert_and_commit(query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur.lastrowid

def format_date(d):
    if isinstance(d, str):
        return d
    return d.isoformat()

# -------------------------
# PDF summary helper
# -------------------------
def make_pdf_summary(title, sections):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(6)
    pdf.set_font("Arial", "", 11)
    for h, txt in sections:
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 8, h)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 6, txt)
        pdf.ln(3)
    bio = io.BytesIO()
    pdf.output(bio)
    bio.seek(0)
    return bio.read()

# -------------------------
# App UI
# -------------------------
st.set_page_config(page_title="Enterprise WebApp - HR | Finance | Procurement | CRM", layout="wide")
st.title("Enterprise Management - HR | Finance | Procurement | CRM")
st.markdown("This demo app implements 4 modules for a corporate assignment. Data stored locally in `enterprise.db`.")

# Top-level nav
module = st.sidebar.selectbox("Choose module", ["Overview","HR","Finance","Procurement / Pending","CRM","Data Import/Export","PDF Snapshot"])

# ---------- OVERVIEW ----------
if module == "Overview":
    st.header("Company Dashboard Overview")
    # quick stats
    emp_count = query_df("SELECT COUNT(*) as cnt FROM employees").iloc[0]['cnt']
    cust_count = query_df("SELECT COUNT(*) as cnt FROM customers").iloc[0]['cnt']
    pending_pos = query_df("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='Pending'").iloc[0]['cnt']
    open_tickets = query_df("SELECT COUNT(*) as cnt FROM tickets WHERE status='Open'").iloc[0]['cnt']
    st.metric("Employees", emp_count)
    st.metric("Customers", cust_count)
    st.metric("Pending Purchase Orders", pending_pos)
    st.metric("Open Support Tickets", open_tickets)

    st.subheader("Finance snapshot (last 90 days)")
    try:
        tx = query_df("SELECT tx_date, tx_type, amount FROM transactions WHERE date(tx_date) >= date('now','-90 days')")
        if not tx.empty:
            tx['tx_date'] = pd.to_datetime(tx['tx_date'])
            s = tx.groupby('tx_type')['amount'].sum().reset_index()
            st.dataframe(s)
            st.line_chart(tx.set_index('tx_date').groupby(pd.Grouper(freq='D'))['amount'].sum().fillna(0))
        else:
            st.info("No transactions in last 90 days.")
    except Exception as e:
        st.error(str(e))

# ---------- HR ----------
elif module == "HR":
    st.header("Human Resources")
    hr_tab = st.tabs(["Employees","Attendance","Leaves","Reports"])
    # Employees tab
    with hr_tab[0]:
        st.subheader("Add new employee")
        with st.form("add_emp"):
            emp_code = st.text_input("Employee Code (unique)")
            name = st.text_input("Full name")
            dept = st.text_input("Department")
            role = st.text_input("Role / Position")
            hire = st.date_input("Hire date", value=datetime.date.today())
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            submitted = st.form_submit_button("Add Employee")
        if submitted:
            try:
                insert_and_commit("INSERT INTO employees(emp_code,name,department,role,hire_date,email,phone) VALUES (?,?,?,?,?,?,?)",
                                  (emp_code,name,dept,role,format_date(hire),email,phone))
                st.success("Employee added.")
            except Exception as e:
                st.error("Error: " + str(e))
        st.markdown("Existing employees")
        emps = query_df("SELECT * FROM employees")
        st.dataframe(emps)

        # export employees
        if st.button("Download employees CSV"):
            st.download_button("Download CSV", data=to_csv_bytes(emps), file_name="employees.csv", mime="text/csv")

    # Attendance
    with hr_tab[1]:
        st.subheader("Mark Attendance")
        emps = query_df("SELECT id, name, emp_code FROM employees")
        if emps.empty:
            st.info("No employees - add employees first.")
        else:
            e_sel = st.selectbox("Select employee", emps.apply(lambda r: f"{r['emp_code']} - {r['name']}", axis=1).tolist())
            emp_id = int(e_sel.split(" - ")[0]) if "-" in e_sel else emps.iloc[0]['id']
            date = st.date_input("Date", value=datetime.date.today())
            status = st.selectbox("Status", ["Present","Absent","Leave"])
            note = st.text_input("Note (optional)")
            if st.button("Save attendance"):
                # resolve emp_id properly
                # if e_sel formatted as "code - name", find id
                try:
                    code = e_sel.split(" - ")[0]
                    emp_row = query_df("SELECT id FROM employees WHERE emp_code = ?", (code,))
                    if not emp_row.empty:
                        emp_id = int(emp_row.iloc[0]['id'])
                    insert_and_commit("INSERT INTO attendance(emp_id,date,status,note) VALUES (?,?,?,?)",
                                      (emp_id, format_date(date), status, note))
                    st.success("Attendance saved.")
                except Exception as e:
                    st.error(str(e))
            st.markdown("View attendance by month")
            mon = st.selectbox("Choose month", [datetime.date.today().replace(day=1) - datetime.timedelta(days=30*i) for i in range(0,6)], format_func=lambda d: d.strftime("%B %Y"))
            mon_start = mon.replace(day=1)
            mon_end = (mon_start + pd.offsets.MonthEnd()).date()
            q = "SELECT a.id, e.emp_code, e.name, a.date, a.status, a.note FROM attendance a JOIN employees e ON a.emp_id=e.id WHERE date(a.date) BETWEEN ? AND ?"
            df_att = pd.read_sql_query(q, conn, params=(mon_start.isoformat(), mon_end.isoformat()))
            st.dataframe(df_att)

    # Leaves
    with hr_tab[2]:
        st.subheader("Apply / Approve Leaves")
        emps = query_df("SELECT id, emp_code, name FROM employees")
        if emps.empty:
            st.info("No employees.")
        else:
            with st.form("apply_leave"):
                e_choice = st.selectbox("Employee", emps.apply(lambda r: f"{r['emp_code']} - {r['name']}", axis=1).tolist())
                start = st.date_input("Start date")
                end = st.date_input("End date", value=start)
                ltype = st.selectbox("Leave type", ["Annual","Sick","Maternity","Unpaid","Other"])
                reason = st.text_area("Reason", height=80)
                apply_btn = st.form_submit_button("Apply")
            if apply_btn:
                code = e_choice.split(" - ")[0]
                emp_row = query_df("SELECT id FROM employees WHERE emp_code=?", (code,))
                if not emp_row.empty:
                    emp_id = int(emp_row.iloc[0]['id'])
                    insert_and_commit("INSERT INTO leaves(emp_id,leave_type,start_date,end_date,reason,applied_on) VALUES (?,?,?,?,?,?)",
                                      (emp_id, ltype, start.isoformat(), end.isoformat(), reason, datetime.date.today().isoformat()))
                    st.success("Leave applied (Pending approval).")
        st.markdown("Pending leave requests")
        leaves = query_df("SELECT l.id, e.emp_code, e.name, l.leave_type, l.start_date, l.end_date, l.reason, l.status FROM leaves l JOIN employees e ON l.emp_id = e.id WHERE l.status='Pending'")
        st.dataframe(leaves)
        if not leaves.empty:
            lid = st.number_input("Enter Leave ID to Approve/Reject", min_value=1, step=1)
            action = st.selectbox("Action", ["Approve","Reject"])
            if st.button("Apply action"):
                new_status = "Approved" if action=="Approve" else "Rejected"
                insert_and_commit("UPDATE leaves SET status=? WHERE id=?", (new_status, lid))
                st.success("Action applied.")

    # Reports
    with hr_tab[3]:
        st.subheader("HR Reports")
        emps = query_df("SELECT * FROM employees")
        st.write("Headcount by Department")
        if not emps.empty:
            st.dataframe(emps.groupby("department")["id"].count().rename("count").reset_index())
        st.write("Absences last 30 days")
        abs_df = query_df("SELECT a.date, e.emp_code, e.name, a.status FROM attendance a JOIN employees e ON a.emp_id=e.id WHERE a.status='Absent' AND date(a.date) >= date('now','-30 days')")
        st.dataframe(abs_df)

# ---------- FINANCE ----------
elif module == "Finance":
    st.header("Finance")
    f_tab = st.tabs(["Add Transaction","Transactions","Summary & Charts"])
    with f_tab[0]:
        st.subheader("Record Income / Expense")
        with st.form("add_tx"):
            tx_date = st.date_input("Date", value=datetime.date.today())
            tx_type = st.selectbox("Type", ["Income","Expense"])
            category = st.text_input("Category (e.g., Sales, Salary, Utilities)")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            ref = st.text_input("Reference (optional)")
            notes = st.text_area("Notes (optional)")
            add = st.form_submit_button("Save Transaction")
        if add:
            insert_and_commit("INSERT INTO transactions(tx_date,tx_type,category,amount,reference,notes) VALUES (?,?,?,?,?,?)",
                              (format_date(tx_date), tx_type, category, amount, ref, notes))
            st.success("Transaction recorded.")
    with f_tab[1]:
        st.subheader("Transactions")
        df_tx = query_df("SELECT * FROM transactions ORDER BY date(tx_date) DESC")
        st.dataframe(df_tx)
        if not df_tx.empty:
            st.download_button("Download transactions CSV", data=to_csv_bytes(df_tx), file_name="transactions.csv", mime="text/csv")
    with f_tab[2]:
        st.subheader("Summary")
        df_tx = query_df("SELECT tx_date, tx_type, amount FROM transactions")
        if df_tx.empty:
            st.info("No transactions yet.")
        else:
            df_tx['tx_date'] = pd.to_datetime(df_tx['tx_date'])
            s = df_tx.groupby('tx_type')['amount'].sum().reset_index()
            st.dataframe(s)
            income = float(s[s['tx_type']=='Income']['amount'].sum()) if 'Income' in s['tx_type'].values else 0.0
            expense = float(s[s['tx_type']=='Expense']['amount'].sum()) if 'Expense' in s['tx_type'].values else 0.0
            st.metric("Total Income", f"{income:.2f}")
            st.metric("Total Expense", f"{expense:.2f}")
            st.metric("Net Balance", f"{(income-expense):.2f}")
            st.write("Monthly cashflow (sum)")
            monthly = df_tx.set_index('tx_date').groupby(pd.Grouper(freq='M'))['amount'].sum().reset_index()
            monthly['tx_date'] = monthly['tx_date'].dt.to_period('M').astype(str)
            st.bar_chart(monthly.set_index('tx_date')['amount'])

# ---------- PROCUREMENT / PENDING ----------
elif module == "Procurement / Pending":
    st.header("Procurement & Pending Approvals")
    p_tab = st.tabs(["Suppliers","Purchase Orders","Pending Approvals"])
    with p_tab[0]:
        st.subheader("Add Supplier")
        with st.form("add_supplier"):
            sname = st.text_input("Supplier name")
            contact = st.text_input("Contact person")
            email = st.text_input("Email")
            addr = st.text_area("Address")
            add_sup = st.form_submit_button("Save Supplier")
        if add_sup:
            insert_and_commit("INSERT INTO suppliers(name,contact,email,address) VALUES (?,?,?,?)", (sname,contact,email,addr))
            st.success("Supplier added.")
        st.write("Suppliers list")
        st.dataframe(query_df("SELECT * FROM suppliers"))

    with p_tab[1]:
        st.subheader("Create Purchase Order (PO)")
        suppliers = query_df("SELECT id, name FROM suppliers")
        with st.form("create_po"):
            po_no = st.text_input("PO Number (unique)")
            sup_choice = st.selectbox("Supplier", suppliers.apply(lambda r: f"{r['id']} - {r['name']}", axis=1).tolist() if not suppliers.empty else ["-"])
            created_on = st.date_input("Created on", value=datetime.date.today())
            due = st.date_input("Due date", value=datetime.date.today()+datetime.timedelta(days=7))
            items = st.text_area("Items (one per line: qty x item - unit_price)", height=120)
            total = st.number_input("Total amount", min_value=0.0, format="%.2f")
            notes = st.text_area("Notes (optional)")
            create = st.form_submit_button("Create PO")
        if create:
            try:
                sup_id = int(sup_choice.split(" - ")[0]) if suppliers.shape[0]>0 else None
                insert_and_commit("INSERT INTO purchase_orders(po_no,supplier_id,created_on,due_date,items,total_amount,notes) VALUES (?,?,?,?,?,?,?)",
                                  (po_no, sup_id, format_date(created_on), format_date(due), items, total, notes))
                st.success("Purchase Order created (Pending).")
            except Exception as e:
                st.error(str(e))
        st.write("POs")
        st.dataframe(query_df("SELECT p.id, p.po_no, s.name as supplier, p.created_on, p.due_date, p.total_amount, p.status FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id"))

    with p_tab[2]:
        st.subheader("Pending Approvals")
        pending = query_df("SELECT id,po_no,total_amount,status FROM purchase_orders WHERE status='Pending'")
        st.dataframe(pending)
        if not pending.empty:
            sel = st.number_input("Enter PO ID to change status", min_value=1, step=1)
            newstatus = st.selectbox("New status", ["Approved","Received","Cancelled"])
            if st.button("Apply status"):
                insert_and_commit("UPDATE purchase_orders SET status=? WHERE id=?", (newstatus, sel))
                st.success("Status updated.")

# ---------- CRM ----------
elif module == "CRM":
    st.header("Customer Relationship Management")
    crm_tab = st.tabs(["Customers","Tickets","Sales Orders","CRM Overview"])
    with crm_tab[0]:
        st.subheader("Add Customer / Lead")
        with st.form("add_cust"):
            cust_code = st.text_input("Customer Code (unique)")
            cname = st.text_input("Name")
            cemail = st.text_input("Email")
            phone = st.text_input("Phone")
            company = st.text_input("Company")
            notes = st.text_area("Notes")
            addc = st.form_submit_button("Save Customer")
        if addc:
            try:
                insert_and_commit("INSERT INTO customers(cust_code,name,email,phone,company,notes) VALUES (?,?,?,?,?,?)",
                                  (cust_code,cname,cemail,phone,company,notes))
                st.success("Customer saved.")
            except Exception as e:
                st.error(str(e))
        st.write("Customers")
        st.dataframe(query_df("SELECT * FROM customers"))

    with crm_tab[1]:
        st.subheader("Support Tickets")
        customers = query_df("SELECT id, name, cust_code FROM customers")
        with st.form("add_ticket"):
            cust_choice = st.selectbox("Customer", customers.apply(lambda r: f"{r['cust_code']} - {r['name']}", axis=1).tolist() if not customers.empty else ["-"])
            subj = st.text_input("Subject")
            desc = st.text_area("Description")
            assigned = st.text_input("Assign to (staff name)")
            addt = st.form_submit_button("Create Ticket")
        if addt:
            try:
                cust_id = int(cust_choice.split(" - ")[0])
                insert_and_commit("INSERT INTO tickets(customer_id,subject,description,created_on,assigned_to) VALUES (?,?,?,?,?)",
                                  (cust_id, subj, desc, datetime.date.today().isoformat(), assigned))
                st.success("Ticket created.")
            except Exception as e:
                st.error(str(e))
        st.write("Open tickets")
        st.dataframe(query_df("SELECT t.id, c.name as customer, t.subject, t.created_on, t.status, t.assigned_to FROM tickets t LEFT JOIN customers c ON t.customer_id=c.id WHERE t.status='Open'"))

    with crm_tab[2]:
        st.subheader("Sales Orders")
        customers = query_df("SELECT id,cust_code,name FROM customers")
        with st.form("add_order"):
            order_no = st.text_input("Order No (unique)")
            cust_choice = st.selectbox("Customer", customers.apply(lambda r: f"{r['cust_code']} - {r['name']}", axis=1).tolist() if not customers.empty else ["-"])
            order_date = st.date_input("Order date", value=datetime.date.today())
            total_amt = st.number_input("Total amount", min_value=0.0, format="%.2f")
            notes = st.text_area("Notes")
            addo = st.form_submit_button("Create Order")
        if addo:
            try:
                cust_id = int(cust_choice.split(" - ")[0])
                insert_and_commit("INSERT INTO sales_orders(order_no,customer_id,order_date,total_amount,notes) VALUES (?,?,?,?,?)",
                                  (order_no,cust_id,format_date(order_date),total_amt,notes))
                st.success("Sales order created.")
            except Exception as e:
                st.error(str(e))
        st.write("Sales Orders")
        st.dataframe(query_df("SELECT so.id, so.order_no, c.name as customer, so.order_date, so.total_amount, so.status FROM sales_orders so LEFT JOIN customers c ON so.customer_id=c.id"))

    with crm_tab[3]:
        st.subheader("CRM Overview")
        open_tickets = query_df("SELECT COUNT(*) as cnt FROM tickets WHERE status='Open'").iloc[0]['cnt']
        leads = query_df("SELECT COUNT(*) as cnt FROM customers").iloc[0]['cnt']
        orders = query_df("SELECT COUNT(*) as cnt FROM sales_orders").iloc[0]['cnt']
        st.metric("Open Tickets", open_tickets)
        st.metric("Customers / Leads", leads)
        st.metric("Sales Orders", orders)

# ---------- Data Import / Export ----------
elif module == "Data Import/Export":
    st.header("Import / Export CSV data")
    st.write("You can upload CSV files to bulk-import employees, customers or transactions (simple expects specific columns).")
    choice = st.selectbox("Type to import", ["Employees","Customers","Transactions"])
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df.head(10))
        if st.button("Import now"):
            try:
                if choice=="Employees":
                    for _, r in df.iterrows():
                        insert_and_commit("INSERT OR IGNORE INTO employees(emp_code,name,department,role,hire_date,email,phone) VALUES (?,?,?,?,?,?,?)",
                                          (r.get('emp_code'), r.get('name'), r.get('department'), r.get('role'), r.get('hire_date'), r.get('email'), r.get('phone')))
                elif choice=="Customers":
                    for _, r in df.iterrows():
                        insert_and_commit("INSERT OR IGNORE INTO customers(cust_code,name,email,phone,company,notes) VALUES (?,?,?,?,?,?)",
                                          (r.get('cust_code'), r.get('name'), r.get('email'), r.get('phone'), r.get('company'), r.get('notes')))
                else:
                    for _, r in df.iterrows():
                        insert_and_commit("INSERT INTO transactions(tx_date,tx_type,category,amount,reference,notes) VALUES (?,?,?,?,?,?)",
                                          (r.get('tx_date'), r.get('tx_type'), r.get('category'), float(r.get('amount') or 0.0), r.get('reference'), r.get('notes')))
                st.success("Imported.")
            except Exception as e:
                st.error("Import error: " + str(e))
    st.markdown("---")
    st.write("Export entire DB tables to CSV")
    table = st.selectbox("Choose table to export", ["employees","attendance","leaves","transactions","suppliers","purchase_orders","customers","tickets","sales_orders"])
    if st.button("Export table to CSV"):
        df = query_df(f"SELECT * FROM {table}")
        st.download_button("Download CSV", data=to_csv_bytes(df), file_name=f"{table}.csv", mime="text/csv")

# ---------- PDF Snapshot ----------
elif module == "PDF Snapshot":
    st.header("Generate PDF Snapshot / Summary")
    st.write("Create a short PDF report that summarizes current project state.")
    title = st.text_input("Report title", value="Enterprise Project Snapshot")
    if st.button("Generate PDF"):
        sections = []
        # small summaries
        sections.append(("Employees", str(query_df("SELECT COUNT(*) as cnt FROM employees").iloc[0]['cnt'])))
        sections.append(("Customers", str(query_df("SELECT COUNT(*) as cnt FROM customers").iloc[0]['cnt'])))
        sections.append(("Pending POs", str(query_df("SELECT COUNT(*) as cnt FROM purchase_orders WHERE status='Pending'").iloc[0]['cnt'])))
        sections.append(("Open Tickets", str(query_df("SELECT COUNT(*) as cnt FROM tickets WHERE status='Open'").iloc[0]['cnt'])))
        pdf_bytes = make_pdf_summary(title, sections)
        st.download_button("Download PDF", data=pdf_bytes, file_name="enterprise_snapshot.pdf", mime="application/pdf")

st.markdown("---")
st.caption("This app is a demo skeleton for your Unit-16 assignment — I'll customise fields, add authentication, or change UI as per teacher's audio if you want. Data saved in enterprise.db.")
