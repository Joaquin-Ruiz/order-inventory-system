# Order & Inventory Management System

Sistema backend para gestion de productos, pedidos e inventario, con API REST en NestJS, PostgreSQL, Prisma y un pipeline ETL en Python para integrar archivos Excel sucios en la misma base de datos.

## Stack

- NestJS + TypeScript
- PostgreSQL 16
- Prisma migrations
- JWT authentication
- Python + Pandas + SQLAlchemy
- Docker Compose
- Swagger/OpenAPI
- pytest

## Estructura

```text
.
├── api/                    # API REST NestJS
│   ├── prisma/             # Schema y migraciones
│   └── src/                # Modulos auth/products/orders/reports/users
├── data/examples/          # Datasets Excel de entrada
├── etl/                    # Pipeline ETL Python
│   ├── etl.py              # Orquestador CLI
│   ├── src/                # Readers, cleaners, validators, DB layer
│   └── tests/              # Pruebas pytest
├── docker-compose.yml      # PostgreSQL
├── .env.example
└── README.md
```

## Requisitos

- Docker + Docker Compose
- Node.js 20+ (probado con Node 24)
- npm
- Python 3.11+

## Variables De Entorno

Crear `.env` en la raiz copiando `.env.example`:

```bash
cp .env.example .env
```

Valores usados en desarrollo:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=order_inventory
POSTGRES_PORT=5432
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/order_inventory
JWT_SECRET=replace_with_a_long_random_secret
JWT_EXPIRES_IN=1h
```

La API tambien puede usar `api/.env` con el mismo `DATABASE_URL`, `JWT_SECRET` y `JWT_EXPIRES_IN`. `JWT_SECRET` es obligatorio: la API falla al iniciar si no esta definido, en vez de usar una credencial embebida en el codigo.

## Levantar PostgreSQL

Desde la raiz del proyecto:

```bash
docker compose up -d
```

Esto levanta PostgreSQL en `localhost:5432` usando las variables del `.env`.

## Instalar Dependencias API

```bash
cd api
npm ci
```

## Migraciones Prisma

Con PostgreSQL levantado:

```bash
cd api
npx prisma migrate deploy
```

Para regenerar el cliente Prisma si hiciera falta:

```bash
npx prisma generate
```

## Levantar API

```bash
cd api
npm run start:dev
```

La API queda disponible en:

```text
http://localhost:3000/api
```

Swagger/OpenAPI:

```text
http://localhost:3000/api/docs
```

## Auth/JWT

Registrar usuario:

```bash
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password123"}'
```

Login:

```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password123"}'
```

La respuesta incluye un `accessToken`. Usarlo en endpoints protegidos:

```bash
curl http://localhost:3000/api/orders \
  -H "Authorization: Bearer <accessToken>"
```

Endpoints protegidos con JWT:

- `GET /api/auth/profile`
- `GET /api/users`
- `GET/POST/PATCH/DELETE /api/products`
- `GET /api/orders`
- `POST /api/orders`
- `PATCH /api/orders/:id/status`
- `GET /api/reports/top-products`

## Endpoints Principales

Productos:

- `POST /api/products`
- `GET /api/products`
- `GET /api/products/:id`
- `PATCH /api/products/:id`
- `DELETE /api/products/:id`

Pedidos:

- `POST /api/orders`
- `GET /api/orders`
- `GET /api/orders/:id`
- `PATCH /api/orders/:id/status`

Reporte:

- `GET /api/reports/top-products?from=2026-01-01&to=2026-06-30&limit=5`

## Crear Pedido

Ejemplo de creacion de pedido. El endpoint valida stock y ejecuta todo en una transaccion: si un producto no existe o no tiene stock suficiente, hace rollback completo.

```bash
curl -X POST http://localhost:3000/api/orders \
  -H "Authorization: Bearer <accessToken>" \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Comercial Andes Sur SpA",
    "items": [
      {"productId": "<product-uuid>", "quantity": 2}
    ]
  }'
```

Al crear un pedido:

- Se genera `order_number` correlativo (`PED-xxxx`).
- Se agregan cantidades repetidas por producto.
- Se valida stock dentro de la transaccion.
- Se crean `order_items`.
- Se descuenta stock.
- Se registra un `inventory_movement` tipo `OUT` con `source=API`.

## ETL

El ETL vive en `etl/` y lee los archivos de `data/examples/`.

Instalar dependencias:

```bash
cd etl
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Dry-run sin escribir en BD:

```bash
python etl.py --dry-run
```

Ejecutar carga completa:

```bash
python etl.py
```

Ejecutar una fuente especifica:

```bash
python etl.py catalog
python etl.py orders
python etl.py details
python etl.py movements
```

Usar una carpeta o archivo especifico:

```bash
python etl.py --input ../data/examples
python etl.py catalog --input ../data/examples/01_catalogo_productos_2026.xlsx
python etl.py --input ../data/incoming-export.xlsx
```

Los archivos explicitos se identifican por su contenido, por lo que un job puede renombrarlos. El proceso retorna codigo distinto de cero si no reconoce una entrada, falta una fuente solicitada o falla una escritura en PostgreSQL; esto permite que cron/schedulers detecten el fallo.

El ETL usa `ETL_DATABASE_URL` si existe; si no, usa `DATABASE_URL`. Para cargas reales una de las dos es obligatoria; `--dry-run` no necesita credenciales.

## ETL: Resultado Esperado

Con los datasets incluidos, el dry-run reporta aproximadamente:

```text
catalog    raw=101    cleaned=101    rejected=0
orders     raw=407    cleaned=407    rejected=6
details    raw=1033   cleaned=940    rejected=0
movements  raw=201    cleaned=201    rejected=0
```

En una base limpia, la carga validada en PostgreSQL deja:

```text
products: 101
orders: 401
order_items: 940
inventory_movements: 201
```

Las seis cabeceras rechazadas tienen fecha nula o imposible y no poseen items en el detalle, por lo que los 940 items limpios son vinculables.

## Reglas De Calidad Del ETL

Productos:

- Normaliza SKU con el mismo criterio de la API: `PREFIX-0000` (`FER-10` -> `FER-0010`).
- Descarta filas sin SKU valido o sin nombre.
- Deduplica por SKU; gana la ultima version procesada.
- Aplica correcciones publicadas en la hoja `CORRECCIONES MARZO`.
- Normaliza precios de `HOGAR` a neto, porque esa hoja declara precios con IVA incluido (19%).
- Stock negativo se fuerza a 0.

Pedidos:

- Deduplica por `order_number`.
- Normaliza fechas mixtas: ISO, serial Excel, `14-abr-26`, `28 de abr de 26`, etc.
- Rechaza fechas imposibles o nulas (`invalid_date`).
- Mapea estados libres a enum: `PENDING`, `PROCESSING`, `DISPATCHED`, `COMPLETED`, `CANCELLED`.
- Estados desconocidos caen a `PENDING`.

Detalle de pedidos:

- Lee 5 bloques `CARGA` con columnas en distinto orden.
- Lee `DETALLE ANEXO` como carga tardia.
- Detecta columnas por encabezado, no por posicion fija.
- Resuelve filas sin SKU por descripcion contra el catalogo.
- Normaliza cantidades y precios en formato CLP (`$ 38.640`, `1.760,00`, `5.260`).
- Agrupa por `(order_number, sku)` sumando cantidades para respetar la restriccion unica de la tabla.

Movimientos de bodega:

- Lee una hoja por dia.
- Descarta hojas/filas de plantilla, saldos y totales.
- Normaliza tipos de movimiento a `IN`, `OUT`, `ADJUSTMENT`.
- Usa `external_key` estable para idempotencia.

Idempotencia:

- Productos y pedidos usan `INSERT ... ON CONFLICT DO UPDATE`.
- Items actualizan cantidad y precio ante conflicto por `(order_id, product_id)`.
- Movimientos actualizan todos sus datos ante conflicto por `external_key`.
- El ultimo stock importado se guarda como `catalog_stock`; una nueva version aplica solo la diferencia entre snapshots. Asi, volver a importar el catalogo no borra pedidos realizados por la API.
- Los movimientos historicos se conservan como libro de auditoria y no vuelven a aplicarse al stock: el snapshot de catalogo ya incorpora actividad de bodega y hacerlo duplicaria movimientos.
- Correr el ETL dos veces no duplica datos.

## Reporte De Negocio

El reporte esta implementado como funcion SQL en PostgreSQL, no como calculo puro de ORM:

```sql
top_selling_products(p_from, p_to, p_limit)
```

Endpoint:

```bash
curl "http://localhost:3000/api/reports/top-products?from=2026-01-01&to=2026-06-30&limit=5" \
  -H "Authorization: Bearer <accessToken>"
```

El KPI entrega:

- SKU y nombre del producto.
- Cantidad vendida.
- Revenue total.
- Cantidad de ordenes.
- Desglose de ordenes `API` vs `ETL`.
- Stock actual.
- Movimiento neto de inventario en el rango.

## Tests

API:

```bash
cd api
npm run build
npm run lint
npm test
npm run test:e2e
```

ETL:

```bash
cd etl
python -m pytest
```

Resultado validado:

```text
36 passed
```

## Decisiones De Diseño

- PostgreSQL es la fuente unica de verdad compartida por API y ETL.
- Prisma se usa para el modelo y migraciones de la API; el ETL usa SQLAlchemy Core con SQL explicito para controlar upserts e idempotencia.
- El SKU se normaliza igual en API y ETL para que ambas fuentes apunten al mismo producto.
- La creacion de pedidos en API usa transaccion para validar stock, crear items, registrar movimiento y descontar inventario atomica y consistentemente.
- La asignacion de `order_number` usa un advisory lock transaccional de PostgreSQL y calcula el maximo numerico, evitando colisiones entre instancias concurrentes.
- El ETL separa readers, cleaners, validators y repositorios para aislar lectura de archivos sucios, reglas de negocio y persistencia.
- El reporte usa una funcion SQL porque el requisito pide procesamiento en PostgreSQL y porque el KPI depende de joins/agregaciones naturales para la base de datos.
- Swagger se agrega como herramienta de evaluacion/manual testing, con bearer JWT configurado.

## Que Haria Distinto Con Mas Tiempo

- Agregar tests e2e de API con una base de datos temporal.
- Agregar Swagger mas detallado con respuestas y ejemplos por endpoint.
- Agregar roles (`admin`, `operator`, `viewer`) sobre JWT.
- Hacer que Docker Compose levante tambien la API y ejecute migraciones automaticamente.
- Crear un job scheduler o contenedor dedicado para ejecutar el ETL periodicamente.
- Guardar auditoria detallada de filas rechazadas por el ETL en una tabla `etl_rejections`.
- Modelar clientes como entidad propia en lugar de string libre en `orders.customer`.
- Mover el reporting a un modelo dimensional si crece el volumen: facturas/fact_order_items, dim_product, dim_customer, dim_date y snapshots de inventario.
- Agregar observabilidad: logs estructurados, metricas de filas procesadas y alertas si sube la tasa de rechazo.

## Comandos Rapidos

```bash
docker compose up -d

cd api
npm install
npx prisma migrate deploy
npm run start:dev

cd ../etl
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python etl.py --dry-run
python etl.py
python -m pytest
```
