import { INestApplication } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module.js';
import { PrismaService } from '../src/prisma/prisma.service.js';

process.env.JWT_SECRET ??= 'test-only-jwt-secret';

describe('JWT protection (e2e)', () => {
  let app: INestApplication;
  let jwtService: JwtService;

  const prisma = {
    product: {
      findMany: vi.fn().mockResolvedValue([]),
    },
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PrismaService)
      .useValue(prisma)
      .compile();

    jwtService = moduleFixture.get(JwtService);
    app = moduleFixture.createNestApplication();
    app.setGlobalPrefix('api');
    await app.init();
  });

  it('rejects unauthenticated product requests', async () => {
    await request(app.getHttpServer()).get('/api/products').expect(401);
  });

  it('accepts a valid bearer token', async () => {
    const token = await jwtService.signAsync({
      sub: '00000000-0000-0000-0000-000000000001',
      email: 'admin@example.com',
    });

    await request(app.getHttpServer())
      .get('/api/products')
      .set('Authorization', `Bearer ${token}`)
      .expect(200)
      .expect([]);
  });

  afterAll(async () => {
    await app.close();
  });
});
