import aws_cdk as core
import aws_cdk.assertions as assertions

from dctechevents.dctechevents_stack import DctecheventsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in dctechevents/dctechevents_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = DctecheventsStack(app, "dctechevents")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
