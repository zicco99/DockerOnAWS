from aws_cdk import (
    CfnOutput,
    Stack,
    RemovalPolicy,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_s3_deployment as s3_deployment,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct

class AppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, repository_name: str, stage: str, image_tag: str, push_image: bool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #-----------------
        #   Setup  -
        #-----------------

        #VPC with 2 AZs
        main_vpc = ec2.Vpc(self, f"{repository_name}-{stage}-vpc", max_azs=2)

        # Define ECR Repository
        docker_repository = ecr.Repository(self, f"{repository_name}-{stage}-docker-repository",
            repository_name=f"{repository_name}-{stage}",
            removal_policy=RemovalPolicy.DESTROY
        )

        self.ecr_repository = docker_repository

        #-----------------
        #   Dockerizing  -
        #-----------------
        # Setting up the codebuild project to build the Docker image

        IMAGE_TAG = image_tag + "-" + stage

        source_bucket = s3.Bucket(self, f"{repository_name}-{stage}-source-bucket",
            bucket_name=f"{repository_name}-{stage}-source-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # CodeBuild project to build Docker images
        build_project = codebuild.Project(self, f"{repository_name}-{stage}-microservice-build-project",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,  # Required to build Docker images
                environment_variables={
                    'AWS_ACCOUNT_ID': codebuild.BuildEnvironmentVariable(value=self.account),
                    'AWS_DEFAULT_REGION': codebuild.BuildEnvironmentVariable(value=self.region),
                    'REPOSITORY_URI': codebuild.BuildEnvironmentVariable(value=docker_repository.repository_uri),
                    'IMAGE_TAG': codebuild.BuildEnvironmentVariable(value=IMAGE_TAG)
                }
            ),
            source=codebuild.Source.s3(
                bucket=source_bucket,
                path="microservice/"  # Path within the S3 bucket where the source code is stored
            ),
            build_spec=codebuild.BuildSpec.from_object({
                'version': '0.2',
                'phases': {
                    'pre_build': {
                        'commands': [
                            'echo Logging in to Amazon ECR...',
                            'aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPOSITORY_URI',
                            'COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)'
                        ]
                    },
                    'build': {
                        'commands': [
                            'echo Build started on `date`',
                            'docker build -t $REPOSITORY_URI:latest -f Dockerfile .',
                            'docker tag $REPOSITORY_URI:latest $REPOSITORY_URI:$IMAGE_TAG'
                        ]
                    },
                    'post_build': {
                        'commands': [
                            'echo Build completed on `date`',
                            'docker push $REPOSITORY_URI:latest',
                            'docker push $REPOSITORY_URI:$IMAGE_TAG'
                        ]
                    }
                }
            })
        )

        #-----------------
        #   Permissions -
        #-----------------
        # Permissions for the CodeBuild project

        docker_repository.grant_pull_push(build_project.role)

        build_project.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[f"{source_bucket.bucket_arn}/*"]
        ))

        build_project.add_to_role_policy(iam.PolicyStatement(
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"]
        ))

        s3_deployment.BucketDeployment(self, f"{repository_name}-{stage}-s3-deployment",
            sources=[s3_deployment.Source.asset("./microservice")],
            destination_bucket=source_bucket,
            destination_key_prefix="microservice"  # Folder within the S3 bucket to upload to
        )

        rule = events.Rule(self, f"{repository_name}-{stage}-rule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["AWS API Call via CloudTrail"],
                detail={
                    'eventName': ['PutObject', 'CopyObject', 'CompleteMultipartUpload'],
                    'requestParameters': {
                        'bucketName': [source_bucket.bucket_name]
                    }
                }
            )
        )

        rule.add_target(targets.CodeBuildProject(build_project))

        #-----------------
        #   Deployment  -
        #-----------------

        # Define all is needed for a fargate service

        cluster = ecs.Cluster(self, f"{repository_name}-{stage}-cluster",
            cluster_name=f"{repository_name}-{stage}-cluster",
            vpc=main_vpc
        )

        log_group = logs.LogGroup(self, f"{repository_name}-{stage}-log-group",
            log_group_name=f"/ecs/{repository_name}-{stage}-log-group",
            removal_policy=RemovalPolicy.DESTROY
        )

        task_definition = ecs.FargateTaskDefinition(self,f"{repository_name}-{stage}-task-definition",
            memory_limit_mib=512,
            cpu=256,
        )

        task_definition.add_container("MicroServiceContainer",
            image=ecs.ContainerImage.from_ecr_repository(docker_repository, tag=image_tag),
            logging=ecs.LogDrivers.aws_logs(
                log_group=log_group,
                stream_prefix="ecs"
            ),
            port_mappings=[ecs.PortMapping(container_port=80)]
        )

        service = ecs.FargateService(self, f"{repository_name}-{stage}-service",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            assign_public_ip=True
        )

        CfnOutput(self, "StackRegion", value=self.region, description="AWS Region")
        CfnOutput(self, "DockerRepositoryUri", value=docker_repository.repository_uri, description="Docker Repository URL")
