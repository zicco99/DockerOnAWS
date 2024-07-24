from aws_cdk import (
    CfnOutput,
    Stack,
    Stage,
    RemovalPolicy,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment
)
from constructs import Construct

class AppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, repository_name: str, stage: str, image_tag: str, push_image: bool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
 
        source_bucket = s3.Bucket(self, f"{repository_name}-{stage}-source_bucket",
            bucket_name=f"{repository_name}-{stage}-source-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        s3_deployment.BucketDeployment(self, f"{repository_name}-{stage}-s3_deployment",
            sources=[s3_deployment.Source.asset("./microservice")],
            destination_bucket=source_bucket,
            destination_key_prefix="microservice"
        )

        docker_repository = ecr.Repository(self, f"{repository_name}-{stage}-docker_repository",
            repository_name=repository_name,
            removal_policy=RemovalPolicy.DESTROY
        )

        build_project = codebuild.Project(self, f"{repository_name}-{stage}-microservice_build_project",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
                environment_variables={
                    'AWS_ACCOUNT_ID': codebuild.BuildEnvironmentVariable(
                        value=self.account
                    ),
                    'AWS_DEFAULT_REGION': codebuild.BuildEnvironmentVariable(
                        value=self.region
                    ),
                    'REPOSITORY_URI': codebuild.BuildEnvironmentVariable(
                        value=docker_repository.repository_uri
                    ),
                    'IMAGE_TAG': codebuild.BuildEnvironmentVariable(
                        value='latest'  # Default image tag
                    )
                }
            ),
            source=codebuild.Source.s3(
                bucket=source_bucket,
                path="microservice/"  # Ensure this path matches the destination_key_prefix in BucketDeployment
            ),
            build_spec=codebuild.BuildSpec.from_object({
                'version': '0.2',
                'phases': {
                    'pre_build': {
                        'commands': [
                            'echo Logging in to Amazon ECR...',
                            'aws --version',
                            'aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPOSITORY_URI',
                            'COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)',
                            'IMAGE_TAG=${COMMIT_HASH:=latest}'
                        ]
                    },
                    'build': {
                        'commands': [
                            'echo Build started on `date`',
                            'echo Building the Docker image...',
                            'docker build -t $REPOSITORY_URI:latest -f Dockerfile .',
                            'docker tag $REPOSITORY_URI:latest $REPOSITORY_URI:$IMAGE_TAG'
                        ]
                    },
                    'post_build': {
                        'commands': [
                            'echo Build completed on `date`',
                            'echo Pushing the Docker images...',
                            'docker push $REPOSITORY_URI:latest',
                            'docker push $REPOSITORY_URI:$IMAGE_TAG'
                        ]
                    }
                }
            })
        )

        docker_repository.grant_pull_push(build_project.role)

        build_project.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[f"{source_bucket.bucket_arn}/*"]
        ))

        build_project.add_to_role_policy(iam.PolicyStatement(
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"]
        ))

        # Outputs
        CfnOutput(self, "StackRegion", value=self.region, description="AWS Region")
        CfnOutput(self, "DockerRepositoryUri", value=docker_repository.repository_uri, description="Docker Repository Url")