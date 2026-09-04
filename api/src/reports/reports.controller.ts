import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard.js';
import { TopProductsQueryDto } from './dto/top-products-query.dto.js';
import { ReportsService } from './reports.service.js';

@Controller('reports')
@UseGuards(JwtAuthGuard)
export class ReportsController {
  constructor(private readonly reportsService: ReportsService) {}

  @Get('top-products')
  topProducts(@Query() query: TopProductsQueryDto) {
    return this.reportsService.topProducts(query);
  }
}
