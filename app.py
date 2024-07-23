from aws_cdk import App

from stack import AppStack

app = App()

AppStack(app, "Ec2ServiceStack", repository_name="ec2-service", stage="staging", image_tag="0.0.1", push_image=True)

app.synth()
