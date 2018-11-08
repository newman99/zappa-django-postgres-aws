"""Zappa Setup.

Create the Zappa settings file, create a new Django project and build
the Docker images.

"""
import subprocess
import os
import json
import random
import string
from pathlib import Path
import boto3
import botocore
import click

TEMPLATE = 'https://gitlab.com/newman99/django-project-template/-/archive/master/django-project-template-master.zip'  # noqa


@click.command()
@click.argument('project_name')
@click.option('-a', '--aws', is_flag=True, help='Create AWS resources.',
              show_default=True)
@click.option('-B', '--buildall', is_flag=True, help='Build all',
              show_default=True)
@click.option('-b', '--build', is_flag=True, help='Build Docker container.',
              show_default=True)
@click.option('-e', '--email', prompt='Enter you Django admin email address',
              help="Django admin email")
@click.option('-n', '--name', prompt='Enter you Django admin username',
              help="Django admin username", default='admin', show_default=True)
@click.option('-p', '--password', prompt='Enter you Django admin password',
              hide_input=True, confirmation_prompt=True,
              help="Django admin password")
@click.option('-r', '--requirements', is_flag=True,
              help='Install requirements.txt using pip.', show_default=True)
@click.option('-s', '--startapp', is_flag=True,
              help='Create a new Django project.', show_default=True)
@click.option('-v', '--virtual', is_flag=True,
              help='Create a new Python virtual environment.',
              show_default=True)
def main(project_name, name, email, password, aws, build, buildall,
         requirements, startapp, virtual):
    """Django - Docker - Zappa - AWS - Lambda.

    Build and deploy a Django app in Docker for local development and
    on AWS Lambda using Zappa.
    """
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

    if startapp or buildall:
        if os.path.exists(project_name):
            print('Error: a project named "{}" already exists.'.format(
                project_name))
        else:
            print('STARTPROJECT')
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
                '--template={}'.format(TEMPLATE)
            ])
            print('MIGRATE')
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
            print('CREATESUPERUSER')
            subprocess.run([
                'docker-compose',
                'exec',
                'web',
                '/bin/bash',
                '-c',
                '''/var/task/test3/manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('{}', '{}', '{}')"'''.format(  # noqa
                    name, email, password
                )
            ])
            subprocess.run([
                'docker-compose',
                'down'
            ])

    if aws or buildall:
        create_aws(project_name)

    exit(0)


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
            print(e)

    create_zappa_settings(env)


def create_zappa_settings(env):
    """Create the zappa_settings.json file."""
    zappa = {
        'dev': {
            'profile_name': 'newman99',
            'runtime': 'python3.6',
            'timeout_seconds': 300,
            'use_precompiled_packages': True,
            'environment_variables': {
                'DJANGO_ENV': 'aws-dev'
            },
            "manage_roles": False,
            "role_name": "Zappa"
        },
        'vpc_config': {'SubnetIds': [], 'SecurityGroupIds': []}
    }

    zappa['vpc_config']['SecurityGroupIds'] = env['SecurityGroupIds']

    zappa['dev']['s3_bucket'] = 'zappa-{}'.format(
        ''.join(random.choices(string.ascii_lowercase + string.digits, k=9)))

    with open('{}/.aws/config'.format(Path.home())) as fp:
        for line in fp:
            if 'region' in line:
                (a, b) = line.rstrip().split(' = ')
                zappa['dev']['aws_region'] = b

    zappa['dev']['project_name'] = '{0}'.format(env['PROJECT_NAME'])
    zappa['dev']['django_settings'] = '{0}.{0}.settings'.format(
        env['PROJECT_NAME'])

    with open('zappa_settings.json', 'w') as fp:
        fp.write(json.dumps(zappa, indent=4, sort_keys=True))

    return zappa


if __name__ == '__main__':
    main()
