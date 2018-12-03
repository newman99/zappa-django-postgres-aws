"""AWS Create Role Test."""
import sys
import boto3
from troposphere import Template, Ref, Tags, ec2
from troposphere.iam import Policy as IAM_Policy
from troposphere.iam import Role as IAM_Role
from troposphere.iam import InstanceProfile as IAM_InstanceProfile
from awacs.aws import Action
from awacs.aws import Allow
from awacs.aws import Policy
from awacs.aws import Principal
from awacs.aws import Statement
from awacs.sts import AssumeRole

t = Template()

policy = IAM_Policy(
    PolicyName="ZappaPolicyTest1",
    PolicyDocument=Policy(
        Statement=[
            Statement(
                Effect="Allow",
                Action=[
                    Action('s3', '*')
                ],
                Resource=['arn:aws:s3:::*']
            ),
            Statement(
                Effect="Allow",
                Action=[
                    Action('logs', '*')
                ],
                Resource=['arn:aws:logs:*:*:*']
            ),
            Statement(
                Effect="Allow",
                Action=[
                    Action('ec2', 'AttachNetworkInterface'),
                    Action('ec2', 'CreateNetworkInterface'),
                    Action('ec2', 'DeleteNetworkInterface'),
                    Action('ec2', 'DescribeInstances'),
                    Action('ec2', 'DescribeNetworkInterfaces'),
                    Action('ec2', 'DetachNetworkInterface'),
                    Action('ec2', 'ModifyNetworkInterfaceAttribute'),
                    Action('ec2', 'ResetNetworkInterfaceAttribute'),
                ],
                Resource=['*']
            ),
            Statement(
                Effect="Allow",
                Action=[
                    Action('xray', 'PutTraceSegments'),
                    Action('xray', 'PutTelemetryRecords'),
                ],
                Resource=['*']
            ),
        ]
    )
)

role = t.add_resource(IAM_Role(
    'ZappaRoleTest1',
    RoleName='ZappaRoleTest1_rn',
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", [
                    "apigateway.amazonaws.com",
                    "events.amazonaws.com",
                    "lambda.amazonaws.com"
                ])
            )
        ]
    ),
    Policies=[policy]
))

instance_profile = t.add_resource(IAM_InstanceProfile(
    "InstanceProfile", Roles=[Ref(role)]
))

myVpc = t.add_resource(
    ec2.VPC(
        'TestVPC',
        CidrBlock='172.31.0.0/16'
    )
)

subnet1 = t.add_resource(
    ec2.Subnet(
        'Subnet1',
        CidrBlock='172.31.0.0/20',
        AvailabilityZone='us-east-1a',
        VpcId=Ref(myVpc)
    )
)

subnet2 = t.add_resource(
    ec2.Subnet(
        'Subnet2',
        CidrBlock='172.31.16.0/20',
        AvailabilityZone='us-east-1b',
        VpcId=Ref(myVpc)
    )
)

mySecurityGroup = t.add_resource(
    ec2.SecurityGroup(
        'simpleSG',
        GroupDescription='postgres traffic allowed',
        VpcId=Ref(myVpc),
        Tags=Tags(
            Name="simpleSG"
        )
    )
)
mySecurityGroupRule = t.add_resource(
    ec2.SecurityGroupIngress(
        "mySecurityGroupIngress",
        GroupId=Ref('simpleSG'),
        IpProtocol='tcp',
        FromPort='5432',
        ToPort='5432',
        SourceSecurityGroupId=Ref('simpleSG'),
        DependsOn='simpleSG'
    )
)

session = boto3.Session(profile_name=sys.argv[1])
cfn = session.client('cloudformation')
template_json = t.to_json(indent=4)
cfn.validate_template(TemplateBody=template_json)

print(template_json)

stack = {
    'StackName': 'ZappaTestStack20',
    'TemplateBody': template_json,
    'Capabilities': ['CAPABILITY_NAMED_IAM']
}

cfn.create_stack(**stack)
