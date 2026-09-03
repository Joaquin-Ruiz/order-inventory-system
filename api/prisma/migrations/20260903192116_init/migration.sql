-- CreateEnum
CREATE TYPE "OrderStatus" AS ENUM ('PENDING', 'PROCESSING', 'DISPATCHED', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "DataSource" AS ENUM ('API', 'ETL');

-- CreateEnum
CREATE TYPE "InventoryMovementType" AS ENUM ('IN', 'OUT', 'ADJUSTMENT');

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "password_hash" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "products" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "sku" TEXT NOT NULL,
    "stock" INTEGER NOT NULL DEFAULT 0,
    "price" DECIMAL(12,2) NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "orders" (
    "id" UUID NOT NULL,
    "order_number" TEXT NOT NULL,
    "date" TIMESTAMP(3) NOT NULL,
    "status" "OrderStatus" NOT NULL DEFAULT 'PENDING',
    "customer" TEXT NOT NULL,
    "source" "DataSource" NOT NULL DEFAULT 'API',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "order_items" (
    "id" UUID NOT NULL,
    "order_id" UUID NOT NULL,
    "product_id" UUID NOT NULL,
    "quantity" INTEGER NOT NULL,
    "unit_price" DECIMAL(12,2) NOT NULL,

    CONSTRAINT "order_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "inventory_movements" (
    "id" UUID NOT NULL,
    "product_id" UUID NOT NULL,
    "type" "InventoryMovementType" NOT NULL,
    "quantity" INTEGER NOT NULL,
    "reason" TEXT,
    "document" TEXT,
    "movement_date" TIMESTAMP(3) NOT NULL,
    "source" "DataSource" NOT NULL DEFAULT 'ETL',
    "external_key" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "inventory_movements_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE UNIQUE INDEX "products_sku_key" ON "products"("sku");

-- CreateIndex
CREATE UNIQUE INDEX "orders_order_number_key" ON "orders"("order_number");

-- CreateIndex
CREATE INDEX "orders_date_idx" ON "orders"("date");

-- CreateIndex
CREATE INDEX "orders_status_idx" ON "orders"("status");

-- CreateIndex
CREATE INDEX "order_items_product_id_idx" ON "order_items"("product_id");

-- CreateIndex
CREATE UNIQUE INDEX "order_items_order_id_product_id_key" ON "order_items"("order_id", "product_id");

-- CreateIndex
CREATE UNIQUE INDEX "inventory_movements_external_key_key" ON "inventory_movements"("external_key");

-- CreateIndex
CREATE INDEX "inventory_movements_product_id_idx" ON "inventory_movements"("product_id");

-- CreateIndex
CREATE INDEX "inventory_movements_movement_date_idx" ON "inventory_movements"("movement_date");

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "orders"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "inventory_movements" ADD CONSTRAINT "inventory_movements_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
