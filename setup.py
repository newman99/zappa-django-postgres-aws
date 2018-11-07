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
import argparse

TEMPLATE = 'https://gitlab.com/newman99/django-project-template/-/archive/master/django-project-template-master.zip'  # noqa


def main():
    """Main."""
    args = process_args()

    if args.build:
        subprocess.run(['docker-compose', 'build'])

    if args.virtual:
        subprocess.run([
            'docker',
            'run',
            '-ti',
            '-v',
            '{}:/var/task'.format(os.getcwd()),
            '{}_web:latest'.format(args.project_name),
            'python',
            '-m',
            'virtualenv',
            've'
        ])

    if args.requirements:
        subprocess.run(
            ['docker run -ti -v {}:/var/task {}_web:latest /bin/bash -c "source ve/bin/activate && ve/bin/pip install -r requirements.txt"'.format(os.getcwd(), args.project_name)], # noqa
            shell=True
        )

    if args.startapp:
        if os.path.exists(args.project_name):
            print('Error: a project named "{}" already exists.'.format(
                args.project_name))
        else:
            subprocess.run([
                'docker',
                'run',
                '-ti',
                '-v',
                '{}:/var/task'.format(os.getcwd()),
                '{}_web:latest'.format(args.project_name),
                '/var/task/ve/bin/django-admin',
                'startproject',
                args.project_name,
                '--template={}'.format(TEMPLATE)
            ])

    if args.aws:
        create_aws(args)

    exit(0)


def create_aws(args):
    """Create the AWS resources."""
    env = {'PROJECT_NAME': args.project_name}

    client = boto3.client('ec2')

    try:
        response = client.create_security_group(
            GroupName=args.project_name,
            Description=args.project_name
        )
        env['SecurityGroupIds'] = [response['GroupId']]
    except botocore.exceptions.ClientError:
        response = client.describe_security_groups(
            GroupNames=(args.project_name,)
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


def process_args():
    """Process command line arguements."""
    parser = argparse.ArgumentParser(
        description='Build a Zappa Django Project.'
    )
    parser.add_argument('project_name', type=str, help='Project name')
    parser.add_argument(
        '-a',
        '--aws',
        action='store_true',
        help='Create AWS resources.'
    )
    parser.add_argument(
        '-b',
        '--build',
        action='store_true',
        help='Build Docker contianer.'
    )
    parser.add_argument(
        '-r',
        '--requirements',
        action='store_true',
        help='Install requirements.txt using pip.'
    )
    parser.add_argument(
        '-s',
        '--startapp',
        action='store_true',
        help='Create a new Django project.'
    )
    parser.add_argument(
        '-v',
        '--virtual',
        action='store_true',
        help='Create a new Python virtual environment.'
    )

    args = parser.parse_args()

    # If none of these option are selected, assume do all of them.
    if (
            not args.aws and
            not args.build and
            not args.requirements and
            not args.startapp and
            not args.virtual
    ):
        args.aws = True
        args.build = True
        args.requirements = True
        args.startapp = True
        args.virtual = True

    return args


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
