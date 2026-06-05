import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

# --- STREAMLIT UI CONFIGURATION ---
st.set_page_config(page_title="Gas Cylinder Inventory Simulation", layout="wide")
st.title("📊 Industrial Gas Cylinder Inventory Simulation")
st.markdown("Tracking full/empty cylinder cycles, backlogs, and explicit supplier replenishment lead times.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Daily Demand Distribution")
demand_mean = st.sidebar.number_input("Mean Daily Demand", min_value=0.0, value=8.0, step=0.5)
demand_std = st.sidebar.number_input("Demand Std Dev", min_value=0.0, value=2.0, step=0.5)

st.sidebar.header("2. Supplier & Logistics Timeline")
ship_frequency = st.sidebar.number_input("Ship Empties Every X Days", min_value=1, value=10)
transit_out = st.sidebar.number_input("Transit Time to Supplier (Days)", min_value=0, value=5)
filling_time = st.sidebar.number_input("Supplier Filling Time (Days)", min_value=0, value=20)
transit_in = st.sidebar.number_input("Transit Time Back to Warehouse (Days)", min_value=0, value=5)

tot_lt= transit_out + filling_time + transit_in + ship_frequency
calc_init_stock= demand_mean * tot_lt + 2 * demand_std * np.sqrt(tot_lt)

st.sidebar.header("3. Simulation Parameters")
sim_days = st.sidebar.number_input("Simulation Duration (Days)", min_value=10, max_value=365, value=100, step=10)
initial_full = st.sidebar.number_input("Initial Full Stock", min_value=0, value=int(calc_init_stock))

# Calculate total turnaround time
total_lead_time = transit_out + filling_time + transit_in

st.sidebar.info(f"⏳ **Total Lead Time:** {total_lead_time} days.\n\n"
                f"An order sent on Day 10 will arrive and increase Full Stock on **Day {10 + total_lead_time}**.")

# --- SIMULATION ENGINE ---
if st.sidebar.button("Run Simulation", type="primary"):
    
    days = np.arange(1, sim_days + 1)
    
    # Generate random daily demand (rounded to whole cylinders, no negative demand)
    np.random.seed(42) 
    raw_demand = np.random.normal(demand_mean, demand_std, sim_days)
    daily_demand = np.maximum(0, np.round(raw_demand)).astype(int)
    
    # State variables
    full_stock = initial_full
    empty_stock = 0
    backlog = 0
    
    # Track metrics for correct Service Level
    total_demand_volume = 0
    total_on_time_fulfilled = 0
    
    # Pipeline tracking: { Arrival_Day: Number_of_Cylinders }
    supplier_delivery_pipeline = {}
    
    history = []
    
    for day in range(1, sim_days + 1):
        # --- STEP 1: ARRIVAL OF SUPPLIER ORDER ---
        arriving_cylinders = 0
        if day in supplier_delivery_pipeline:
            arriving_cylinders = supplier_delivery_pipeline[day]
            full_stock += arriving_cylinders
            
        # --- STEP 2: DEMAND & BACKLOG EVALUATION ---
        today_demand = daily_demand[day-1]
        total_demand_volume += today_demand
        total_unfulfilled_demand = today_demand + backlog
        
        # --- STEP 3: FULFILLMENT ---
        if full_stock >= total_unfulfilled_demand:
            fulfilled = total_unfulfilled_demand
            backlog = 0
            # Backlog is cleared entirely, meaning today's demand was met on-time
            on_time_fulfilled_today = today_demand 
        else:
            fulfilled = full_stock
            backlog = total_unfulfilled_demand - full_stock
            
            # Figure out what remains for today's demand after filling old backlog first
            allocated_to_today = max(0, fulfilled - (total_unfulfilled_demand - today_demand))
            on_time_fulfilled_today = allocated_to_today

        total_on_time_fulfilled += on_time_fulfilled_today
            
        # Update physical warehouse stocks based on fulfillment
        full_stock -= fulfilled
        empty_stock += fulfilled
        
        # --- STEP 4: SHIP EMPTY CYLINDERS TO SUPPLIER ---
        empties_shipped = 0
        arrival_day_calculated = 0
        
        if day % ship_frequency == 0 and empty_stock > 0:
            empties_shipped = empty_stock
            empty_stock = 0 # They leave our warehouse
            
            # Define exactly what future day these will arrive back as full stock
            arrival_day_calculated = day + total_lead_time
            supplier_delivery_pipeline[arrival_day_calculated] = (
                supplier_delivery_pipeline.get(arrival_day_calculated, 0) + empties_shipped
            )
            
        # Record day's data
        history.append({
            "Day": day,
            "Demand": today_demand,
            "Arriving from Supplier": arriving_cylinders,
            "Fulfilled": fulfilled,
            "Backlog": backlog,
            "Full Stock": full_stock,
            "Empty Stock": empty_stock,
            "Shipped to Supplier": empties_shipped,
            "Expected Return Day": arrival_day_calculated if empties_shipped > 0 else "-"
        })
        
    df_results = pd.DataFrame(history)
    
    # --- UI DISPLAY ---
    st.subheader("📊 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate real volume-based On-Time In-Full Service Level
    real_service_level = (total_on_time_fulfilled / total_demand_volume * 100) if total_demand_volume > 0 else 100.0
    
    col1.metric("Total Demand", f"{total_demand_volume} units")
    col2.metric("Total Fulfilled", f"{df_results['Fulfilled'].sum()} units")
    col3.metric("Max Backlog", f"{df_results['Backlog'].max()} units")
    col4.metric("On-Time Service Level (OTIF)", f"{real_service_level:.1f}%")
        
    st.subheader("📈 Stock Levels & Backlog Trajectory")
    df_melted = df_results.melt(
        id_vars=["Day"], 
        value_vars=["Full Stock", "Empty Stock", "Backlog"],
        var_name="Metric", value_name="Count"
    )
    fig = px.line(df_melted, x="Day", y="Count", color="Metric",
                  color_discrete_map={"Full Stock": "#2ca02c", "Empty Stock": "#ff7f0e", "Backlog": "#d62728"})
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("📋 Daily Operations Log")
    st.dataframe(df_results, width='content',hide_index=True)
