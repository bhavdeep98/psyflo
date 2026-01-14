#!/usr/bin/env node
/**
 * Feelwell CDK Application Entry Point.
 *
 * Deploys infrastructure in layers:
 * 1. Networking (VPC, subnets)
 * 2. Security (KMS encryption)
 * 3. Database (DocumentDB, PostgreSQL, Redis, OpenSearch)
 * 4. Compute (ECS cluster, services)
 * 5. Compliance (QLDB audit, CloudTrail, Config rules)
 *
 * Usage:
 *   cdk deploy --all --context environment=dev
 *   cdk deploy --all --context environment=production
 */
import 'source-map-support/register';
