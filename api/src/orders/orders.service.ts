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
    const orderNumber = await this.nextOrderNumber();

    const order = await this.prisma.$transaction(async (tx) => {
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

        await tx.product.update({
          where: { id: item.productId },
          data: {
            stock: { decrement: item.quantity },
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

  private loadOrder(
    client: Prisma.TransactionClient,
    orderId: string,
  ) {
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

  private async nextOrderNumber(): Promise<string> {
    const last = await this.prisma.order.findFirst({
      orderBy: { orderNumber: 'desc' },
      select: { orderNumber: true },
    });

    if (!last) {
      return 'PED-1000';
    }

    const match = last.orderNumber.match(/(\d+)$/);

    const next = match ? Number(match[1]) + 1 : 1001;

    return `PED-${next}`;
  }
}
