import {
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { OrderStatus } from '../generated/prisma/enums.js';
import { Prisma } from '../generated/prisma/client.js';
import { PrismaService } from '../prisma/prisma.service.js';
import { CreateOrderDto } from './dto/create-order.dto.js';

@Injectable()
export class OrdersService {
  constructor(private readonly prisma: PrismaService) {}

  async create(createOrderDto: CreateOrderDto) {
    const order = await this.prisma.$transaction(async (tx) => {
      // Serialize number allocation across concurrent API instances. The
      // lock lives only for this transaction and avoids unique-key races.
      await tx.$executeRawUnsafe(
        "SELECT pg_advisory_xact_lock(hashtext('orders.order_number'))",
      );
      const orderNumber = await this.nextOrderNumber(tx);

      const order = await tx.order.create({
        data: {
          orderNumber,
          date: createOrderDto.date ?? new Date(),
          customer: createOrderDto.customer.trim(),
          source: 'API',
        },
      });

      // A single product may appear more than once in the payload, so we
      // aggregate by product to validate stock and apply the movement once.
      const quantities = new Map<string, number>();
      for (const item of createOrderDto.items) {
        quantities.set(
          item.productId,
          (quantities.get(item.productId) ?? 0) + item.quantity,
        );
      }

      const pricedItems: Array<{
        productId: string;
        quantity: number;
        unitPrice: number;
        sku: string;
      }> = [];

      for (const [productId, quantity] of quantities) {
        const product = await tx.product.findUnique({
          where: { id: productId },
        });

        if (!product) {
          throw new NotFoundException(`Product ${productId} not found`);
        }

        if (product.stock < quantity) {
          throw new ConflictException(
            `Insufficient stock for product ${product.sku} (requested ${quantity}, available ${product.stock})`,
          );
        }

        pricedItems.push({
          productId,
          quantity,
          sku: product.sku,
          unitPrice: Number(product.price),
        });
      }

      for (const item of pricedItems) {
        const stockUpdate = await tx.product.updateMany({
          where: {
            id: item.productId,
            stock: { gte: item.quantity },
          },
          data: {
            stock: { decrement: item.quantity },
          },
        });

        if (stockUpdate.count !== 1) {
          throw new ConflictException(
            `Stock changed while creating the order for product ${item.sku}`,
          );
        }

        await tx.orderItem.create({
          data: {
            orderId: order.id,
            productId: item.productId,
            quantity: item.quantity,
            unitPrice: item.unitPrice,
          },
        });

        await tx.inventoryMovement.create({
          data: {
            productId: item.productId,
            type: 'OUT',
            quantity: item.quantity,
            reason: `Venta PED ${order.orderNumber}`,
            document: order.orderNumber,
            movementDate: order.date,
            source: 'API',
            externalKey: `${order.orderNumber}:${item.productId}`,
          },
        });
      }

      return this.loadOrder(tx, order.id);
    });

    return order;
  }

  async findAll() {
    return this.prisma.order.findMany({
      orderBy: { createdAt: 'desc' },
      include: {
        items: {
          include: { product: { select: { sku: true, name: true } } },
        },
      },
    });
  }

  async findOne(id: string) {
    const order = await this.loadOrder(this.prisma, id);

    if (!order) {
      throw new NotFoundException(`Order ${id} not found`);
    }

    return order;
  }

  async updateStatus(id: string, status: OrderStatus) {
    const order = await this.prisma.order.findUnique({
      where: { id },
    });

    if (!order) {
      throw new NotFoundException(`Order ${id} not found`);
    }

    return this.prisma.order.update({
      where: { id },
      data: { status },
    });
  }

  private loadOrder(client: Prisma.TransactionClient, orderId: string) {
    return client.order.findUnique({
      where: { id: orderId },
      include: {
        items: {
          include: {
            product: {
              select: { sku: true, name: true, price: true },
            },
          },
        },
      },
    });
  }

  private async nextOrderNumber(
    client: Prisma.TransactionClient,
  ): Promise<string> {
    const [row] = await client.$queryRawUnsafe<
      Array<{ next_number: bigint | number | string }>
    >(
      `SELECT COALESCE(MAX((regexp_match(order_number, '([0-9]+)$'))[1]::bigint), 999) + 1 AS next_number
       FROM orders
       WHERE order_number ~ '[0-9]+$'`,
    );

    return `PED-${String(row.next_number)}`;
  }
}
