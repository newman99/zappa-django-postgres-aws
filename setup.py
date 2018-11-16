"""Zappa Setup.

Create the Zappa settings file, create a new Django project and build
the Docker images.

"""
import subprocess
import os
import re
import time
import json
import random
import string
import boto3
import botocore
import click
from pathlib import Path
from troposphere import Template, GetAtt, Output
from troposphere.rds import DBInstance

TEMPLATE = 'https://gitlab.com/newman99/django-project-template/-/archive/master/django-project-template-master.zip'  # noqa


@click.command()
@click.argument('project_name')
@click.option('-a', '--aws', is_flag=True, show_default=True,
              help='Create AWS resources.')
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
def main(project_name, name, username, email, password, aws, build, buildall,
         requirements, startproject, virtual, zappa, template):
    """Django - Docker - Zappa - AWS - Lambda.

    Build and deploy a Django app in Docker for local development and
    on AWS Lambda using Zappa.
    """
    os.environ['PROJECT_NAME'] = project_name

    session = create_boto_session()

    stack_name = create_rds(project_name, session)

    create_env_file(project_name, name, email)

    if build or buildall:
        subprocess.run(['docker-compose', 'build'])

    if virtual or buildall:
        subprocess.run([
            'docker',
            'run',
            '-ti',
            '-v',
            '{}:/var/task'.format(os.getcwd()),
            '{}_web:latest'.format(project_name),
            'python',
            '-m',
            'virtualenv',
            've'
        ])

    if requirements or buildall:
        subprocess.run([
            'docker',
            'run',
            '-v',
            '{}:/var/task'.format(os.getcwd()),
            '{}_web:latest'.format(project_name),
            '/bin/bash',
            '-c',
            'source ve/bin/activate && pip install -r requirements.txt'
        ])

    aws_rds_host = get_aws_rds_host(stack_name, session)

    with open('.env', 'a') as fp:
        fp.write('AWS_RDS_HOST={}\n'.format(aws_rds_host))

    if startproject or buildall:
        if os.path.exists(project_name):
            click.echo('Error: a project named "{}" already exists.'.format(
                project_name))
        else:
            click.echo('STARTPROJECT')
            subprocess.run([
                'docker',
                'run',
                '-ti',
                '-v',
                '{}:/var/task'.format(os.getcwd()),
                '{}_web:latest'.format(project_name),
                '/var/task/ve/bin/django-admin',
                'startproject',
                project_name,
                '.',
                '--template={}'.format(TEMPLATE)
            ])
            click.echo('MIGRATE')
            subprocess.run([
                'docker-compose',
                'up',
                '-d'
            ])
            subprocess.run([
                'docker-compose',
                'exec',
                'web',
                '/var/task/{}/manage.py'.format(project_name),
                'migrate'
            ])
            click.echo('CREATESUPERUSER')
            subprocess.run([
                'docker-compose',
                'exec',
                'web',
                '/bin/bash',
                '-c',
                '''/var/task/{}/manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('{}', '{}', '{}')"'''.format(  # noqa
                    project_name, username, email, password
                )
            ])
            subprocess.run([
                'docker-compose',
                'down'
            ])

    if aws or buildall:
        create_aws(project_name)

    create_zappa_settings(project_name, session)

    if zappa or buildall:
        aws_lambda_host = deploy_zappa(project_name)
        with open('.env', 'a') as fp:
            fp.write('AWS_LAMBDA_HOST={}\n'.format(aws_lambda_host))
        update_zappa(project_name)

    exit(0)


def create_env_file(project_name, name, email):
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
        'AWS_ACCESS_KEY_ID': '',
        'AWS_SECRET_ACCESS_KEY': '',
        'AWS_STORAGE_BUCKET_NAME': 'zappa-django-{}'.format(project_name)
    }
    with open('.env', 'w') as fp:
        for e in env:
            fp.write('{}={}\n'.format(e, env[e]))


def create_aws(project_name):
    """Create the AWS resources."""
    env = {'PROJECT_NAME': project_name}

    client = boto3.client('ec2')

    try:
        response = client.create_security_group(
            GroupName=project_name,
            Description=project_name
        )
        env['SecurityGroupIds'] = [response['GroupId']]
    except botocore.exceptions.ClientError:
        response = client.describe_security_groups(
            GroupNames=(project_name,)
        )
        env['SecurityGroupIds'] = [response['SecurityGroups'][0]['GroupId']]

    try:
        response = client.authorize_security_group_ingress(
            GroupId=env['SecurityGroupIds'][0],
            IpProtocol='tcp',
            FromPort=443,
            ToPort=443,
            CidrIp='0.0.0.0/0'
        )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
            pass
        else:
            click.echo(e)


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


def create_zappa_settings(project_name, session):
    """Create the zappa_settings.json file."""
    client = session.client('ec2')

    security_groups = client.describe_security_groups(
        Filters=[{
            'Name': 'description', 'Values': ['default VPC security group', ]
        }]
    )

    group_ids = []
    for sg in security_groups['SecurityGroups']:
        group_ids.append(sg['GroupId'])

    vpc = client.describe_vpcs()

    subnets = client.describe_subnets(
        Filters=[
            {'Name': 'vpc-id', 'Values': [vpc['Vpcs'][0]['VpcId'], ]},
            {
                'Name': 'availability-zone',
                'Values': ['us-east-1a', 'us-east-1b']
            }
        ]
    )

    subnet_ids = []
    for sn in subnets['Subnets']:
        subnet_ids.append(sn['SubnetId'])

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
            "role_name": "Zappa",
            'vpc_config': {
                'SubnetIds': subnet_ids,
                'SecurityGroupIds': group_ids
            }
        }
    }

    zappa['dev']['s3_bucket'] = 'zappa-{}'.format(
        ''.join(random.choices(string.ascii_lowercase + string.digits, k=9)))

    with open('zappa_settings.json', 'w') as fp:
        fp.write(json.dumps(zappa, indent=4, sort_keys=True))

    return zappa


def create_rds(project_name, session):
    """Create Postgres RDS instance using troposphere."""
    stack_name = '{}-zappa'.format(project_name)

    t = Template()

    t.add_description("RDS PostgreSQL DB instance for Zappa Django project.")

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
        PubliclyAccessible=False
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
    while stack_status != 'CREATE_COMPLETE':
        click.echo("Waiting for stack creation...")
        time.sleep(120)
        response = client.describe_stacks(
            StackName=stack_name
        )
        stack_status = response['Stacks'][0]['StackStatus']
    aws_rds_host = response['Stacks'][0]['Outputs'][0]['OutputValue']

    return aws_rds_host


def deploy_zappa(project_name):
    """Deploy to AWS Lambda using Zappa."""
    subprocess.run([
        'docker',
        'run',
        '-v',
        '{}:/var/task'.format(Path.cwd()),
        '-v',
        '{}/.aws:/root/.aws'.format(Path.home()),
        '{}_web:latest'.format(project_name),
        '/bin/bash',
        '-c',
        'source ve/bin/activate && zappa deploy dev'
    ])

    return get_lambda_host(project_name)


def update_zappa(project_name):
    """Deploy to AWS Lambda using Zappa."""
    subprocess.run([
        'docker',
        'run',
        '-v',
        '{}:/var/task'.format(Path.cwd()),
        '-v',
        '{}/.aws:/root/.aws'.format(Path.home()),
        '{}_web:latest'.format(project_name),
        '/bin/bash',
        '-c',
        'source ve/bin/activate && zappa update dev'
    ])


def get_lambda_host(project_name):
    """Get Lambda host."""
    output = subprocess.check_output([
        'docker',
        'run',
        '-v',
        '{}:/var/task'.format(Path.cwd()),
        '-v',
        '{}/.aws:/root/.aws'.format(Path.home()),
        '{}_web:latest'.format(project_name),
        '/bin/bash',
        '-c',
        'source ve/bin/activate && zappa status dev'
    ])

    for line in output.split(b'\n'):
        tokens = line.split(b': ')
        if tokens[0] == b'\tAPI Gateway URL':
            aws_lambda_host = tokens[1].replace(b' ', b'').decode("utf-8")
            aws_lambda_host = aws_lambda_host.replace('https://', '')
            aws_lambda_host = aws_lambda_host.replace('/dev', '')
            return aws_lambda_host


if __name__ == '__main__':
    main()
