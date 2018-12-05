"""Zappa Setup.

Create the Zappa settings file, create a new Django project and build
the Docker images.

"""
import json
import random
import re
import string
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import botocore
import click
import docker
from troposphere import ec2, GetAtt, Output, Ref, Tags, Template
from troposphere.rds import DBInstance, DBSubnetGroup
from troposphere.s3 import Bucket, CorsConfiguration, CorsRules, PublicRead
from troposphere.iam import Policy as IAM_Policy
from troposphere.iam import Role as IAM_Role
from troposphere.iam import InstanceProfile as IAM_InstanceProfile
from awacs.aws import Action, Allow, Policy, Principal, Statement
from awacs.sts import AssumeRole

TEMPLATE = 'https://gitlab.com/newman99/django-split-settings-project-template/-/archive/master/django-split-settings-project-template-master.zip'  # noqa


@click.command()
@click.argument('project_name')
@click.option('-B', '--buildall', is_flag=True, show_default=True,
              help='Build all')
@click.option('-b', '--build', is_flag=True, show_default=True,
              help='Build Docker container.')
@click.option('-r', '--requirements', is_flag=True, show_default=True,
              help='Install requirements.txt using pip.')
@click.option('-s', '--startproject', is_flag=True, show_default=True,
              help='Create a new Django project.')
@click.option('-t', '--template', default=TEMPLATE,
              help="Django startproject template file")
@click.option('-v', '--virtual', is_flag=True, show_default=True,
              help='Create a new Python virtual environment.')
@click.option('-z', '--zappa', is_flag=True, show_default=True,
              help='Deploy Zappa.')
@click.option('--name', prompt='Enter your full name', help="Full name")
@click.option('--username', prompt='Enter your Django admin username',
              default='admin', show_default=True, help="Django admin username")
@click.option('--email', prompt='Enter your Django admin email address',
              help="Django admin email")
@click.option('--password', prompt='Enter your Django admin password',
              hide_input=True, confirmation_prompt=True,
              help="Django admin password")
def main(project_name, name, username, email, password, build, buildall,
         requirements, startproject, virtual, zappa, template):
    """Django - Docker - Zappa - AWS - Lambda.

    Build and deploy a Django app in Docker for local development and
    on AWS Lambda using Zappa.
    """
    start_time = time.monotonic()

    session = create_boto_session()

    role_stack_name = create_role(project_name, session)

    role_info = get_role_name(role_stack_name, session)

    stack_name = create_stack(project_name, role_info, session)

    create_env_file(project_name, name, email, session)

    client = docker.from_env()

    if build or buildall:
        click.echo('Building Docker image...')
        client.images.build(
            path=str(Path.cwd()),
            tag='{}_web:latest'.format(project_name)
        )

    if virtual or buildall:
        click.echo('Creating virtual Python environment...')
        client.containers.run(
            '{}_web:latest'.format(project_name),
            'python -m virtualenv ve',
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            }
        )

    if requirements or buildall:
        click.echo('Installing Python requirements...')
        client.containers.run(
            '{}_web:latest'.format(project_name),
            '/bin/bash -c \
            "source ve/bin/activate && pip install -r requirements.txt"',
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            }
        )

    if startproject or buildall:
        start_project(project_name, client, username,
                      email, password, template)

    create_zappa_settings(project_name, role_stack_name, session, client)

    if zappa or buildall:
        aws_lambda_host = create_zappa_project(
            project_name, stack_name, session,
            client, username, email, password
        )
        click.echo('Django website is running at http://{}/dev/'.format(
            aws_lambda_host
        ))

    end_time = time.monotonic()

    click.echo('Elapsed time: {}'.format(
        time.strftime('%M:%S', time.gmtime(end_time - start_time))
    ))

    exit(0)


def start_project(project_name, client, username, email, password, template):
    """Start Django project."""
    if Path(project_name).exists():
        click.echo('Error: a project named "{}" already exists.'.format(
            project_name))
    else:
        click.echo('Run Django startproject...')
        client.containers.run(
            '{}_web:latest'.format(project_name),
            've/bin/django-admin startproject {} . --template={}'.format(
                project_name,
                template
            ),
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            }
        )

        click.echo('Run initial Django migration...')
        subprocess.run([
            'docker-compose',
            'up',
            '-d'
        ])
        subprocess.run([
            'docker-compose',
            'exec',
            'web',
            '/var/task/manage.py',
            'migrate'
        ])

        click.echo('Run Django createsuperuser in Docker container...')
        subprocess.run([
            'docker-compose',
            'exec',
            'web',
            '/bin/bash',
            '-c',
            '''/var/task/manage.py shell -c \
                "from django.contrib.auth import get_user_model; \
                User = get_user_model(); \
                User.objects.create_superuser('{}', '{}', '{}')"'''.format(
                    username, email, password
            )
        ])
        subprocess.run([
            'docker-compose',
            'down'
        ])


def create_zappa_project(
    project_name, stack_name, session, client, username, email, password
):
    """Create the zappa project."""
    aws_rds_host = get_aws_rds_host(stack_name, session)

    with open('.env', 'a') as fp:
        fp.write('AWS_RDS_HOST={}\n'.format(aws_rds_host))

    aws_lambda_host = deploy_zappa(project_name, client)

    with open('.env', 'a') as fp:
        fp.write('AWS_LAMBDA_HOST={}\n'.format(aws_lambda_host))

    update_zappa(project_name, client)

    click.echo('Run initial Django migration for Zappa deployment...')
    client.containers.run(
        '{}_web:latest'.format(project_name),
        '/bin/bash -c "source ve/bin/activate && zappa manage dev migrate"',
        volumes={
            Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            '{}/.aws'.format(Path.home()): {
                'bind': '/root/.aws',
                'mode': 'ro'
            }
        }
    )
    click.echo('Create Django superuser {} for Zappa...'.format(username))
    try:
        django_command = '''from django.contrib.auth import get_user_model; \
        User = get_user_model(); \
        User.objects.create_superuser(\\"{}\\", \\"{}\\", \\"{}\\")'''.format(
                username, email, password
        )
        bash_command = 'source ve/bin/activate \
        && zappa invoke --raw dev "{}"'.format(django_command)
        zappa_command = "/bin/bash -c '{}'".format(bash_command)
        client.containers.run(
            '{}_web:latest'.format(project_name),
            zappa_command,
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
                '{}/.aws'.format(Path.home()): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                }
            }
        )
    except docker.errors.ContainerError:
        pass

    click.echo('Running collectstatic for Zappa deployment...')
    client.containers.run(
        '{}_web:latest'.format(project_name),
        '/bin/bash -c "source ve/bin/activate \
        && python manage.py collectstatic --noinput"',
        environment={'DJANGO_ENV': 'aws-dev'},
        volumes={
            Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            '{}/.aws'.format(Path.home()): {
                'bind': '/root/.aws',
                'mode': 'ro'
            }
        }
    )

    return(aws_lambda_host)


def create_env_file(project_name, name, email, session):
    """Create the .env file."""
    env = {
        'PROJECT_NAME': project_name,
        'ADMIN_USER': name,
        'ADMIN_EMAIL': email,
        'DB_NAME': 'postgres',
        'DB_USER': 'postgres',
        'DB_PASSWORD': 'postgres',
        'ZAPPA_DEPLOYMENT_TYPE': 'dev',
        'DJANGO_SECRET_KEY': '{}'.format(''.join(
            random.choices(string.ascii_lowercase + string.digits, k=50))),
        'AWS_ACCESS_KEY_ID': session.get_credentials().access_key,
        'AWS_SECRET_ACCESS_KEY': session.get_credentials().secret_key,
        'AWS_STORAGE_BUCKET_NAME': 'zappa-django-{}'.format(project_name)
    }
    with open('.env', 'w') as fp:
        for e in env:
            fp.write('{}={}\n'.format(e, env[e]))
    return env


def create_boto_session():
    """Create boto session."""
    session = botocore.session.Session()
    config = session.full_config
    profiles = config.get('profiles', {})
    profile_names = list(profiles.keys())

    if not profile_names:
        click.echo('Error: Set up the ~/.aws/credentials file.')
        exit(1)
    elif len(profile_names) == 1:
        profile_name = profile_names[0]
        click.echo("Okay, using profile {}!".format(
            click.style(profile_name, bold=True))
        )
    else:
        if "default" in profile_names:
            default_profile = [p for p in profile_names if p == "default"][0]
        else:
            default_profile = profile_names[0]
        while True:
            profile_name = input(
                "We found the following profiles: {}, and {}. "
                "Which would you like us to use? (default '{}'): "
                .format(
                     ', '.join(profile_names[:-1]),
                     profile_names[-1],
                     default_profile
                 )) or default_profile
            if profile_name in profiles:
                break

    session = boto3.Session(profile_name=profile_name)

    return session


def create_zappa_settings(project_name, role_stack_name, session, client):
    """Create the zappa_settings.json file."""
    role_info = get_role_name(role_stack_name, session)

    zappa = {
        'dev': {
            'project_name': project_name,
            'django_settings': '{0}.settings'.format(project_name),
            'profile_name': session.profile_name,
            'profile-region': session.region_name,
            's3_bucket': 'zappa-{}'.format(''.join(
                random.choices(string.ascii_lowercase + string.digits, k=9))
            ),
            'runtime': 'python3.6',
            'timeout_seconds': 300,
            'use_precompiled_packages': True,
            'environment_variables': {
                'DJANGO_ENV': 'aws-dev'
            },
            "manage_roles": False,
            "role_name": role_info['role_name'],
            'vpc_config': {
                'SubnetIds': role_info['subnet_ids'],
                'SecurityGroupIds': (role_info['security_group'],)
            }
        }
    }

    zappa['dev']['s3_bucket'] = 'zappa-{}'.format(
        ''.join(random.choices(string.ascii_lowercase + string.digits, k=9)))

    with open('zappa_settings.json', 'w') as fp:
        fp.write(json.dumps(zappa, indent=4, sort_keys=True))

    return zappa


def create_stack(project_name, role_info, session):
    """Create Postgres RDS instance using troposphere."""
    stack_name = '{}-zappa-rds-s3'.format(project_name)

    t = Template()

    t.add_description("RDS PostgreSQL DB instance for Zappa Django project.")

    mydbsubnetgroup = t.add_resource(DBSubnetGroup(
        "MyDBSubnetGroup",
        DBSubnetGroupDescription="Subnets available for the RDS DB Instance",
        SubnetIds=role_info['subnet_ids'],
    ))

    db_instance = t.add_resource(DBInstance(
        '{}Zappa'.format(re.sub(
            r'-([a-z,A-Z,0-9])',
            lambda x: x.group(1).upper(), project_name.capitalize()
        )),
        AllocatedStorage="20",
        DBInstanceClass="db.t2.micro",
        Engine="postgres",
        EngineVersion="10.4",
        DBInstanceIdentifier='{}-zappa'.format(project_name),
        MasterUsername="postgres",
        MasterUserPassword="postgres",
        PubliclyAccessible=False,
        DBSubnetGroupName=Ref(mydbsubnetgroup),
        VPCSecurityGroups=[role_info['security_group']]
    ))

    t.add_resource(Bucket(
        '{}S3Zappa'.format(re.sub(
            r'-([a-z,A-Z,0-9])',
            lambda x: x.group(1).upper(), project_name.capitalize()
        )),
        BucketName='zappa-django-{}'.format(project_name),
        CorsConfiguration=CorsConfiguration(
            CorsRules=[CorsRules(
                AllowedHeaders=["Authorization"],
                AllowedMethods=["GET"],
                AllowedOrigins=["*"],
                MaxAge=3000
            )],
        ),
        AccessControl=PublicRead
    ))

    t.add_output(Output(
        'AwsRdsHost',
        Description='AWS RDS HOST',
        Value=GetAtt(db_instance, "Endpoint.Address")
    ))

    resource = session.resource('cloudformation')
    resource.create_stack(
        StackName=stack_name,
        TemplateBody=t.to_json()
    )

    return stack_name


def get_aws_rds_host(stack_name, session):
    """Get the AWS RDS host."""
    client = session.client('cloudformation')
    stack_status = None
    click.echo("Waiting for stack creation...", nl=False)
    while stack_status != 'CREATE_COMPLETE':
        click.echo(".", nl=False)
        time.sleep(30)
        response = client.describe_stacks(
            StackName=stack_name
        )
        stack_status = response['Stacks'][0]['StackStatus']
        if stack_status == 'ROLLBACK_COMPLETE':
            click.echo('Error - Stack creation failed (Create RDS Stack).')
            exit(1)
    click.echo(' done', fg='green')
    aws_rds_host = response['Stacks'][0]['Outputs'][0]['OutputValue']

    return aws_rds_host


def get_role_name(stack_name, session):
    """Get Role name."""
    client = session.client('cloudformation')
    stack_status = None
    click.echo("Waiting for stack creation...", nl=False)
    while stack_status != 'CREATE_COMPLETE':
        click.echo(".", nl=False)
        time.sleep(30)
        response = client.describe_stacks(
            StackName=stack_name
        )
        stack_status = response['Stacks'][0]['StackStatus']
        if stack_status == 'ROLLBACK_COMPLETE':
            click.echo('Error - Stack creation failed (Create Role Stack).')
            exit(1)
    click.echo(' done', fg='green')
    outputs = response['Stacks'][0]['Outputs']

    role_name = ''
    security_group = ''
    subnet_ids = []

    for output in outputs:
        if output['OutputKey'] == 'RoleName':
            role_name = output['OutputValue']
        if output['OutputKey'] == 'SecurityGroupId':
            security_group = output['OutputValue']
        if output['Description'] == 'SubnetId':
            subnet_ids.append(output['OutputValue'])

    return {
        'role_name': role_name,
        'security_group': security_group,
        'subnet_ids': subnet_ids
    }


def deploy_zappa(project_name, client):
    """Deploy to AWS Lambda using Zappa."""
    click.echo('Deploying Django project on AWS Lambda using Zappa...')
    try:
        client.containers.run(
            '{}_web:latest'.format(project_name),
            '/bin/bash -c "source ve/bin/activate && zappa deploy dev"',
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
                '{}/.aws'.format(Path.home()): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                }
            }
        )
    except docker.errors.ContainerError:
        pass

    return get_lambda_host(project_name, client)


def update_zappa(project_name, client):
    """Deploy to AWS Lambda using Zappa."""
    click.echo(
        'Updating Zappa deployment to add Lambda host to ALLOWED_HOSTS...'
    )
    try:
        client.containers.run(
            '{}_web:latest'.format(project_name),
            '/bin/bash -c "source ve/bin/activate && zappa update dev"',
            volumes={
                Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
                '{}/.aws'.format(Path.home()): {
                    'bind': '/root/.aws',
                    'mode': 'ro'
                }
            }
        )
    except docker.errors.ContainerError:
        pass


def get_lambda_host(project_name, client):
    """Get Lambda host."""
    output = client.containers.run(
        '{}_web:latest'.format(project_name),
        '/bin/bash -c "source ve/bin/activate && zappa status dev"',
        volumes={
            Path.cwd(): {'bind': '/var/task', 'mode': 'rw'},
            '{}/.aws'.format(Path.home()): {
                'bind': '/root/.aws',
                'mode': 'ro'
            }
        }
    )

    for line in output.split(b'\n'):
        tokens = line.split(b': ')
        if tokens[0] == b'\tAPI Gateway URL':
            aws_lambda_host = urlparse(
                tokens[1].decode('utf-8').replace(' ', '')
            ).netloc
            return aws_lambda_host


def create_role(project_name, session):
    """Create role."""
    t = Template()

    t.add_description("AWS Role, VPC, Security Group, and Subnet for Zappa.")

    policy = IAM_Policy(
        PolicyName="{}-Policy".format(project_name),
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
                        Action('lambda', 'InvokeFunction')
                    ],
                    Resource=['*']
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
        'ZappaRole{}'.format(project_name),
        RoleName='ZappaRole{}'.format(project_name),
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

    t.add_resource(IAM_InstanceProfile(
        "InstanceProfile", Roles=[Ref(role)]
    ))

    myVpc = t.add_resource(
        ec2.VPC(
            'VPC{}'.format(project_name),
            CidrBlock='172.31.0.0/16',
            Tags=Tags(
                Name='ZappaVPC{}'.format(project_name),
            )
        )
    )

    subnet_1 = t.add_resource(
        ec2.Subnet(
            'Subnet1{}'.format(project_name),
            CidrBlock='172.31.0.0/20',
            AvailabilityZone='us-east-1a',
            VpcId=Ref(myVpc)
        )
    )

    subnet_2 = t.add_resource(
        ec2.Subnet(
            'Subnet2{}'.format(project_name),
            CidrBlock='172.31.16.0/20',
            AvailabilityZone='us-east-1b',
            VpcId=Ref(myVpc)
        )
    )

    security_group = t.add_resource(
        ec2.SecurityGroup(
            'ZappaSG{}'.format(project_name),
            GroupDescription='postgres traffic allowed',
            VpcId=Ref(myVpc),
            Tags=Tags(
                Name='ZappaSG{}'.format(project_name),
            )
        )
    )
    t.add_resource(
        ec2.SecurityGroupIngress(
            "{}GroupIngress".format(project_name),
            GroupId=Ref('ZappaSG{}'.format(project_name),),
            IpProtocol='tcp',
            FromPort='5432',
            ToPort='5432',
            SourceSecurityGroupId=Ref('ZappaSG{}'.format(project_name),),
            DependsOn='ZappaSG{}'.format(project_name),
        )
    )

    t.add_output(Output(
        'RoleName',
        Description='Role Name',
        Value=Ref(role)
    ))

    t.add_output(Output(
        'SecurityGroupId',
        Description='Security Group Id',
        Value=GetAtt(security_group, "GroupId")
    ))

    t.add_output(Output(
        'SubnetId1',
        Description='SubnetId',
        Value=Ref(subnet_1)
    ))

    t.add_output(Output(
        'SubnetId2',
        Description='SubnetId',
        Value=Ref(subnet_2)
    ))

    stack_name = 'Zappa-Role-VPC-SG-{}'.format(project_name)

    resource = session.resource('cloudformation')
    resource.create_stack(
        StackName=stack_name,
        TemplateBody=t.to_json(),
        Capabilities=['CAPABILITY_NAMED_IAM']
    )

    return stack_name


if __name__ == '__main__':
    main()
