/**
 * Safety Service Stack - Layer 1 deterministic guardrails.
 * 
 * CRITICAL SERVICE - First line of defense for student safety.
 * 
 * Responsibilities:
 * - Receive messages from Chat Service for safety scanning
 * - Detect crisis keywords and patterns (ADR-001)
 * - Bypass LLM entirely for high-risk inputs
 * - Publish crisis events to Kinesis (ADR-004)
 * 
 * Architecture:
 * - Internal ALB (not internet-facing)
 * - Always runs 2+ instances for HA
 * - Sub-50ms p99 latency target
 * - Publishes to Crisis Engine's Kinesis stream
 * 
 * @see ADR-001 for deterministic guardrail implementation
 * @see ADR-003 for zero PII in logs
 * @see ADR-004 for event-driven crisis response
 */
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kinesis from 'aws-cdk-lib/aws-kinesis';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as path from 'path';
import { Construct } from 'constructs';

export interface SafetyServiceStackProps extends cdk.StackProps {
    /** ECS cluster */
    cluster: ecs.ICluster;
    /** VPC for service placement */
    vpc: ec2.IVpc;
    /** Crisis events Kinesis stream (from CrisisEngineStack) */
    crisisEventStream: kinesis.IStream;
    /** Environment identifier */
    environment: 'dev' | 'production';
    /** PII hash salt (from Secrets Manager in production) */
    piiHashSalt?: string;
    /** Service configuration */
    config: {
        cpu: number;
        memory: number;
        desiredCount: number;
        minCapacity: number;
        maxCapacity: number;
    };
}

export class SafetyServiceStack extends cdk.Stack {
    /** Fargate service */
    public readonly service: ecs.FargateService;
    /** Internal Application Load Balancer */
    public readonly loadBalancer: elbv2.ApplicationLoadBalancer;
    /** Service URL for other services to call */
    public readonly serviceUrl: string;
    /** Security group */
    public readonly securityGroup: ec2.SecurityGroup;

    constructor(scope: Construct, id: string, props: SafetyServiceStackProps) {
        super(scope, id, props);

        const { cluster, vpc, crisisEventStream, environment, config } = props;
        const isProduction = environment === 'production';

        // Security group - internal only
        this.securityGroup = new ec2.SecurityGroup(this, 'SecurityGroup', {
            vpc,
            description: 'Safety Service security group - CRITICAL SERVICE',
            allowAllOutbound: true,
        });

        // Task definition
        const taskDef = new ecs.FargateTaskDefinition(this, 'TaskDef', {
            cpu: config.cpu,
            memoryLimitMiB: config.memory,
            runtimePlatform: {
                cpuArchitecture: ecs.CpuArchitecture.ARM64, // Graviton2 for cost
                operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
            },
        });

        // Grant Kinesis write access for crisis event publishing (ADR-004)
        crisisEventStream.grantWrite(taskDef.taskRole);

        // Container
        const servicePath = path.join(__dirname, '../../../../../services/safety_service');
        const container = taskDef.addContainer('SafetyService', {
            image: ecs.ContainerImage.fromAsset(servicePath),
            environment: {
                ENVIRONMENT: environment,
                SERVICE_NAME: 'safety-service',
                PORT: '8001',
                KINESIS_STREAM_NAME: crisisEventStream.streamName,
                CRISIS_PUBLISHING_ENABLED: 'true',
                BERT_SCANNER_ENABLED: 'false', // Enable when ML layer ready
                LOG_REDACTION_ENABLED: 'true', // ADR-003
                PATTERN_VERSION: '2026.01.14',
                // PII salt should come from Secrets Manager in production
                PII_HASH_SALT: props.piiHashSalt || 'dev_salt_change_in_production_minimum_32_characters',
            },
            logging: ecs.LogDrivers.awsLogs({
                streamPrefix: 'safety-service',
                logRetention: isProduction
                    ? logs.RetentionDays.ONE_YEAR  // Longer for safety-critical
                    : logs.RetentionDays.ONE_WEEK,
            }),
            healthCheck: {
                command: ['CMD-SHELL', 'curl -f http://localhost:8001/health || exit 1'],
                interval: cdk.Duration.seconds(15), // Frequent checks for critical service
                timeout: cdk.Duration.seconds(5),
                retries: 2,
                startPeriod: cdk.Duration.seconds(30),
            },
        });

        container.addPortMappings({ containerPort: 8001 });

        // Fargate service - ALWAYS 2+ instances for HA
        this.service = new ecs.FargateService(this, 'Service', {
            cluster,
            taskDefinition: taskDef,
            desiredCount: Math.max(config.desiredCount, 2), // NEVER less than 2
            securityGroups: [this.securityGroup],
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            circuitBreaker: { rollback: true },
            enableExecuteCommand: true,
            cloudMapOptions: {
                name: 'safety',
            },
        });

        // Auto-scaling with minimum 2 instances
        const scaling = this.service.autoScaleTaskCount({
            minCapacity: Math.max(config.minCapacity, 2), // NEVER below 2
            maxCapacity: config.maxCapacity,
        });

        scaling.scaleOnCpuUtilization('CpuScaling', {
            targetUtilizationPercent: 60, // Scale earlier for safety-critical
            scaleInCooldown: cdk.Duration.minutes(5),
            scaleOutCooldown: cdk.Duration.seconds(30), // Scale out fast
        });

        // Internal Application Load Balancer
        this.loadBalancer = new elbv2.ApplicationLoadBalancer(this, 'ALB', {
            vpc,
            internetFacing: false, // Internal only
            securityGroup: this.securityGroup,
        });

        const listener = this.loadBalancer.addListener('Listener', {
            port: 80,
            protocol: elbv2.ApplicationProtocol.HTTP,
        });

        listener.addTargets('SafetyTargets', {
            port: 8001,
            protocol: elbv2.ApplicationProtocol.HTTP,
            targets: [this.service],
            healthCheck: {
                path: '/health',
                interval: cdk.Duration.seconds(15),
                healthyThresholdCount: 2,
                unhealthyThresholdCount: 2,
                timeout: cdk.Duration.seconds(5),
            },
            deregistrationDelay: cdk.Duration.seconds(30),
        });

        this.serviceUrl = `http://${this.loadBalancer.loadBalancerDnsName}`;

        // CloudWatch Alarms - CRITICAL SERVICE MONITORING
        
        // Alarm: High latency (safety scans must be fast)
        new cloudwatch.Alarm(this, 'HighLatencyAlarm', {
            metric: this.loadBalancer.metrics.targetResponseTime({
                statistic: 'p99',
            }),
            threshold: 0.05, // 50ms p99 target
            evaluationPeriods: 3,
            datapointsToAlarm: 2,
            alarmDescription: 'CRITICAL: Safety service p99 latency > 50ms',
            treatMissingData: cloudwatch.TreatMissingData.BREACHING,
        });

        // Alarm: Unhealthy hosts
        new cloudwatch.Alarm(this, 'UnhealthyHostsAlarm', {
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'UnHealthyHostCount',
                dimensionsMap: {
                    LoadBalancer: this.loadBalancer.loadBalancerFullName,
                },
                statistic: 'Average',
                period: cdk.Duration.minutes(1),
            }),
            threshold: 1,
            evaluationPeriods: 1,
            alarmDescription: 'CRITICAL: Safety service has unhealthy hosts',
            treatMissingData: cloudwatch.TreatMissingData.BREACHING,
        });

        // Alarm: High error rate
        new cloudwatch.Alarm(this, 'HighErrorRateAlarm', {
            metric: this.loadBalancer.metrics.httpCodeTarget(
                elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
                { statistic: 'Sum', period: cdk.Duration.minutes(1) }
            ),
            threshold: 5,
            evaluationPeriods: 2,
            alarmDescription: 'CRITICAL: Safety service 5xx errors > 5/min',
        });

        // Alarm: Service CPU high
        new cloudwatch.Alarm(this, 'HighCpuAlarm', {
            metric: this.service.metricCpuUtilization(),
            threshold: 80,
            evaluationPeriods: 3,
            alarmDescription: 'Safety service CPU > 80%',
        });

        // Tagging - Critical service markers
        cdk.Tags.of(this.service).add('Service', 'safety-service');
        cdk.Tags.of(this.service).add('CriticalService', 'true');
        cdk.Tags.of(this.service).add('SLO', '99.99-availability');
        cdk.Tags.of(this.service).add('Compliance', 'FERPA-COPPA');
        cdk.Tags.of(this.service).add('ADR', 'ADR-001');

        // Outputs
        new cdk.CfnOutput(this, 'ServiceUrl', {
            value: this.serviceUrl,
            description: 'Safety Service internal URL',
            exportName: `${environment}-SafetyServiceUrl`,
        });

        new cdk.CfnOutput(this, 'LoadBalancerArn', {
            value: this.loadBalancer.loadBalancerArn,
            description: 'Safety Service ALB ARN',
            exportName: `${environment}-SafetyServiceAlbArn`,
        });
    }
}
