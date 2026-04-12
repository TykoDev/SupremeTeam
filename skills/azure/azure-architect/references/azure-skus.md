# Azure SKU Selection Guide

## App Service Plan

| SKU | vCPU | RAM | Use Case |
|-----|------|-----|----------|
| B1 (Basic) | 1 | 1.75 GB | Dev/test, low traffic |
| B2 (Basic) | 2 | 3.5 GB | Small production, moderate traffic |
| S1 (Standard) | 1 | 1.75 GB | Production with auto-scale, slots |
| P1v3 (Premium) | 2 | 8 GB | High traffic, VNet integration |

**Recommendation:** Start with B2 for small production workloads. Move to S1+ when
deployment slots or auto-scaling are needed.

## PostgreSQL Flexible Server

| SKU | vCores | RAM | Use Case |
|-----|--------|-----|----------|
| Burstable B1ms | 1 | 2 GB | Dev/test, light production |
| Burstable B2s | 2 | 4 GB | Small production with burst needs |
| GP D2ds_v5 | 2 | 8 GB | Steady production workloads |
| GP D4ds_v5 | 4 | 16 GB | Medium production, pgvector |

**Storage:** Start at 32 GB (minimum), scale to 128 GB for production with pgvector.
Storage auto-grow is not supported on Burstable -- pre-allocate.

**Extensions for this project:** `vector` (pgvector for embeddings), `pgcrypto` (UUID generation).

## Container Registry

| SKU | Storage | Builds | Replication | Use Case |
|-----|---------|--------|-------------|----------|
| Basic | 10 GB | No | No | Small teams, < 5 images |
| Standard | 100 GB | Yes | No | Medium teams |
| Premium | 500 GB | Yes | Yes | Enterprise, geo-replication |

**Recommendation:** Basic for most projects. Standard when using ACR Tasks for CI builds.

## Key Vault

| SKU | HSM | Price | Use Case |
|-----|-----|-------|----------|
| Standard | Software | Low | Most applications |
| Premium | Hardware | High | Regulatory compliance (FIPS 140-2 L2) |

**Recommendation:** Standard unless regulatory requirements mandate HSM-backed keys.

## Storage Account

| Tier | Redundancy | Use Case |
|------|-----------|----------|
| Standard LRS | Local (3 copies) | Dev, non-critical data |
| Standard ZRS | Zone (3 zones) | Production, regional resilience |
| Standard GRS | Geo (2 regions) | Disaster recovery |

**Recommendation:** LRS for blob attachments and file uploads in small production.
ZRS when SLA requirements exceed 99.9%.
