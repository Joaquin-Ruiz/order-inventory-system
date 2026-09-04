import { Test } from '@nestjs/testing';
import { GUARDS_METADATA } from '@nestjs/common/constants';
import { AppModule } from './app.module.js';
import { JwtAuthGuard } from './auth/jwt-auth.guard.js';
import { PrismaService } from './prisma/prisma.service.js';
import { ProductsController } from './products/products.controller.js';

process.env.JWT_SECRET ??= 'test-only-jwt-secret';

describe('AppModule', () => {
  it('resolves the shared JWT guard for protected feature modules', async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PrismaService)
      .useValue({})
      .compile();

    expect(moduleRef.get(JwtAuthGuard)).toBeInstanceOf(JwtAuthGuard);

    const productGuards = Reflect.getMetadata(
      GUARDS_METADATA,
      ProductsController,
    ) as unknown[];
    expect(productGuards).toContain(JwtAuthGuard);

    await moduleRef.close();
  });
});
