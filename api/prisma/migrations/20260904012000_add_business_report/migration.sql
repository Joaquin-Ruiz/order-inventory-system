CREATE OR REPLACE FUNCTION top_selling_products(
    p_from TIMESTAMP,
    p_to TIMESTAMP,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    product_id UUID,
    sku TEXT,
    product_name TEXT,
    total_quantity_sold BIGINT,
    total_revenue NUMERIC(14, 2),
    order_count BIGINT,
    api_order_count BIGINT,
    etl_order_count BIGINT,
    current_stock INTEGER,
    net_inventory_movement BIGINT
)
LANGUAGE sql
STABLE
AS $$
WITH sales AS (
    SELECT
        oi.product_id,
        SUM(oi.quantity)::BIGINT AS total_quantity_sold,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)::NUMERIC(14, 2) AS total_revenue,
        COUNT(DISTINCT o.id)::BIGINT AS order_count,
        COUNT(DISTINCT o.id) FILTER (WHERE o.source = 'API')::BIGINT AS api_order_count,
        COUNT(DISTINCT o.id) FILTER (WHERE o.source = 'ETL')::BIGINT AS etl_order_count
    FROM order_items oi
    INNER JOIN orders o ON o.id = oi.order_id
    WHERE o.date >= p_from
      AND o.date < (p_to + INTERVAL '1 day')
      AND o.status <> 'CANCELLED'
    GROUP BY oi.product_id
), movements AS (
    SELECT
        im.product_id,
        SUM(
            CASE im.type
                WHEN 'IN' THEN im.quantity
                WHEN 'OUT' THEN -im.quantity
                ELSE im.quantity
            END
        )::BIGINT AS net_inventory_movement
    FROM inventory_movements im
    WHERE im.movement_date >= p_from
      AND im.movement_date < (p_to + INTERVAL '1 day')
    GROUP BY im.product_id
)
SELECT
    p.id AS product_id,
    p.sku,
    p.name AS product_name,
    s.total_quantity_sold,
    s.total_revenue,
    s.order_count,
    s.api_order_count,
    s.etl_order_count,
    p.stock AS current_stock,
    COALESCE(m.net_inventory_movement, 0)::BIGINT AS net_inventory_movement
FROM sales s
INNER JOIN products p ON p.id = s.product_id
LEFT JOIN movements m ON m.product_id = p.id
ORDER BY s.total_quantity_sold DESC, s.total_revenue DESC, p.sku ASC
LIMIT GREATEST(COALESCE(p_limit, 5), 1);
$$;
