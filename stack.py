from aws_cdk import CfnOutput, Stack, Stage
from constructs import Construct


class AppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, repository_name: str, stage: Stage, image_tag: str, push_image: bool, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        

        CfnOutput(self, "StackRegion", value=self.region, description="AWS Region")