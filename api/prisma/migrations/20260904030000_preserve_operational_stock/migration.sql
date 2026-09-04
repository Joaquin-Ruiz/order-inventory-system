-- Track the last stock snapshot imported from the catalog. The first import
-- after this migration calibrates the snapshot without resetting stock that
-- may already have been changed by API orders.
ALTER TABLE "products"
ADD COLUMN "catalog_stock" INTEGER;

ALTER TABLE "products"
ADD CONSTRAINT "products_catalog_stock_non_negative"
CHECK ("catalog_stock" IS NULL OR "catalog_stock" >= 0);
