#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
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
require("source-map-support/register");
const cdk = require("aws-cdk-lib");
// Networking
const vpc_stack_1 = require("../lib/stacks/networking/vpc-stack");
// Security
const encryption_stack_1 = require("../lib/stacks/security/encryption-stack");
// Database
const documentdb_stack_1 = require("../lib/stacks/database/documentdb-stack");
const postgres_stack_1 = require("../lib/stacks/database/postgres-stack");
const redis_stack_1 = require("../lib/stacks/database/redis-stack");
const opensearch_stack_1 = require("../lib/stacks/database/opensearch-stack");
// Compute
const ecs_cluster_stack_1 = require("../lib/stacks/compute/ecs-cluster-stack");
const chat_service_stack_1 = require("../lib/stacks/compute/services/chat-service-stack");
const observer_service_stack_1 = require("../lib/stacks/compute/services/observer-service-stack");
const crisis_engine_stack_1 = require("../lib/stacks/compute/services/crisis-engine-stack");
const safety_service_stack_1 = require("../lib/stacks/compute/services/safety-service-stack");
// Compliance
const audit_stack_1 = require("../lib/stacks/compliance/audit-stack");
const config_rules_stack_1 = require("../lib/stacks/compliance/config-rules-stack");
// Observability
const dashboard_stack_1 = require("../lib/stacks/observability/dashboard-stack");
const alarms_stack_1 = require("../lib/stacks/observability/alarms-stack");
// Config
const environments_1 = require("../lib/config/environments");
const app = new cdk.App();
// Get environment from context (default: dev)
const environmentName = app.node.tryGetContext('environment') || 'dev';
const config = environmentName === 'production'
    ? environments_1.productionConfig
    : environments_1.devConfig;
// AWS environment
const env = {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};
// Stack naming convention: Feelwell-{Domain}-{Environment}
const stackName = (domain) => `Feelwell-${domain}-${environmentName}`;
// ============================================================================
// Layer 1: Networking
// ============================================================================
const vpcStack = new vpc_stack_1.VpcStack(app, stackName('Vpc'), {
    env,
    vpcCidr: config.vpcCidr,
    maxAzs: config.maxAzs,
    natGateways: config.natGateways,
    environment: config.environment,
});
// ============================================================================
// Layer 2: Security
// ============================================================================
const encryptionStack = new encryption_stack_1.EncryptionStack(app, stackName('Encryption'), {
    env,
    environment: config.environment,
});
// ============================================================================
// Layer 3: Database
// ============================================================================
const documentDbStack = new documentdb_stack_1.DocumentDbStack(app, stackName('DocumentDb'), {
    env,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
});
documentDbStack.addDependency(vpcStack);
documentDbStack.addDependency(encryptionStack);
const postgresStack = new postgres_stack_1.PostgresStack(app, stackName('Postgres'), {
    env,
    vpc: vpcStack.vpc,
    kmsKey: encryptionStack.masterKey,
    environment: config.environment,
});
postgresStack.addDependency(vpcStack);
postgresStack.addDependency(encryptionStack);
const redisStack = new redis_stack_1.RedisStack(app, stackName('Redis'), {
    env,
    vpc: vpcStack.vpc,
    environment: config.environment,
});
redisStack.addDependency(vpcStack);
const openSearchStack = new opensearch_stack_1.OpenSearchStack(app, stackName('OpenSearch'), {
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
const ecsClusterStack = new ecs_cluster_stack_1.EcsClusterStack(app, stackName('EcsCluster'), {
    env,
    vpc: vpcStack.vpc,
    environment: config.environment,
});
ecsClusterStack.addDependency(vpcStack);
// Crisis Engine first (creates Kinesis stream needed by Safety Service)
const crisisEngineStack = new crisis_engine_stack_1.CrisisEngineStack(app, stackName('CrisisEngine'), {
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
const safetyServiceStack = new safety_service_stack_1.SafetyServiceStack(app, stackName('SafetyService'), {
    env,
    environment: config.environment,
    crisisEventStreamArn: crisisEngineStack.eventStream.streamArn,
});
safetyServiceStack.addDependency(crisisEngineStack);
// Chat Service
const chatServiceStack = new chat_service_stack_1.ChatServiceStack(app, stackName('ChatService'), {
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
const observerServiceStack = new observer_service_stack_1.ObserverServiceStack(app, stackName('ObserverService'), {
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
const auditStack = new audit_stack_1.AuditStack(app, stackName('Audit'), {
    env,
    kmsKey: encryptionStack.auditKey,
    environment: config.environment,
});
auditStack.addDependency(encryptionStack);
const configRulesStack = new config_rules_stack_1.ConfigRulesStack(app, stackName('ConfigRules'), {
    env,
    environment: config.environment,
});
// ============================================================================
// Layer 6: Observability
// ============================================================================
const dashboardStack = new dashboard_stack_1.DashboardStack(app, stackName('Dashboards'), {
    env,
    environment: config.environment,
});
const alarmsStack = new alarms_stack_1.AlarmsStack(app, stackName('Alarms'), {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmVlbHdlbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmZWVsd2VsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFDQTs7Ozs7Ozs7Ozs7OztHQWFHO0FBQ0gsdUNBQXFDO0FBQ3JDLG1DQUFtQztBQUVuQyxhQUFhO0FBQ2Isa0VBQThEO0FBRTlELFdBQVc7QUFDWCw4RUFBMEU7QUFFMUUsV0FBVztBQUNYLDhFQUEwRTtBQUMxRSwwRUFBc0U7QUFDdEUsb0VBQWdFO0FBQ2hFLDhFQUEwRTtBQUUxRSxVQUFVO0FBQ1YsK0VBQTBFO0FBQzFFLDBGQUFxRjtBQUNyRixrR0FBNkY7QUFDN0YsNEZBQXVGO0FBQ3ZGLDhGQUF5RjtBQUV6RixhQUFhO0FBQ2Isc0VBQWtFO0FBQ2xFLG9GQUErRTtBQUUvRSxnQkFBZ0I7QUFDaEIsaUZBQTZFO0FBQzdFLDJFQUF1RTtBQUV2RSxTQUFTO0FBQ1QsNkRBQTRGO0FBRTVGLE1BQU0sR0FBRyxHQUFHLElBQUksR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDO0FBRTFCLDhDQUE4QztBQUM5QyxNQUFNLGVBQWUsR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDLGFBQWEsQ0FBQyxhQUFhLENBQUMsSUFBSSxLQUFLLENBQUM7QUFDdkUsTUFBTSxNQUFNLEdBQXNCLGVBQWUsS0FBSyxZQUFZO0lBQzlELENBQUMsQ0FBQywrQkFBZ0I7SUFDbEIsQ0FBQyxDQUFDLHdCQUFTLENBQUM7QUFFaEIsa0JBQWtCO0FBQ2xCLE1BQU0sR0FBRyxHQUFHO0lBQ1IsT0FBTyxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsbUJBQW1CO0lBQ3hDLE1BQU0sRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGtCQUFrQixJQUFJLFdBQVc7Q0FDeEQsQ0FBQztBQUVGLDJEQUEyRDtBQUMzRCxNQUFNLFNBQVMsR0FBRyxDQUFDLE1BQWMsRUFBRSxFQUFFLENBQUMsWUFBWSxNQUFNLElBQUksZUFBZSxFQUFFLENBQUM7QUFFOUUsK0VBQStFO0FB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Q0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxZQUFZLEVBQUUsYUFBYSxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyIjIS91c3IvYmluL2VudiBub2RlXG4vKipcbiAqIEZlZWx3ZWxsIENESyBBcHBsaWNhdGlvbiBFbnRyeSBQb2ludC5cbiAqIFxuICogRGVwbG95cyBpbmZyYXN0cnVjdHVyZSBpbiBsYXllcnM6XG4gKiAxLiBOZXR3b3JraW5nIChWUEMsIHN1Ym5ldHMpXG4gKiAyLiBTZWN1cml0eSAoS01TIGVuY3J5cHRpb24pXG4gKiAzLiBEYXRhYmFzZSAoRG9jdW1lbnREQiwgUG9zdGdyZVNRTCwgUmVkaXMsIE9wZW5TZWFyY2gpXG4gKiA0LiBDb21wdXRlIChFQ1MgY2x1c3Rlciwgc2VydmljZXMpXG4gKiA1LiBDb21wbGlhbmNlIChRTERCIGF1ZGl0LCBDbG91ZFRyYWlsLCBDb25maWcgcnVsZXMpXG4gKiBcbiAqIFVzYWdlOlxuICogICBjZGsgZGVwbG95IC0tYWxsIC0tY29udGV4dCBlbnZpcm9ubWVudD1kZXZcbiAqICAgY2RrIGRlcGxveSAtLWFsbCAtLWNvbnRleHQgZW52aXJvbm1lbnQ9cHJvZHVjdGlvblxuICovXG5pbXBvcnQgJ3NvdXJjZS1tYXAtc3VwcG9ydC9yZWdpc3Rlcic7XG5pbXBvcnQgKiBhcyBjZGsgZnJvbSAnYXdzLWNkay1saWInO1xuXG4vLyBOZXR3b3JraW5nXG5pbXBvcnQgeyBWcGNTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvbmV0d29ya2luZy92cGMtc3RhY2snO1xuXG4vLyBTZWN1cml0eVxuaW1wb3J0IHsgRW5jcnlwdGlvblN0YWNrIH0gZnJvbSAnLi4vbGliL3N0YWNrcy9zZWN1cml0eS9lbmNyeXB0aW9uLXN0YWNrJztcblxuLy8gRGF0YWJhc2VcbmltcG9ydCB7IERvY3VtZW50RGJTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvZGF0YWJhc2UvZG9jdW1lbnRkYi1zdGFjayc7XG5pbXBvcnQgeyBQb3N0Z3Jlc1N0YWNrIH0gZnJvbSAnLi4vbGliL3N0YWNrcy9kYXRhYmFzZS9wb3N0Z3Jlcy1zdGFjayc7XG5pbXBvcnQgeyBSZWRpc1N0YWNrIH0gZnJvbSAnLi4vbGliL3N0YWNrcy9kYXRhYmFzZS9yZWRpcy1zdGFjayc7XG5pbXBvcnQgeyBPcGVuU2VhcmNoU3RhY2sgfSBmcm9tICcuLi9saWIvc3RhY2tzL2RhdGFiYXNlL29wZW5zZWFyY2gtc3RhY2snO1xuXG4vLyBDb21wdXRlXG5pbXBvcnQgeyBFY3NDbHVzdGVyU3RhY2sgfSBmcm9tICcuLi9saWIvc3RhY2tzL2NvbXB1dGUvZWNzLWNsdXN0ZXItc3RhY2snO1xuaW1wb3J0IHsgQ2hhdFNlcnZpY2VTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvY29tcHV0ZS9zZXJ2aWNlcy9jaGF0LXNlcnZpY2Utc3RhY2snO1xuaW1wb3J0IHsgT2JzZXJ2ZXJTZXJ2aWNlU3RhY2sgfSBmcm9tICcuLi9saWIvc3RhY2tzL2NvbXB1dGUvc2VydmljZXMvb2JzZXJ2ZXItc2VydmljZS1zdGFjayc7XG5pbXBvcnQgeyBDcmlzaXNFbmdpbmVTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvY29tcHV0ZS9zZXJ2aWNlcy9jcmlzaXMtZW5naW5lLXN0YWNrJztcbmltcG9ydCB7IFNhZmV0eVNlcnZpY2VTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvY29tcHV0ZS9zZXJ2aWNlcy9zYWZldHktc2VydmljZS1zdGFjayc7XG5cbi8vIENvbXBsaWFuY2VcbmltcG9ydCB7IEF1ZGl0U3RhY2sgfSBmcm9tICcuLi9saWIvc3RhY2tzL2NvbXBsaWFuY2UvYXVkaXQtc3RhY2snO1xuaW1wb3J0IHsgQ29uZmlnUnVsZXNTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3MvY29tcGxpYW5jZS9jb25maWctcnVsZXMtc3RhY2snO1xuXG4vLyBPYnNlcnZhYmlsaXR5XG5pbXBvcnQgeyBEYXNoYm9hcmRTdGFjayB9IGZyb20gJy4uL2xpYi9zdGFja3Mvb2JzZXJ2YWJpbGl0eS9kYXNoYm9hcmQtc3RhY2snO1xuaW1wb3J0IHsgQWxhcm1zU3RhY2sgfSBmcm9tICcuLi9saWIvc3RhY2tzL29ic2VydmFiaWxpdHkvYWxhcm1zLXN0YWNrJztcblxuLy8gQ29uZmlnXG5pbXBvcnQgeyBwcm9kdWN0aW9uQ29uZmlnLCBkZXZDb25maWcsIEVudmlyb25tZW50Q29uZmlnIH0gZnJvbSAnLi4vbGliL2NvbmZpZy9lbnZpcm9ubWVudHMnO1xuXG5jb25zdCBhcHAgPSBuZXcgY2RrLkFwcCgpO1xuXG4vLyBHZXQgZW52aXJvbm1lbnQgZnJvbSBjb250ZXh0IChkZWZhdWx0OiBkZXYpXG5jb25zdCBlbnZpcm9ubWVudE5hbWUgPSBhcHAubm9kZS50cnlHZXRDb250ZXh0KCdlbnZpcm9ubWVudCcpIHx8ICdkZXYnO1xuY29uc3QgY29uZmlnOiBFbnZpcm9ubWVudENvbmZpZyA9IGVudmlyb25tZW50TmFtZSA9PT0gJ3Byb2R1Y3Rpb24nIFxuICAgID8gcHJvZHVjdGlvbkNvbmZpZyBcbiAgICA6IGRldkNvbmZpZztcblxuLy8gQVdTIGVudmlyb25tZW50XG5jb25zdCBlbnYgPSB7XG4gICAgYWNjb3VudDogcHJvY2Vzcy5lbnYuQ0RLX0RFRkFVTFRfQUNDT1VOVCxcbiAgICByZWdpb246IHByb2Nlc3MuZW52LkNES19ERUZBVUxUX1JFR0lPTiB8fCAndXMtZWFzdC0xJyxcbn07XG5cbi8vIFN0YWNrIG5hbWluZyBjb252ZW50aW9uOiBGZWVsd2VsbC17RG9tYWlufS17RW52aXJvbm1lbnR9XG5jb25zdCBzdGFja05hbWUgPSAoZG9tYWluOiBzdHJpbmcpID0+IGBGZWVsd2VsbC0ke2RvbWFpbn0tJHtlbnZpcm9ubWVudE5hbWV9YDtcblxuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuLy8gTGF5ZXIgMTogTmV0d29ya2luZ1xuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuY29uc3QgdnBjU3RhY2sgPSBuZXcgVnBjU3RhY2soYXBwLCBzdGFja05hbWUoJ1ZwYycpLCB7XG4gICAgZW52LFxuICAgIHZwY0NpZHI6IGNvbmZpZy52cGNDaWRyLFxuICAgIG1heEF6czogY29uZmlnLm1heEF6cyxcbiAgICBuYXRHYXRld2F5czogY29uZmlnLm5hdEdhdGV3YXlzLFxuICAgIGVudmlyb25tZW50OiBjb25maWcuZW52aXJvbm1lbnQsXG59KTtcblxuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuLy8gTGF5ZXIgMjogU2VjdXJpdHlcbi8vID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT1cbmNvbnN0IGVuY3J5cHRpb25TdGFjayA9IG5ldyBFbmNyeXB0aW9uU3RhY2soYXBwLCBzdGFja05hbWUoJ0VuY3J5cHRpb24nKSwge1xuICAgIGVudixcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxufSk7XG5cbi8vID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT1cbi8vIExheWVyIDM6IERhdGFiYXNlXG4vLyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09XG5jb25zdCBkb2N1bWVudERiU3RhY2sgPSBuZXcgRG9jdW1lbnREYlN0YWNrKGFwcCwgc3RhY2tOYW1lKCdEb2N1bWVudERiJyksIHtcbiAgICBlbnYsXG4gICAgdnBjOiB2cGNTdGFjay52cGMsXG4gICAga21zS2V5OiBlbmNyeXB0aW9uU3RhY2subWFzdGVyS2V5LFxuICAgIGVudmlyb25tZW50OiBjb25maWcuZW52aXJvbm1lbnQsXG59KTtcbmRvY3VtZW50RGJTdGFjay5hZGREZXBlbmRlbmN5KHZwY1N0YWNrKTtcbmRvY3VtZW50RGJTdGFjay5hZGREZXBlbmRlbmN5KGVuY3J5cHRpb25TdGFjayk7XG5cbmNvbnN0IHBvc3RncmVzU3RhY2sgPSBuZXcgUG9zdGdyZXNTdGFjayhhcHAsIHN0YWNrTmFtZSgnUG9zdGdyZXMnKSwge1xuICAgIGVudixcbiAgICB2cGM6IHZwY1N0YWNrLnZwYyxcbiAgICBrbXNLZXk6IGVuY3J5cHRpb25TdGFjay5tYXN0ZXJLZXksXG4gICAgZW52aXJvbm1lbnQ6IGNvbmZpZy5lbnZpcm9ubWVudCxcbn0pO1xucG9zdGdyZXNTdGFjay5hZGREZXBlbmRlbmN5KHZwY1N0YWNrKTtcbnBvc3RncmVzU3RhY2suYWRkRGVwZW5kZW5jeShlbmNyeXB0aW9uU3RhY2spO1xuXG5jb25zdCByZWRpc1N0YWNrID0gbmV3IFJlZGlzU3RhY2soYXBwLCBzdGFja05hbWUoJ1JlZGlzJyksIHtcbiAgICBlbnYsXG4gICAgdnBjOiB2cGNTdGFjay52cGMsXG4gICAgZW52aXJvbm1lbnQ6IGNvbmZpZy5lbnZpcm9ubWVudCxcbn0pO1xucmVkaXNTdGFjay5hZGREZXBlbmRlbmN5KHZwY1N0YWNrKTtcblxuY29uc3Qgb3BlblNlYXJjaFN0YWNrID0gbmV3IE9wZW5TZWFyY2hTdGFjayhhcHAsIHN0YWNrTmFtZSgnT3BlblNlYXJjaCcpLCB7XG4gICAgZW52LFxuICAgIHZwYzogdnBjU3RhY2sudnBjLFxuICAgIGttc0tleTogZW5jcnlwdGlvblN0YWNrLm1hc3RlcktleSxcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxufSk7XG5vcGVuU2VhcmNoU3RhY2suYWRkRGVwZW5kZW5jeSh2cGNTdGFjayk7XG5vcGVuU2VhcmNoU3RhY2suYWRkRGVwZW5kZW5jeShlbmNyeXB0aW9uU3RhY2spO1xuXG4vLyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09XG4vLyBMYXllciA0OiBDb21wdXRlXG4vLyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09XG5jb25zdCBlY3NDbHVzdGVyU3RhY2sgPSBuZXcgRWNzQ2x1c3RlclN0YWNrKGFwcCwgc3RhY2tOYW1lKCdFY3NDbHVzdGVyJyksIHtcbiAgICBlbnYsXG4gICAgdnBjOiB2cGNTdGFjay52cGMsXG4gICAgZW52aXJvbm1lbnQ6IGNvbmZpZy5lbnZpcm9ubWVudCxcbn0pO1xuZWNzQ2x1c3RlclN0YWNrLmFkZERlcGVuZGVuY3kodnBjU3RhY2spO1xuXG4vLyBDcmlzaXMgRW5naW5lIGZpcnN0IChjcmVhdGVzIEtpbmVzaXMgc3RyZWFtIG5lZWRlZCBieSBTYWZldHkgU2VydmljZSlcbmNvbnN0IGNyaXNpc0VuZ2luZVN0YWNrID0gbmV3IENyaXNpc0VuZ2luZVN0YWNrKGFwcCwgc3RhY2tOYW1lKCdDcmlzaXNFbmdpbmUnKSwge1xuICAgIGVudixcbiAgICBjbHVzdGVyOiBlY3NDbHVzdGVyU3RhY2suY2x1c3RlcixcbiAgICB2cGM6IHZwY1N0YWNrLnZwYyxcbiAgICBrbXNLZXk6IGVuY3J5cHRpb25TdGFjay5tYXN0ZXJLZXksXG4gICAgZW52aXJvbm1lbnQ6IGNvbmZpZy5lbnZpcm9ubWVudCxcbiAgICBjb25maWc6IGNvbmZpZy5jcmlzaXNFbmdpbmUsXG59KTtcbmNyaXNpc0VuZ2luZVN0YWNrLmFkZERlcGVuZGVuY3koZWNzQ2x1c3RlclN0YWNrKTtcbmNyaXNpc0VuZ2luZVN0YWNrLmFkZERlcGVuZGVuY3koZW5jcnlwdGlvblN0YWNrKTtcblxuLy8gU2FmZXR5IFNlcnZpY2UgKExhbWJkYSAtIG5lZWRzIENyaXNpcyBFbmdpbmUgc3RyZWFtKVxuY29uc3Qgc2FmZXR5U2VydmljZVN0YWNrID0gbmV3IFNhZmV0eVNlcnZpY2VTdGFjayhhcHAsIHN0YWNrTmFtZSgnU2FmZXR5U2VydmljZScpLCB7XG4gICAgZW52LFxuICAgIGVudmlyb25tZW50OiBjb25maWcuZW52aXJvbm1lbnQsXG4gICAgY3Jpc2lzRXZlbnRTdHJlYW1Bcm46IGNyaXNpc0VuZ2luZVN0YWNrLmV2ZW50U3RyZWFtLnN0cmVhbUFybixcbn0pO1xuc2FmZXR5U2VydmljZVN0YWNrLmFkZERlcGVuZGVuY3koY3Jpc2lzRW5naW5lU3RhY2spO1xuXG4vLyBDaGF0IFNlcnZpY2VcbmNvbnN0IGNoYXRTZXJ2aWNlU3RhY2sgPSBuZXcgQ2hhdFNlcnZpY2VTdGFjayhhcHAsIHN0YWNrTmFtZSgnQ2hhdFNlcnZpY2UnKSwge1xuICAgIGVudixcbiAgICBjbHVzdGVyOiBlY3NDbHVzdGVyU3RhY2suY2x1c3RlcixcbiAgICB2cGM6IHZwY1N0YWNrLnZwYyxcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxuICAgIGRvY3VtZW50RGJFbmRwb2ludDogZG9jdW1lbnREYlN0YWNrLmNsdXN0ZXIuY2x1c3RlckVuZHBvaW50LnNvY2tldEFkZHJlc3MsXG4gICAgcmVkaXNFbmRwb2ludDogcmVkaXNTdGFjay5lbmRwb2ludCxcbiAgICBvcGVuU2VhcmNoRW5kcG9pbnQ6IG9wZW5TZWFyY2hTdGFjay5kb21haW4uZG9tYWluRW5kcG9pbnQsXG4gICAgY29uZmlnOiBjb25maWcuY2hhdFNlcnZpY2UsXG59KTtcbmNoYXRTZXJ2aWNlU3RhY2suYWRkRGVwZW5kZW5jeShlY3NDbHVzdGVyU3RhY2spO1xuY2hhdFNlcnZpY2VTdGFjay5hZGREZXBlbmRlbmN5KGRvY3VtZW50RGJTdGFjayk7XG5jaGF0U2VydmljZVN0YWNrLmFkZERlcGVuZGVuY3kocmVkaXNTdGFjayk7XG5jaGF0U2VydmljZVN0YWNrLmFkZERlcGVuZGVuY3kob3BlblNlYXJjaFN0YWNrKTtcblxuLy8gT2JzZXJ2ZXIgU2VydmljZVxuY29uc3Qgb2JzZXJ2ZXJTZXJ2aWNlU3RhY2sgPSBuZXcgT2JzZXJ2ZXJTZXJ2aWNlU3RhY2soYXBwLCBzdGFja05hbWUoJ09ic2VydmVyU2VydmljZScpLCB7XG4gICAgZW52LFxuICAgIGNsdXN0ZXI6IGVjc0NsdXN0ZXJTdGFjay5jbHVzdGVyLFxuICAgIHZwYzogdnBjU3RhY2sudnBjLFxuICAgIGVudmlyb25tZW50OiBjb25maWcuZW52aXJvbm1lbnQsXG4gICAgcG9zdGdyZXNFbmRwb2ludDogcG9zdGdyZXNTdGFjay5pbnN0YW5jZS5kYkluc3RhbmNlRW5kcG9pbnRBZGRyZXNzLFxuICAgIG9wZW5TZWFyY2hFbmRwb2ludDogb3BlblNlYXJjaFN0YWNrLmRvbWFpbi5kb21haW5FbmRwb2ludCxcbiAgICBraW5lc2lzU3RyZWFtQXJuOiBjcmlzaXNFbmdpbmVTdGFjay5ldmVudFN0cmVhbS5zdHJlYW1Bcm4sXG4gICAgY29uZmlnOiBjb25maWcub2JzZXJ2ZXJTZXJ2aWNlLFxufSk7XG5vYnNlcnZlclNlcnZpY2VTdGFjay5hZGREZXBlbmRlbmN5KGVjc0NsdXN0ZXJTdGFjayk7XG5vYnNlcnZlclNlcnZpY2VTdGFjay5hZGREZXBlbmRlbmN5KHBvc3RncmVzU3RhY2spO1xub2JzZXJ2ZXJTZXJ2aWNlU3RhY2suYWRkRGVwZW5kZW5jeShvcGVuU2VhcmNoU3RhY2spO1xub2JzZXJ2ZXJTZXJ2aWNlU3RhY2suYWRkRGVwZW5kZW5jeShjcmlzaXNFbmdpbmVTdGFjayk7XG5cbi8vID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT1cbi8vIExheWVyIDU6IENvbXBsaWFuY2Vcbi8vID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT1cbmNvbnN0IGF1ZGl0U3RhY2sgPSBuZXcgQXVkaXRTdGFjayhhcHAsIHN0YWNrTmFtZSgnQXVkaXQnKSwge1xuICAgIGVudixcbiAgICBrbXNLZXk6IGVuY3J5cHRpb25TdGFjay5hdWRpdEtleSxcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxufSk7XG5hdWRpdFN0YWNrLmFkZERlcGVuZGVuY3koZW5jcnlwdGlvblN0YWNrKTtcblxuY29uc3QgY29uZmlnUnVsZXNTdGFjayA9IG5ldyBDb25maWdSdWxlc1N0YWNrKGFwcCwgc3RhY2tOYW1lKCdDb25maWdSdWxlcycpLCB7XG4gICAgZW52LFxuICAgIGVudmlyb25tZW50OiBjb25maWcuZW52aXJvbm1lbnQsXG59KTtcblxuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuLy8gTGF5ZXIgNjogT2JzZXJ2YWJpbGl0eVxuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuY29uc3QgZGFzaGJvYXJkU3RhY2sgPSBuZXcgRGFzaGJvYXJkU3RhY2soYXBwLCBzdGFja05hbWUoJ0Rhc2hib2FyZHMnKSwge1xuICAgIGVudixcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxufSk7XG5cbmNvbnN0IGFsYXJtc1N0YWNrID0gbmV3IEFsYXJtc1N0YWNrKGFwcCwgc3RhY2tOYW1lKCdBbGFybXMnKSwge1xuICAgIGVudixcbiAgICBlbnZpcm9ubWVudDogY29uZmlnLmVudmlyb25tZW50LFxuICAgIGNyaXNpc0V2ZW50U3RyZWFtOiBjcmlzaXNFbmdpbmVTdGFjay5ldmVudFN0cmVhbSxcbiAgICBzYWZldHlTY2FubmVyOiBzYWZldHlTZXJ2aWNlU3RhY2suc2Nhbm5lckZ1bmN0aW9uLFxufSk7XG5hbGFybXNTdGFjay5hZGREZXBlbmRlbmN5KGNyaXNpc0VuZ2luZVN0YWNrKTtcbmFsYXJtc1N0YWNrLmFkZERlcGVuZGVuY3koc2FmZXR5U2VydmljZVN0YWNrKTtcblxuLy8gPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PVxuLy8gR2xvYmFsIFRhZ2dpbmdcbi8vID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT1cbmNkay5UYWdzLm9mKGFwcCkuYWRkKCdQcm9qZWN0JywgJ0ZlZWx3ZWxsJyk7XG5jZGsuVGFncy5vZihhcHApLmFkZCgnRW52aXJvbm1lbnQnLCBlbnZpcm9ubWVudE5hbWUpO1xuY2RrLlRhZ3Mub2YoYXBwKS5hZGQoJ01hbmFnZWRCeScsICdDREsnKTtcbmNkay5UYWdzLm9mKGFwcCkuYWRkKCdDb3N0Q2VudGVyJywgJ0VuZ2luZWVyaW5nJyk7XG4iXX0=