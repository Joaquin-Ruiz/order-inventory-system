ALTER TABLE "products"
ADD CONSTRAINT "products_stock_non_negative"
CHECK ("stock" >= 0);

ALTER TABLE "products"
ADD CONSTRAINT "products_price_non_negative"
CHECK ("price" >= 0);

ALTER TABLE "order_items"
ADD CONSTRAINT "order_items_quantity_positive"
CHECK ("quantity" > 0);

ALTER TABLE "order_items"
ADD CONSTRAINT "order_items_unit_price_non_negative"
CHECK ("unit_price" >= 0);

ALTER TABLE "inventory_movements"
ADD CONSTRAINT "inventory_movements_quantity_positive"
CHECK ("quantity" > 0);