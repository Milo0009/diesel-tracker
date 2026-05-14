import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import time

def get_db():
    return sqlite3.connect('diesel_monitor.db')

def get_logs():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM fuel_logs", conn)
    conn.close()
    return df

def get_next_series():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM fuel_logs ORDER BY id DESC LIMIT 1")
    last_id = c.fetchone()
    conn.close()
    return str(last_id[0] + 1).zfill(4) if last_id else "0001"

def update_inventory(liters_deducted):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE inventory SET current_stock = current_stock - ? WHERE id = 1", (liters_deducted,))
    conn.commit()
    conn.close()

def inject_custom_css():
    st.markdown("""
        <style>
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .login-box { animation: fadeIn 0.8s ease-out; padding: 40px; border-radius: 20px; background-color: #ffffff; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 1px solid #e1e4e8; }
        .main-title { font-family: 'Inter', sans-serif; color: #1f2937; text-align: center; font-weight: 800; margin-bottom: 5px; }
        .sub-title { text-align: center; color: #6b7280; font-size: 15px; margin-bottom: 30px; }
        [data-testid="stMetricValue"] { font-size: 28px; color: #1f2937; }
        </style>
    """, unsafe_allow_html=True)

def login_page():
    inject_custom_css()
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🚛</h1>", unsafe_allow_html=True)
        st.markdown('<h1 class="main-title">Continuum Packaging Corporation</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">Diesel & Tank Management System</p>', unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("👤 Username")
            pwd = st.text_input("🔑 Password", type="password")
            submit = st.form_submit_button("SIGN IN", use_container_width=True)
            if submit:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (user, pwd))
                result = c.fetchone()
                conn.close()
                if result:
                    st.session_state['logged_in'] = True
                    st.session_state['current_user'] = user
                    st.toast("Welcome back!", icon="🫡")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Access Denied: Invalid Credentials")
        st.markdown('</div>', unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_page()
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Menu:", 
                           ["📊 Dashboard & Analytics", "⛽ Log Diesel Refuel", "🛣️ Daily Trip Log", "⚙️ Database Management", "🔐 Change Password"],
                           key="sidebar_nav")
    st.sidebar.divider()
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state['logged_in'] = False
        st.rerun()

    conn = get_db()
    inventory_data = pd.read_sql_query("SELECT current_stock FROM inventory WHERE id = 1", conn)
    stock = inventory_data.iloc[0]['current_stock'] if not inventory_data.empty else 0
    conn.close()

    if page == "📊 Dashboard & Analytics":
        st.title("📊 Trucks Performance Analytics")
        col_inv1, col_inv2 = st.columns([2, 1])
        with col_inv1:
            if stock < 500: st.error(f"🚨 **INVENTORY LOW:** {stock:,.2f} L")
            else: st.info(f"📊 **Main Tank Stock:** {stock:,.2f} Liters")
        with col_inv2:
            with st.expander("Update Tank"):
                mode = st.radio("Action:", ["Add Stock", "Set Absolute"], horizontal=True, key="tank_mode")
                new_amount = st.number_input("Liters", min_value=0.0)
                if st.button("Update Tank"):
                    conn = get_db()
                    if mode == "Add Stock": conn.execute("UPDATE inventory SET current_stock = current_stock + ? WHERE id = 1", (new_amount,))
                    else: conn.execute("UPDATE inventory SET current_stock = ? WHERE id = 1", (new_amount,))
                    conn.commit(); conn.close()
                    st.rerun()

        st.divider()
        tab_fuel, tab_trips = st.tabs(["⛽ Diesel Performance", "🛣️ Trip Analytics"])
        df = get_logs()

        with tab_fuel:
            fuel_only = df[df['liters_loaded'] > 0].copy()
            if not fuel_only.empty:
                st.subheader("🚛 Total Diesel Consumption per Truck (Liters)")
                truck_total = fuel_only.groupby('plate_number')['liters_loaded'].sum().reset_index()
                st.bar_chart(data=truck_total, x='plate_number', y='liters_loaded')
                
                top_truck = truck_total.loc[truck_total['liters_loaded'].idxmax()]
                st.metric("Highest Consumer", f"{top_truck['plate_number']}", f"{top_truck['liters_loaded']:,.2f} L")
                st.dataframe(truck_total.sort_values(by='liters_loaded', ascending=False), use_container_width=True)
            else:
                st.info("No records.")

        with tab_trips:
            eff_df = df[(df['liters_loaded'] > 0) & (df['distance_travelled'] > 0)].copy()
            
            if not eff_df.empty:
                st.subheader("⛽ Efficiency Ranking (km/L)")
                truck_eff = eff_df.groupby('plate_number').agg({'distance_travelled': 'sum', 'liters_loaded': 'sum'}).reset_index()
                truck_eff['km_per_liter'] = truck_eff['distance_travelled'] / truck_eff['liters_loaded']
                
                st.bar_chart(data=truck_eff, x='plate_number', y='km_per_liter')
                
                m1, m2 = st.columns(2)
                most_eff = truck_eff.loc[truck_eff['km_per_liter'].idxmax()]
                least_eff = truck_eff.loc[truck_eff['km_per_liter'].idxmin()]
                
                m1.metric("Most Efficient", f"{most_eff['plate_number']}", f"{most_eff['km_per_liter']:.2f} km/L")
                m2.metric("Least Efficient", f"{least_eff['plate_number']}", f"{least_eff['km_per_liter']:.2f} km/L", delta_color="inverse")
            
            st.divider()
            st.subheader("🛣️ Trip History")
            trip_records = df[df['time'] == 'TRIP'].copy()
            if not trip_records.empty:
                st.dataframe(trip_records[['date', 'plate_number', 'driver_name', 'distance_travelled']].sort_values(by='date', ascending=False), use_container_width=True)
            else:
                st.info("No trips recorded in 'Daily Trip Log'.")

    elif page == "⛽ Log Diesel Refuel":
        st.title("⛽ Diesel Refueling Entry")
        
        with st.container(border=True):
            c_date, c_plate = st.columns(2)
            with c_date: entry_date = st.date_input("Refuel Date", datetime.now())
            with c_plate: plate = st.text_input("Plate Number").upper()
            
            c_driver, c_liters = st.columns(2)
            with c_driver: driver = st.text_input("Driver Name")
            with c_liters: liters = st.number_input("Liters Loaded", min_value=0.0, step=0.1)
            
            st.write("---")
            c_odo1, c_odo2 = st.columns(2)
            with c_odo1: last_o = st.number_input("Opening Odometer", min_value=0.0, value=0.0)
            with c_odo2: next_o = st.number_input("Closing Odometer", min_value=0.0, value=0.0)
        
        if plate and driver and liters > 0:
            
            calc_dist = next_o - last_o if next_o > last_o else 0
            calc_eff = calc_dist / liters if calc_dist > 0 else 0
            
            st.warning("⚠️ **VALIDATE ENTRY:** Double-check the information before saving.")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Truck", plate)
            m2.metric("Liters", f"{liters} L")

            m3.metric("Distance", f"{calc_dist} km" if calc_dist > 0 else "N/A")
            
            if calc_eff > 0:
                st.info(f"💡 **Efficiency:** {calc_eff:,.2f} km/L")
            else:
                st.info("💡 **Note:** No Odometer readings available. Efficiency cannot be calculated.")
            
            confirmed = st.checkbox("CONFIRM")

            if confirmed:
                if st.button("💾 SAVE REFUEL LOG", type="primary", use_container_width=True):
                    if liters > stock: 
                        st.error(f"❌ Insufficient tank stock! (Available: {stock:,.2f} L)")
                    else:
                        conn = get_db()

                        conn.execute("""INSERT INTO fuel_logs 
                            (date, time, plate_number, driver_name, series, wheeler, liters_loaded, last_odometer, latest_odometer, distance_travelled) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                            (entry_date.strftime("%Y-%m-%d"), "MANUAL", plate, driver, get_next_series(), 4, liters, last_o, next_o, calc_dist))
                        conn.commit()
                        conn.close()
                        
                        update_inventory(liters)
                        st.success("✅ Saved! Successfully updated the inventory.")
                        time.sleep(3)
                        st.rerun()
        else:
            st.info("💡 Please fill in the Plate, Driver, and Liters fields to save the record.")

    elif page == "🛣️ Daily Trip Log":
        st.title("🛣️ Daily Trip Record")
        with st.form("trip_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            t_plate = c1.text_input("Plate Number").upper()
            t_customer = c1.text_input("Customer Name")
            t_dest = c2.text_input("Destination")
            t_date = c2.date_input("Trip Date", datetime.now())
            st.divider()
            t_open = st.number_input("Opening Odometer", min_value=0.0)
            t_close = st.number_input("Closing Odometer", min_value=0.0)
            if st.form_submit_button("💾 SAVE TRIP RECORD"):
                if t_plate and t_close > t_open:
                    details = f"CUST: {t_customer} | DEST: {t_dest}"
                    conn = get_db()
                    conn.execute("INSERT INTO fuel_logs (date, time, plate_number, driver_name, series, wheeler, liters_loaded, last_odometer, latest_odometer, distance_travelled) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                                (t_date.strftime("%Y-%m-%d"), "TRIP", t_plate, details, "TRIP", "N/A", 0.0, t_open, t_close, t_close-t_open))
                    conn.commit(); conn.close()
                    st.success("Trip Saved!"); time.sleep(1); st.rerun()

    elif page == "⚙️ Database Management":
        st.title("⚙️ Database Controls")
        view_tab, edit_tab, del_tab = st.tabs(["📋 View & Filter", "✏️ Edit Record", "🗑️ Delete Record"])
        all_logs = get_logs()
        
        with view_tab:
            if not all_logs.empty:
                all_logs['date'] = pd.to_datetime(all_logs['date']).dt.date
                c1, c2, c3 = st.columns([1,1,1])
                start_d = c1.date_input("Start Date", all_logs['date'].min())
                end_d = c2.date_input("End Date", all_logs['date'].max())
                p_list = ["ALL"] + sorted(all_logs['plate_number'].unique().tolist())
                s_plate = c3.selectbox("Filter Plate", p_list)
                f_df = all_logs[(all_logs['date'] >= start_d) & (all_logs['date'] <= end_d)]
                if s_plate != "ALL": f_df = f_df[f_df['plate_number'] == s_plate]
                st.dataframe(f_df.sort_values(by='id', ascending=False), use_container_width=True)
            else: st.info("Empty database.")

        with edit_tab:
            st.subheader("✏️ Edit Record")
            e_id = st.number_input("Enter Record ID to Edit:", step=1, min_value=1)
            if e_id:
                conn = get_db(); row = pd.read_sql_query("SELECT * FROM fuel_logs WHERE id = ?", conn, params=(e_id,)); conn.close()
                if not row.empty:
                    with st.form("edit_form"):
                        new_p = st.text_input("Plate", value=row.iloc[0]['plate_number']).upper()
                        new_l = st.number_input("Liters", value=float(row.iloc[0]['liters_loaded']))
                        new_d = st.number_input("Distance", value=float(row.iloc[0]['distance_travelled']))
                        if st.form_submit_button("Update"):
                            diff = new_l - row.iloc[0]['liters_loaded']
                            conn = get_db()
                            conn.execute("UPDATE fuel_logs SET plate_number=?, liters_loaded=?, distance_travelled=? WHERE id=?", (new_p, new_l, new_d, e_id))
                            conn.execute("UPDATE inventory SET current_stock = current_stock - ? WHERE id=1", (diff,))
                            conn.commit(); conn.close(); st.success("Updated!"); time.sleep(1); st.rerun()

        with del_tab:
            st.subheader("🗑️ Delete Record")
            d_id = st.number_input("Enter Record ID to Delete:", step=1, min_value=1)
            if st.button("🗑️ DELETE PERMANENTLY", type="primary"):
                conn = get_db(); res = conn.execute("SELECT liters_loaded FROM fuel_logs WHERE id=?", (d_id,)).fetchone()
                if res:
                    conn.execute("UPDATE inventory SET current_stock = current_stock + ? WHERE id=1", (res[0],))
                    conn.execute("DELETE FROM fuel_logs WHERE id=?", (d_id,))
                    conn.commit(); conn.close(); st.warning(f"Record #{d_id} deleted."); time.sleep(1); st.rerun()

    elif page == "🔐 Change Password":
        st.title("🔐 Change Account Password")
        with st.container(border=True):
            old_p = st.text_input("Current Password", type="password")
            new_p = st.text_input("New Password", type="password")
            confirm_p = st.text_input("Confirm New Password", type="password")
            
            if st.button("Update Password", use_container_width=True, type="primary"):
                if new_p != confirm_p:
                    st.error("Passwords do not match!")
                elif not new_p:
                    st.warning("Please enter a new password.")
                else:
                    conn = get_db()
                    c = conn.cursor()
                    # Tinitignan kung tama yung lumang password para sa current user
                    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (st.session_state['current_user'], old_p))
                    if c.fetchone():
                        c.execute("UPDATE users SET password = ? WHERE username = ?", (new_p, st.session_state['current_user']))
                        conn.commit()
                        st.success("Password updated successfully!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Incorrect current password.")
                    conn.close()