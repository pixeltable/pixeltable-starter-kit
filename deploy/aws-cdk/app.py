"""AWS CDK stack: deploys the Pixeltable App Template on ECS Fargate."""

import os

from aws_cdk import (
    App,
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_efs as efs,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from dotenv import load_dotenv

load_dotenv()


class PixeltableAppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Secrets ──────────────────────────────────────────────────────
        secret = secretsmanager.Secret(
            self,
            "ApiSecrets",
            secret_name="pixeltable-app/api-keys",
            secret_object_value={
                "ANTHROPIC_API_KEY": SecretValue.unsafe_plain_text(
                    os.getenv("ANTHROPIC_API_KEY", "")
                ),
                "OPENAI_API_KEY": SecretValue.unsafe_plain_text(
                    os.getenv("OPENAI_API_KEY", "")
                ),
            },
        )

        # ── VPC ──────────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # ── EFS for Pixeltable persistent storage ────────────────────────
        file_system = efs.FileSystem(
            self,
            "PixeltableData",
            vpc=vpc,
            removal_policy=RemovalPolicy.RETAIN,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.ELASTIC,
        )

        efs_access_point = file_system.add_access_point(
            "AccessPoint",
            path="/pixeltable",
            create_acl=efs.Acl(owner_uid="1000", owner_gid="1000", permissions="755"),
            posix_user=efs.PosixUser(uid="1000", gid="1000"),
        )

        # ── ECS Cluster ──────────────────────────────────────────────────
        cluster = ecs.Cluster(
            self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.ENABLED
        )

        # ── Docker image (built from repo root) ─────────────────────────
        image = ecr_assets.DockerImageAsset(
            self,
            "AppImage",
            directory="../../",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        # ── CloudWatch logs ──────────────────────────────────────────────
        log_group = logs.LogGroup(
            self, "Logs", retention=logs.RetentionDays.TWO_WEEKS
        )

        # ── Task definition (with EFS volume) ────────────────────────────
        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=4096,
            memory_limit_mib=8192,
        )

        task_def.add_volume(
            name="pixeltable-data",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=efs_access_point.access_point_id,
                    iam="ENABLED",
                ),
            ),
        )

        container = task_def.add_container(
            "App",
            image=ecs.ContainerImage.from_docker_image_asset(image),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="pixeltable-app", log_group=log_group
            ),
            secrets={
                "ANTHROPIC_API_KEY": ecs.Secret.from_secrets_manager(
                    secret, "ANTHROPIC_API_KEY"
                ),
                "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(
                    secret, "OPENAI_API_KEY"
                ),
            },
            environment={
                "PIXELTABLE_HOME": "/data/pixeltable",
                "CORS_ORIGINS": "*",
            },
        )

        container.add_port_mappings(ecs.PortMapping(container_port=8000))
        container.add_mount_points(
            ecs.MountPoint(
                container_path="/data/pixeltable",
                source_volume="pixeltable-data",
                read_only=False,
            )
        )

        # ── Fargate service + ALB ────────────────────────────────────────
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            platform_version=ecs.FargatePlatformVersion.VERSION1_4,
        )

        # Allow EFS access from Fargate tasks
        file_system.connections.allow_default_port_from(
            fargate_service.service.connections
        )
        file_system.grant_root_access(task_def.task_role)

        # Health check
        fargate_service.target_group.configure_health_check(
            path="/api/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
        )

        # Auto-scaling
        scaling = fargate_service.service.auto_scale_task_count(
            min_capacity=1, max_capacity=4
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # ── Outputs ──────────────────────────────────────────────────────
        CfnOutput(
            self,
            "AppUrl",
            value=f"http://{fargate_service.load_balancer.load_balancer_dns_name}",
            description="Application URL",
        )


app = App()
PixeltableAppStack(app, "PixeltableAppStack")
app.synth()
