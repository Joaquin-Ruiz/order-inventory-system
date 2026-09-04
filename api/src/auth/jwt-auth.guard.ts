import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  // Nest 12 reflects the factory guard's optional module-options constructor
  // as a dependency. Declaring the no-argument constructor prevents feature
  // modules from trying to resolve that optional token themselves.
  constructor() {
    super();
  }
}
