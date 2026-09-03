import {
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service.js';
import { CreateProductDto } from './dto/create-product.dto.js';
import { UpdateProductDto } from './dto/update-product.dto.js';
import { normalizeSku } from '../common/utils/normalize-sku.js';

@Injectable()
export class ProductsService {
  constructor(private readonly prisma: PrismaService) {}

  async create(createProductDto: CreateProductDto) {
    const sku = normalizeSku(createProductDto.sku);

    const existingProduct = await this.prisma.product.findUnique({
      where: { sku },
    });

    if (existingProduct) {
      throw new ConflictException(
        `Product with SKU ${sku} already exists`,
      );
    }

    return this.prisma.product.create({
      data: {
        name: createProductDto.name.trim(),
        sku,
        stock: createProductDto.stock,
        price: createProductDto.price,
        active: createProductDto.active ?? true,
      },
    });
  }

  async findAll() {
    return this.prisma.product.findMany({
      orderBy: {
        createdAt: 'desc',
      },
    });
  }

  async findOne(id: string) {
    const product = await this.prisma.product.findUnique({
      where: { id },
    });

    if (!product) {
      throw new NotFoundException(`Product ${id} not found`);
    }

    return product;
  }

  async update(id: string, updateProductDto: UpdateProductDto) {
    await this.findOne(id);

    const data = {
      ...updateProductDto,
      ...(updateProductDto.name && {
        name: updateProductDto.name.trim(),
      }),
      ...(updateProductDto.sku && {
        sku: normalizeSku(updateProductDto.sku),
      }),
    };

    if (data.sku) {
      const existingProduct = await this.prisma.product.findUnique({
        where: { sku: data.sku },
      });

      if (existingProduct && existingProduct.id !== id) {
        throw new ConflictException(
          `Product with SKU ${data.sku} already exists`,
        );
      }
    }

    return this.prisma.product.update({
      where: { id },
      data,
    });
  }

  async remove(id: string) {
    await this.findOne(id);

    await this.prisma.product.delete({
      where: { id },
    });

    return {
      message: 'Product deleted successfully',
    };
  }
}