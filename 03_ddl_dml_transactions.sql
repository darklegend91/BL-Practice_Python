CREATE TABLE shipment_audit_test (
    audit_id SERIAL PRIMARY KEY,
    shipment_id TEXT,
    action_type TEXT,
    action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE shipments
ADD COLUMN shipment_status TEXT DEFAULT 'On Time';


-- Add a CHECK constraint so only valid status values are allowed
ALTER TABLE shipments
ADD CONSTRAINT shipments_status_check
CHECK (
    shipment_status IN (
        'On Time',
        'Delayed',
        'High Risk',
        'Completed'
    )
);


-- ----------------------------------------------------------
-- Optional meaningful risk classification column
-- ----------------------------------------------------------

ALTER TABLE shipment_risk
ADD COLUMN risk_classification TEXT;


-- Update risk classification based on delay probability
UPDATE shipment_risk
SET risk_classification =
    CASE
        WHEN delay_probability >= 0.70 THEN 'High'
        WHEN delay_probability >= 0.40 THEN 'Medium'
        ELSE 'Low'
    END;


-- ----------------------------------------------------------
-- 3. DROP
-- Drop the temporary audit table
-- ----------------------------------------------------------

DROP TABLE shipment_audit_test;


-- ----------------------------------------------------------
-- 4. TRUNCATE
-- Create a temporary table first so production data is safe
-- ----------------------------------------------------------

CREATE TABLE shipment_temp (
    shipment_id TEXT,
    remarks TEXT
);


-- Insert a sample row
INSERT INTO shipment_temp
VALUES ('TEST001', 'Temporary shipment record');


-- Remove all rows while keeping table structure
TRUNCATE TABLE shipment_temp;


-- Optional cleanup
DROP TABLE shipment_temp;



-- ==========================================================
-- B. DML OPERATIONS
-- ==========================================================


-- ----------------------------------------------------------
-- 1. INSERT A NEW SUPPLIER
-- ----------------------------------------------------------

INSERT INTO suppliers (
    supplier_id,
    country,
    political_risk_index,
    port_congestion_index,
    supplier_reliability
)
VALUES (
    'SUP051',
    'India',
    3.20,
    4.10,
    0.91
);


-- ----------------------------------------------------------
-- 2. INSERT A NEW SHIPMENT
-- ----------------------------------------------------------

-- First make sure the product exists
INSERT INTO products (
    product_type,
    monthly_demand_tons,
    alternative_supplier_count
)
VALUES (
    'Steel',
    25000,
    5
)
ON CONFLICT (product_type) DO NOTHING;


-- Insert shipment
INSERT INTO shipments (
    shipment_id,
    supplier_id,
    product_type,
    shipment_volume_tons,
    fuel_price_usd,
    historical_delay_days,
    transit_time_days,
    current_delay_days,
    freight_cost_usd,
    revenue_impact_usd,
    disruption_event,
    shipment_status
)
VALUES (
    'SHP1001',
    'SUP051',
    'Steel',
    5000,
    90.00,
    4,
    15,
    2,
    125000.00,
    250000.00,
    '0',
    'On Time'
);


-- Insert corresponding risk record
INSERT INTO shipment_risk (
    shipment_id,
    route_risk_score,
    delay_probability,
    risk_classification
)
VALUES (
    'SHP1001',
    4.50,
    0.30,
    'Low'
);


-- ----------------------------------------------------------
-- 3. UPDATE DELAYED SHIPMENTS
-- ----------------------------------------------------------

UPDATE shipments
SET shipment_status = 'Delayed'
WHERE current_delay_days > 0;


-- Optional check
SELECT
    shipment_id,
    current_delay_days,
    shipment_status
FROM shipments
WHERE shipment_status = 'Delayed';


-- ----------------------------------------------------------
-- 4. UPDATE FREIGHT COSTS FOR SELECTED SHIPMENTS
-- Example: increase freight cost by 8% for high-delay shipments
-- ----------------------------------------------------------

UPDATE shipments
SET freight_cost_usd = freight_cost_usd * 1.08
WHERE current_delay_days >= 10;


-- Verify
SELECT
    shipment_id,
    current_delay_days,
    freight_cost_usd
FROM shipments
WHERE current_delay_days >= 10;


-- ----------------------------------------------------------
-- 5. DELETE A TEST RECORD
-- ----------------------------------------------------------

-- Create a test supplier
INSERT INTO suppliers (
    supplier_id,
    country,
    political_risk_index,
    port_congestion_index,
    supplier_reliability
)
VALUES (
    'SUP_TEST',
    'Test Country',
    1.00,
    1.00,
    0.50
);


-- Delete test record
DELETE FROM suppliers
WHERE supplier_id = 'SUP_TEST';


-- ----------------------------------------------------------
-- 6. UPSERT USING ON CONFLICT
-- Insert supplier if new, otherwise update existing supplier
-- ----------------------------------------------------------

INSERT INTO suppliers (
    supplier_id,
    country,
    political_risk_index,
    port_congestion_index,
    supplier_reliability
)
VALUES (
    'SUP051',
    'India',
    3.50,
    4.30,
    0.94
)

ON CONFLICT (supplier_id)

DO UPDATE SET
    country = EXCLUDED.country,
    political_risk_index = EXCLUDED.political_risk_index,
    port_congestion_index = EXCLUDED.port_congestion_index,
    supplier_reliability = EXCLUDED.supplier_reliability;



-- ==========================================================
-- C. TRANSACTION EXERCISE — SUCCESSFUL TRANSACTION
-- BEGIN -> UPDATE -> VALIDATION -> COMMIT
-- ==========================================================

BEGIN;

-- Update shipment information
UPDATE shipments
SET
    current_delay_days = current_delay_days + 2,
    shipment_status = 'Delayed'
WHERE shipment_id = 'SHP1001';


-- Update related shipment risk
UPDATE shipment_risk
SET
    delay_probability = 0.60,
    risk_classification = 'Medium'
WHERE shipment_id = 'SHP1001';


-- Validation query before COMMIT
SELECT
    s.shipment_id,
    s.current_delay_days,
    s.shipment_status,
    sr.delay_probability,
    sr.risk_classification
FROM shipments s
JOIN shipment_risk sr
    ON s.shipment_id = sr.shipment_id
WHERE s.shipment_id = 'SHP1001';


-- Permanently save transaction
COMMIT;



-- ==========================================================
-- D. TRANSACTION EXERCISE — ERROR AND ROLLBACK
-- ==========================================================

BEGIN;


-- First valid update
UPDATE shipments
SET freight_cost_usd = freight_cost_usd + 5000
WHERE shipment_id = 'SHP1001';


-- Intentional error:
-- delay_probability must be between 0 and 1
UPDATE shipment_risk
SET delay_probability = 1.50
WHERE shipment_id = 'SHP1001';


-- PostgreSQL will generate an error because:
-- CHECK (delay_probability BETWEEN 0 AND 1)


-- Roll back all changes made in this transaction
ROLLBACK;


-- Verify that the freight cost update was also undone
SELECT
    s.shipment_id,
    s.freight_cost_usd,
    sr.delay_probability
FROM shipments s
JOIN shipment_risk sr
    ON s.shipment_id = sr.shipment_id
WHERE s.shipment_id = 'SHP1001';



-- ==========================================================
-- E. OPTIONAL: VIEW THE UPDATED RECORDS
-- ==========================================================

SELECT *
FROM shipments
WHERE shipment_id = 'SHP1001';


SELECT *
FROM shipment_risk
WHERE shipment_id = 'SHP1001';