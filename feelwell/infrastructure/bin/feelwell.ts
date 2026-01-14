#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkingStack } from '../lib/stacks/networking-stack';
import { SecurityStack } from '../lib/stacks/security-stack';
import { DatabaseStack } from '../lib/stacks/database-stack';
import { ComputeStack } from '../lib/stacks/compute-stack';
import { ComplianceStack } from '../lib/stacks/compliance-stack';
import { productionConfig, devConfig } from '../lib/config';

const app = new cdk.App();

// Get environment from context
const environment = app.node.tryGetContext('environment') || 'dev';
const config = environment === 'production' ? productionConfig : devConfig;

// Define environment (Region fixed for cost estimate consistency)
const env = {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1',
};

// 1. Networking Layer
const networkingStack = new NetworkingStack(app, `Feelwell-Networking-${environment}`, {
    env,
    vpcCidr: config.vpcCidr ?? '10.0.0.0/16', // Fallback for dev reuse
    maxAzs: config.maxAzs ?? 2,
    natGateways: config.natGateways,
});

// 2. Security Layer
const securityStack = new SecurityStack(app, `Feelwell-Security-${environment}`, {
    env,
    vpc: networkingStack.vpc,
});

// 3. Data Layer
const databaseStack = new DatabaseStack(app, `Feelwell-Database-${environment}`, {
    env,
    vpc: networkingStack.vpc,
    kmsKey: securityStack.kmsKey,
    environment: config.environment,
});

// 4. Compute Layer
const computeStack = new ComputeStack(app, `Feelwell-Compute-${environment}`, {
    env,
    vpc: networkingStack.vpc,
    databases: databaseStack,
    environment: config.environment,
    chatServiceConfig: config.chatService,
    observerServiceConfig: config.observerService,
    crisisEngineConfig: config.crisisEngine,
});

// 5. Compliance Layer
const complianceStack = new ComplianceStack(app, `Feelwell-Compliance-${environment}`, {
    env,
    environment: config.environment,
});

// Global Tagging
cdk.Tags.of(app).add('Project', 'Feelwell');
cdk.Tags.of(app).add('Environment', environment);
cdk.Tags.of(app).add('ManagedBy', 'CDK');
cdk.Tags.of(app).add('CostCenter', 'Engineering');
