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
import * as cdk from 'aws-cdk-lib';

// Networking
import { VpcStack } from '../lib/stacks/networking/vpc-stack';

// Security
import { EncryptionStack } from '../lib/stacks/security/encryption-stack';

// Database
import { DocumentDbStack } from '../lib/stacks/database/documentdb-stack';
import { PostgresStack } from '../lib/stacks/database/postgres-stack';
import { RedisStack } from '../lib/stacks/database/redis-stack';
import { OpenSearchStack } from '../lib/stacks/database/opensearch-stack';

// Compute
import { EcsClusterStack } from '../lib/stacks/compute/ecs-cluster-stack';
import { ChatServiceStack } from '../lib/stacks/compute/services/chat-service-stack';
import { ObserverServiceStack } from '../lib/stacks/compute/services/observer-service-stack';
import { CrisisEngineStack } from '../lib/stacks/compute/services/crisis-engine-stack';
import { SafetyServiceStack } from '../lib/stacks/compute/services/safety-service-stack';

// Compliance
import { AuditStack } from '../lib/stacks/compliance/audit-stack';
import { ConfigRulesStack } from '../lib/stacks/compliance/config-rules-stack';

// Observability
import { DashboardStack } from '../lib/stacks/observability/dashboard-stack';
import { AlarmsStack } from '../lib/stacks/observability/alarms-stack';

// Config
import { productionConfig, devConfig, EnvironmentConfig } from '../lib/config/environments';

const app = new cdk.App();

// Get environment from context (default: dev)
const environmentName = app.node.tryGetContext('environment') || 'dev';
const config: EnvironmentConfig = environmentName === 'production' 
    ? productionConfig 
    : devConfig;

// AWS environment
const env = {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// Stack naming convention: Feelwell-{Domain}-{Environment}
const stackName = (domain: string) => `Feelwell-${domain}-${environmentName}`;

// ============================================================================
// Layer 1: Networking
// ============================================================================
const vpcStack = new VpcStack(app, stackName('Vpc'), {
    env,
    vpcCidr: config.vpcCidr,
    maxAzs: config.maxAzs,
    natGateways: config.natGateways,
    environment: config.environment,
});

// ============================================================================
// Layer 2: Security
// ============================================================================
const encryptionStack = new EncryptionStack(app, stackName('Encryption'), {
    env,
    environment: config.environment,
});

// ============================================================================
// Layer 3: Database
// ============================================================================
const documentDbStack = new DocumentDbStack(app, stackName('DocumentDb'), {
    env,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
});
documentDbStack.addDependency(vpcStack);
documentDbStack.addDependency(encryptionStack);

const postgresStack = new PostgresStack(app, stackName('Postgres'), {
    env,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
});
postgresStack.addDependency(vpcStack);
postgresStack.addDependency(encryptionStack);

const redisStack = new RedisStack(app, stackName('Redis'), {
    env,
    vpc: vpcStack.vpc,
    environment: config.environment,
});
redisStack.addDependency(vpcStack);

const openSearchStack = new OpenSearchStack(app, stackName('OpenSearch'), {
    env,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
});
openSearchStack.addDependency(vpcStack);
openSearchStack.addDependency(encryptionStack);

// ============================================================================
// Layer 4: Compute
// ============================================================================
const ecsClusterStack = new EcsClusterStack(app, stackName('EcsCluster'), {
    env,
    vpc: vpcStack.vpc,
    environment: config.environment,
});
ecsClusterStack.addDependency(vpcStack);

// Crisis Engine first (creates Kinesis stream needed by Safety Service)
const crisisEngineStack = new CrisisEngineStack(app, stackName('CrisisEngine'), {
    env,
    cluster: ecsClusterStack.cluster,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
    config: config.crisisEngine,
});
crisisEngineStack.addDependency(ecsClusterStack);
crisisEngineStack.addDependency(encryptionStack);

// Safety Service (Lambda - needs Crisis Engine stream)
const safetyServiceStack = new SafetyServiceStack(app, stackName('SafetyService'), {
    env,
    environment: config.environment,
    crisisEventStreamArn: crisisEngineStack.eventStream.streamArn,
});
safetyServiceStack.addDependency(crisisEngineStack);

// Chat Service
const chatServiceStack = new ChatServiceStack(app, stackName('ChatService'), {
    env,
    cluster: ecsClusterStack.cluster,
    vpc: vpcStack.vpc,
    environment: config.environment,
    documentDbEndpoint: documentDbStack.cluster.clusterEndpoint.socketAddress,
    redisEndpoint: redisStack.endpoint,
    openSearchEndpoint: openSearchStack.domain.domainEndpoint,
    config: config.chatService,
});
chatServiceStack.addDependency(ecsClusterStack);
chatServiceStack.addDependency(documentDbStack);
chatServiceStack.addDependency(redisStack);
chatServiceStack.addDependency(openSearchStack);

// Observer Service
const observerServiceStack = new ObserverServiceStack(app, stackName('ObserverService'), {
    env,
    cluster: ecsClusterStack.cluster,
    vpc: vpcStack.vpc,
    environment: config.environment,
    postgresEndpoint: postgresStack.instance.dbInstanceEndpointAddress,
    openSearchEndpoint: openSearchStack.domain.domainEndpoint,
    kinesisStreamArn: crisisEngineStack.eventStream.streamArn,
    config: config.observerService,
});
observerServiceStack.addDependency(ecsClusterStack);
observerServiceStack.addDependency(postgresStack);
observerServiceStack.addDependency(openSearchStack);
observerServiceStack.addDependency(crisisEngineStack);

// ============================================================================
// Layer 5: Compliance
// ============================================================================
const auditStack = new AuditStack(app, stackName('Audit'), {
    env,
    kmsKey: encryptionStack.auditKey,
    environment: config.environment,
});
auditStack.addDependency(encryptionStack);

const configRulesStack = new ConfigRulesStack(app, stackName('ConfigRules'), {
    env,
    environment: config.environment,
});

// ============================================================================
// Layer 6: Observability
// ============================================================================
const dashboardStack = new DashboardStack(app, stackName('Dashboards'), {
    env,
    environment: config.environment,
});

const alarmsStack = new AlarmsStack(app, stackName('Alarms'), {
    env,
    environment: config.environment,
    crisisEventStream: crisisEngineStack.eventStream,
    safetyScanner: safetyServiceStack.scannerFunction,
});
alarmsStack.addDependency(crisisEngineStack);
alarmsStack.addDependency(safetyServiceStack);

// ============================================================================
// Global Tagging
// ============================================================================
cdk.Tags.of(app).add('Project', 'Feelwell');
cdk.Tags.of(app).add('Environment', environmentName);
cdk.Tags.of(app).add('ManagedBy', 'CDK');
cdk.Tags.of(app).add('CostCenter', 'Engineering');
