from aws_cdk import App

from stack import AppStack

app = App()

AppStack(app, "AppStack", repository_name="webapp", stage="staging", image_tag="0.0.1", push_image=True)

app.synth()
