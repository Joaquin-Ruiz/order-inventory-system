import { PrismaService } from '../prisma/prisma.service.js';
import { OrdersService } from './orders.service.js';

describe('OrdersService', () => {
  it('allocates the order number under a transaction lock', async () => {
    const productId = '00000000-0000-0000-0000-000000000001';
    const createdOrder = {
      id: '00000000-0000-0000-0000-000000000002',
      orderNumber: 'PED-10000',
      date: new Date('2026-06-01T10:00:00.000Z'),
    };
    const loadedOrder = { ...createdOrder, items: [] };

    const tx = {
      $executeRawUnsafe: vi.fn().mockResolvedValue(1),
      $queryRawUnsafe: vi.fn().mockResolvedValue([{ next_number: 10000n }]),
      order: {
        create: vi.fn().mockResolvedValue(createdOrder),
        findUnique: vi.fn().mockResolvedValue(loadedOrder),
      },
      product: {
        findUnique: vi.fn().mockResolvedValue({
          id: productId,
          sku: 'FER-0001',
          stock: 10,
          price: 1500,
        }),
        updateMany: vi.fn().mockResolvedValue({ count: 1 }),
      },
      orderItem: { create: vi.fn().mockResolvedValue({}) },
      inventoryMovement: { create: vi.fn().mockResolvedValue({}) },
    };
    const prisma = {
      $transaction: vi.fn((callback) => callback(tx)),
    };
    const service = new OrdersService(prisma as unknown as PrismaService);

    const result = await service.create({
      customer: 'Cliente de prueba',
      date: createdOrder.date,
      items: [{ productId, quantity: 2 }],
    });

    expect(result).toEqual(loadedOrder);
    expect(tx.$executeRawUnsafe).toHaveBeenCalledWith(
      "SELECT pg_advisory_xact_lock(hashtext('orders.order_number'))",
    );
    expect(tx.order.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ orderNumber: 'PED-10000' }),
      }),
    );
    expect(tx.product.updateMany).toHaveBeenCalledWith({
      where: { id: productId, stock: { gte: 2 } },
      data: { stock: { decrement: 2 } },
    });
    expect(tx.$executeRawUnsafe.mock.invocationCallOrder[0]).toBeLessThan(
      tx.$queryRawUnsafe.mock.invocationCallOrder[0],
    );
    expect(tx.$queryRawUnsafe.mock.invocationCallOrder[0]).toBeLessThan(
      tx.order.create.mock.invocationCallOrder[0],
    );
  });
});
