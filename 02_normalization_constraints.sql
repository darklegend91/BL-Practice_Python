CREATE TABLE suppliers (
    supplier_id TEXT PRIMARY KEY,
    country TEXT NOT NULL,
    political_risk_index NUMERIC(10, 2) CHECK (political_risk_index >= 0),
    port_congestion_index NUMERIC(10, 2) CHECK (port_congestion_index >= 0),
    supplier_reliability NUMERIC(3, 2) CHECK (supplier_reliability BETWEEN 0 AND 1)
);

-- ==========================================================
-- 2. PRODUCTS TABLE
-- ==========================================================
CREATE TABLE products (
    product_type TEXT PRIMARY KEY,
    monthly_demand_tons NUMERIC(12, 2) CHECK (monthly_demand_tons > 0),
    alternative_supplier_count INTEGER CHECK (alternative_supplier_count >= 0)
);

-- ==========================================================
-- 3. INVENTORY TABLE (Bridge between Suppliers & Products)
-- ==========================================================
CREATE TABLE inventory (
    inventory_id SERIAL PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    product_type TEXT NOT NULL REFERENCES products(product_type) ON DELETE CASCADE,
    inventory_days INTEGER CHECK (inventory_days >= 0),
    
    -- Candidate Key: A supplier can only have one inventory record per product
    CONSTRAINT unique_supplier_product UNIQUE (supplier_id, product_type)
);

-- ==========================================================
-- 4. SHIPMENTS TABLE (The main transaction table)
-- ==========================================================
CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
    product_type TEXT NOT NULL REFERENCES products(product_type) ON DELETE RESTRICT,
    shipment_volume_tons NUMERIC(12, 2) CHECK (shipment_volume_tons > 0),
    fuel_price_usd NUMERIC(12, 2) CHECK (fuel_price_usd >= 0),
    historical_delay_days INTEGER CHECK (historical_delay_days >= 0),
    transit_time_days INTEGER CHECK (transit_time_days >= 0),
    current_delay_days INTEGER CHECK (current_delay_days >= 0),
    freight_cost_usd NUMERIC(15, 2) CHECK (freight_cost_usd >= 0),
    revenue_impact_usd NUMERIC(15, 2) CHECK (revenue_impact_usd >= 0),
    disruption_event TEXT,
    
    -- Optional: If you want to enforce that current delay cannot exceed transit time
    CHECK (current_delay_days <= transit_time_days)
);

-- ==========================================================
-- 5. SHIPMENT RISK TABLE (1-to-1 relationship with shipments)
-- ==========================================================
CREATE TABLE shipment_risk (
    risk_id SERIAL PRIMARY KEY,
    shipment_id TEXT NOT NULL UNIQUE REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    route_risk_score NUMERIC(10, 2) CHECK (route_risk_score >= 0),
    delay_probability NUMERIC(3, 2) CHECK (delay_probability BETWEEN 0 AND 1)
);





-- Data Insertion
INSERT INTO suppliers (supplier_id, country, political_risk_index, port_congestion_index, supplier_reliability)
SELECT DISTINCT
    supplier_id,
    country,
    political_risk_index,
    port_congestion_index,
    supplier_reliability
FROM shipment_raw
ON CONFLICT (supplier_id) DO NOTHING;


INSERT INTO products (product_type, monthly_demand_tons, alternative_supplier_count)
SELECT DISTINCT
    product_type,
    monthly_demand_tons,
    alternative_supplier_count
FROM shipment_raw
ON CONFLICT (product_type) DO NOTHING;

INSERT INTO inventory (supplier_id, product_type, inventory_days)
SELECT DISTINCT
    supplier_id,
    product_type,
    inventory_days
FROM shipment_raw
ON CONFLICT (supplier_id, product_type) DO NOTHING;



SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'shipments'::regclass 
  AND contype = 'c';

ALTER TABLE shipments DROP CONSTRAINT shipments_check;
ALTER TABLE shipments DROP CONSTRAINT shipments_revenue_impact_usd_check;

INSERT INTO shipments (
    shipment_id, supplier_id, product_type, shipment_volume_tons,
    fuel_price_usd, historical_delay_days, transit_time_days,
    current_delay_days, freight_cost_usd, revenue_impact_usd,
    disruption_event
)
SELECT 
    shipment_id, supplier_id, product_type, shipment_volume_tons,
    fuel_price_usd, historical_delay_days, transit_time_days,
    current_delay_days, freight_cost_usd, revenue_impact_usd,
    disruption_event
FROM shipment_raw
ON CONFLICT (shipment_id) DO NOTHING;


INSERT INTO shipment_risk (shipment_id, route_risk_score, delay_probability)
SELECT 
    shipment_id, route_risk_score, delay_probability
FROM shipment_raw
ON CONFLICT (shipment_id) DO NOTHING;