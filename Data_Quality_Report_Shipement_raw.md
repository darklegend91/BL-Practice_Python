# Data Quality Report

## What is the data about 

This dataset contains the information about the shipments that are being passed from the hormuz point and their impacts .

## Our 5‑Layer Framework

### Layer 1: Structural Integrity (The “Skeleton”)

Primary Key Uniqueness: No duplicate Shipemnt_id in data.
`select count(*) from shipment_raw group by shipment_id having count(*) > 1`

Foreign Key Logic: Even if you don’t have a separate Supplier table, check if Supplier_ID appears in a consistent format (e.g., always “SUP” + 3 digits).

`SELECT COUNT(*) AS Non_Consistent_supplier FROM shipment_raw WHERE supplier_id !~ '^SUP[0-9]{3}$'`

### Layer 2: Completeness (The “Fill Rate”)
The null percentage per column.

`SELECT COUNT(*) FILTER (WHERE shipment_id IS NULL) AS null_shipment_id, 
    COUNT(*) FILTER (WHERE supplier_id IS NULL) AS null_supplier_id,
    COUNT(*) FILTER (WHERE country IS NULL) AS null_country,
    COUNT(*) FILTER (WHERE product_type IS NULL) AS null_product_type,
    COUNT(*) FILTER (WHERE monthly_demand_tons IS NULL) AS null_monthly_demand,
    COUNT(*) FILTER (WHERE shipment_volume_tons IS NULL) AS null_shipment_volume,
    COUNT(*) FILTER (WHERE route_risk_score IS NULL) AS null_route_risk,
    COUNT(*) FILTER (WHERE historical_delay_days IS NULL) AS null_historical_delay,
    COUNT(*) FILTER (WHERE fuel_price_usd IS NULL) AS null_fuel_price,
    COUNT(*) FILTER (WHERE political_risk_index IS NULL) AS null_political_risk,
    COUNT(*) FILTER (WHERE port_congestion_index IS NULL) AS null_port_congestion,
    COUNT(*) FILTER (WHERE inventory_days IS NULL) AS null_inventory_days,
    COUNT(*) FILTER (WHERE supplier_reliability IS NULL) AS null_supplier_reliability,
    COUNT(*) FILTER (WHERE alternative_supplier_count IS NULL) AS null_alt_supplier,
    COUNT(*) FILTER (WHERE transit_time_days IS NULL) AS null_transit_time,
    COUNT(*) FILTER (WHERE delay_probability IS NULL) AS null_delay_prob,
    COUNT(*) FILTER (WHERE current_delay_days IS NULL) AS null_current_delay,
    COUNT(*) FILTER (WHERE freight_cost_usd IS NULL) AS null_freight_cost,
    COUNT(*) FILTER (WHERE revenue_impact_usd IS NULL) AS null_revenue_impact,
    COUNT(*) FILTER (WHERE disruption_event IS NULL) AS null_disruption_event
FROM shipment_raw;`

"null_shipment_id"	"null_supplier_id"	"null_country"	"null_product_type"	"null_monthly_demand"	"null_shipment_volume"	"null_route_risk"	"null_historical_delay"	"null_fuel_price"	"null_political_risk"	"null_port_congestion"	"null_inventory_days"	"null_supplier_reliability"	"null_alt_supplier"	"null_transit_time"	"null_delay_prob"	"null_current_delay"	"null_freight_cost"	"null_revenue_impact"	"null_disruption_event"
0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0	0

### Layer 3: Domain & Range Validation (The “Rules”)
This is where you apply business logic to the numeric fields. For your specific schema:

Boundary checks:

Delay_Probability must be between 0.00 and 1.00.

`SELECT COUNT(*) AS out_of_range
FROM shipment_raw
WHERE delay_probability <0 and  delay_probability > 1;`

Route_Risk_Score, Political_Risk_Index, and Port_Congestion_Index should fall within plausible industry ranges (e.g., 1 to 10).

Supplier_Reliability should be between 0 and 1 (or 0–100%, depending on your source).

Non‑negative rules:

Tons, Costs, Days, and Supplier Counts must be ≥ 0. Negative inventory days or negative freight costs are immediate red flags.

Categorical integrity:

Country and Product_Type (e.g., Crude Oil, LNG, Electronics) should match a predefined master list. If you spot “USA” vs “United States” or “Oil” vs “Crude Oil,” that’s a validity issue.

### Layer 4: Intra‑Record Logic (The “Sanity Checks”)
This is the most valuable part of a supply chain DQR. It checks if the numbers in a single row make logical sense together:

Volume vs. Demand: Shipment_Volume_Tons should generally not exceed Monthly_Demand_Tons by a massive margin (unless you are stockpiling). Extreme outliers here suggest data entry errors.

Risk vs. Reliability: If Supplier_Reliability is high (e.g., 0.95), but Historical_Delay_Days and Delay_Probability are also high, that contradicts the definition of reliability.

Risk vs. Cost: If a route has a very high Route_Risk_Score but abnormally low Freight_Cost_USD, it might be a mis‑priced entry or a missing risk premium.

Transit Time vs. Delays: Transit_Time_Days should logically be greater than Current_Delay_Days (you can’t have a delay longer than the total journey).

### Layer 5: Cross‑Record Consistency (The “Patterns”)
Looking at rows together reveals hidden data quality issues:

Supplier consistency: Does the same Supplier_ID always ship from the same Country? If Supplier 015 appears in both Oman and Iraq, your geographic risk analysis will be polluted.

Statistical outliers: Flag any value that is more than 3 standard deviations away from the column mean. For example, if the average Freight_Cost_USD is $200k, but one row shows $20M, that single outlier could skew your entire profit analysis.

Duplicate logical keys: Even if Shipment_ID is unique, are there duplicate combinations of Supplier_ID, Country, Product_Type, and Date (if you had dates)? This could indicate accidental duplicate entries.