from aws_cdk import CfnOutput, Stack, Stage, RemovalPolicy
from aws_cdk import (
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_s3

)
from constructs import Construct


class AppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, repository_name: str, stage: Stage, image_tag: str, push_image: bool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        docker_repository = ecr.Repository(self, f"{repository_name}-{stage}-docker_repository",
            repository_name=repository_name,
            removal_policy=RemovalPolicy.DESTROY
        )

        CfnOutput(self, "StackRegion", value=self.region, description="AWS Region")
        CfnOutput(self, "DockerRepositoryUri", value=docker_repository.repository_uri, description="Docker Repository Url")