--Create a table named shipmnt_raw with the column names.
Create TABLE shipment_raw (
   Shipment_ID              TEXT,
    Supplier_ID              TEXT,
    Country                  TEXT,
    Product_Type             TEXT,
    Monthly_Demand_Tons      NUMERIC,
    Shipment_Volume_Tons     NUMERIC,
    Route_Risk_Score         NUMERIC,
    Historical_Delay_Days    INTEGER,
    Fuel_Price_USD           NUMERIC,
    Political_Risk_Index     NUMERIC,
    Port_Congestion_Index    NUMERIC,
    Inventory_Days           INTEGER,
    Supplier_Reliability     NUMERIC,
    Alternative_Supplier_Count INTEGER,
    Transit_Time_Days        INTEGER,
    Delay_Probability        NUMERIC,
    Current_Delay_Days       INTEGER,
    Freight_Cost_USD         NUMERIC,
    Revenue_Impact_USD       NUMERIC,
    Disruption_Event         TEXT
);

-- Import data from tools in upper top left and import our csv data from the file 

--To find if data is loaded or not
Select * from shipment_raw

-- Find Total Number of records
select count(*) as total_Number_of_Records from shipment_raw;

-- Print all the numbers of the columns in table
SELECT
	COUNT(*) AS NUMBER_OF_COLUMNS
FROM
	INFORMATION_SCHEMA.COLUMNS
WHERE
	TABLE_NAME = 'shipment_raw';

--Find number of null Values
SELECT 
    COUNT(*) FILTER (WHERE shipment_id IS NULL) AS null_shipment_id,
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
FROM shipment_raw;

-- Duplicate Shipment IDs
SELECT
	SHIPMENT_ID,
	COUNT(*) AS DUPLICATE_SHIPMENT_COUNT
FROM
	SHIPMENT_RAW
GROUP BY
	SHIPMENT_ID
HAVING
	COUNT(*) > 1
ORDER BY
	DUPLICATE_SHIPMENT_COUNT DESC;

-- Duplicate Supplier IDs
SELECT
	SUPPLIER_ID,
	COUNT(*) AS DUPLICATE_SUPPLIER_IDS
FROM
	SHIPMENT_RAW
GROUP BY
	SUPPLIER_ID
HAVING
	COUNT(*) > 1
ORDER BY
	DUPLICATE_SUPPLIER_IDS DESC;

-- Negative values where they should not exist
select 
    COUNT(*) FILTER (WHERE monthly_demand_tons < 0) AS negative_monthly_demand,
    COUNT(*) FILTER (WHERE shipment_volume_tons < 0) AS negative_shipment_volume,
    COUNT(*) FILTER (WHERE route_risk_score < 0) AS negative_route_risk,
    COUNT(*) FILTER (WHERE historical_delay_days < 0) AS negative_historical_delay,
    COUNT(*) FILTER (WHERE fuel_price_usd <0) AS negative_fuel_price,
    COUNT(*) FILTER (WHERE political_risk_index < 0) AS negative_political_risk,
    COUNT(*) FILTER (WHERE port_congestion_index < 0) AS negative_port_congestion,
    COUNT(*) FILTER (WHERE inventory_days <0 ) AS negative_inventory_days,
    COUNT(*) FILTER (WHERE supplier_reliability < 0 ) AS negative_supplier_reliability,
    COUNT(*) FILTER (WHERE alternative_supplier_count< 0 ) AS negative_alt_supplier,
    COUNT(*) FILTER (WHERE transit_time_days< 0) AS negative_transit_time,
    COUNT(*) FILTER (WHERE delay_probability  < 0) AS negative_delay_prob,
    COUNT(*) FILTER (WHERE current_delay_days < 0 ) AS negative_current_delay,
    COUNT(*) FILTER (WHERE freight_cost_usd  < 0) AS negative_freight_cost
from shipment_raw;





-- SQL Queries for Data Quality Report

