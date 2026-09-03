# Order & Inventory Management System

Backend API, data integration and ETL pipeline for a mini order and inventory management system.

## Technologies

* NestJS
* TypeScript
* PostgreSQL
* Prisma
* Python
* Pandas
* SQLAlchemy
* Docker
* JWT

## Project Structure

```text
├── api/       # REST API built with NestJS
├── etl/       # Data integration and ETL pipeline
├── data/      # Input/example datasets
└── docker-compose.yml
```

## Requirements

* Node.js 20+
* npm
* Python 3.11+
* Docker
* Docker Compose

## Getting Started

Instructions will be added as the project components are implemented.

## Architecture

The system consists of a NestJS REST API and a Python ETL pipeline that share the same PostgreSQL database.

```text
                    ┌──────────────┐
                    │   REST API   │
                    │   NestJS     │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ PostgreSQL   │
                    └──────▲───────┘
                           │
                    ┌──────┴───────┐
                    │    ETL       │
                    │   Python     │
                    └──────────────┘
```

## Status

Work in progress.
