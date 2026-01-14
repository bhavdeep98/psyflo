# Feelwell Infrastructure

AWS CDK infrastructure for the Feelwell mental health platform.

## Architecture

Infrastructure is organized into 5 layers, each deployed as separate CloudFormation stacks:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 5: COMPLIANCE                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ QLDB Audit      │  │ CloudTrail      │  │ Config Rules    │         │
│  │ (ADR-005)       │  │                 │  │ (FERPA/SOC2)    │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 4: COMPUTE                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ Safety Service  │  │ Chat Service    │  │ Observer Service│         │
│  │ (Lambda)        │  │ (Fargate)       │  │ (Fargate)       │         │
│  │ ADR-001         │  │                 │  │                 │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│  ┌─────────────────┐  ┌─────────────────┐                              │
│  │ Crisis Engine   │  │ ECS Cluster     │                              │
│  │ (Fargate+Kinesis)│  │                 │                              │
│  │ ADR-004         │  │                 │                              │
│  └─────────────────┘  └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 3: DATABASE                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ DocumentDB      │  │ PostgreSQL      │  │ Redis           │         │
│  │ (Conversations) │  │ (Clinical Data) │  │ (Session Cache) │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│  ┌─────────────────┐                                                    │
│  │ OpenSearch      │                                                    │
│  │ (RAG/Logs)      │                                                    │
│  └─────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 2: SECURITY                                 │
│  ┌─────────────────┐  ┌─────────────────┐                              │
│  │ Master KMS Key  │  │ Audit KMS Key   │                              │
│  │ (Data at Rest)  │  │ (Audit Logs)    │                              │
│  └─────────────────┘  └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 1: NETWORKING                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ VPC             │  │ Public Subnets  │  │ Private Subnets │         │
│  │ (Multi-AZ)      │  │ (ALB, NAT)      │  │ (App, DB)       │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
infrastructure/
├── bin/
│   └── feelwell.ts              # CDK app entry point
├── lib/
│   ├── config/
│   │   ├── index.ts
│   │   └── environments.ts      # Dev/Production configs
│   └── stacks/
│       ├── networking/
│       │   ├── index.ts
│       │   └── vpc-stack.ts
│       ├── security/
│       │   ├── index.ts
│       │   └── encryption-stack.ts
│       ├── database/
│       │   ├── index.ts
│       │   ├── documentdb-stack.ts
│       │   ├── postgres-stack.ts
│       │   ├── redis-stack.ts
│       │   └── opensearch-stack.ts
│       ├── compute/
│       │   ├── index.ts
│       │   ├── ecs-cluster-stack.ts
│       │   └── services/
│       │       ├── chat-service-stack.ts
│       │       ├── observer-service-stack.ts
│       │       ├── crisis-engine-stack.ts
│       │       └── safety-service-stack.ts
│       └── compliance/
│           ├── index.ts
│           ├── audit-stack.ts
│           └── config-rules-stack.ts
└── cdk.out/                     # Generated CloudFormation templates
```

## Deployment

### Prerequisites

1. AWS CLI configured with appropriate credentials
2. Node.js 18+ and npm
3. CDK CLI: `npm install -g aws-cdk`

### Deploy Development Environment

```bash
cd feelwell/infrastructure
npm install
cdk bootstrap  # First time only
cdk deploy --all --context environment=dev
```

### Deploy Production Environment

```bash
cdk deploy --all --context environment=production
```

### Deploy Specific Stack

```bash
cdk deploy Feelwell-Vpc-dev
cdk deploy Feelwell-CrisisEngine-production
```

## ADR Compliance

| ADR | Implementation |
|-----|----------------|
| ADR-001 | Safety Service (Lambda) runs before LLM, publishes to Kinesis |
| ADR-002 | S3 lifecycle rules: Glacier at 365 days, Deep Archive at 7 years |
| ADR-003 | All services have `LOG_REDACTION_ENABLED=true` |
| ADR-004 | Crisis Engine uses Kinesis stream, decoupled from Chat Service |
| ADR-005 | QLDB ledger with deletion protection, CloudTrail enabled |
| ADR-006 | Implemented in application code (Analytics Service) |

## Cost Estimates

| Environment | Monthly Cost (Estimate) |
|-------------|------------------------|
| Development | ~$500-800 |
| Production | ~$3,000-5,000 |

Major cost drivers:
- NAT Gateways (~$100/month each)
- DocumentDB (~$200-600/month)
- OpenSearch (~$200-800/month)
- Fargate tasks (~$100-500/month)

## Security

- All data encrypted at rest with KMS
- All traffic encrypted in transit (TLS)
- VPC Flow Logs enabled
- CloudTrail for API audit
- AWS Config rules for compliance monitoring
- No public access to databases (isolated subnets)
