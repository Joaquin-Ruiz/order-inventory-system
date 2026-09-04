import { BadRequestException, Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service.js';
import { TopProductsQueryDto } from './dto/top-products-query.dto.js';

type TopSellingProductRow = {
  product_id: string;
  sku: string;
  product_name: string;
  total_quantity_sold: bigint;
  total_revenue: unknown;
  order_count: bigint;
  api_order_count: bigint;
  etl_order_count: bigint;
  current_stock: number;
  net_inventory_movement: bigint;
};

@Injectable()
export class ReportsService {
  constructor(private readonly prisma: PrismaService) {}

  async topProducts(query: TopProductsQueryDto) {
    const from = new Date(query.from);
    const to = new Date(query.to);

    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
      throw new BadRequestException('Invalid date range');
    }

    if (from > to) {
      throw new BadRequestException('from must be before or equal to to');
    }

    const rows = await this.prisma.$queryRawUnsafe<TopSellingProductRow[]>(
      'SELECT * FROM top_selling_products($1::timestamp, $2::timestamp, $3::integer)',
      from,
      to,
      query.limit ?? 5,
    );

    return rows.map((row) => ({
      productId: row.product_id,
      sku: row.sku,
      productName: row.product_name,
      totalQuantitySold: Number(row.total_quantity_sold),
      totalRevenue: Number(row.total_revenue),
      orderCount: Number(row.order_count),
      apiOrderCount: Number(row.api_order_count),
      etlOrderCount: Number(row.etl_order_count),
      currentStock: row.current_stock,
      netInventoryMovement: Number(row.net_inventory_movement),
    }));
  }
}
