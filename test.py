"""Test setup.py file."""
import unittest
import boto3
import placebo
from setup import create_env_file, create_zappa_settings


class TestSetup(unittest.TestCase):
    """Test setup.py file."""

    def testEnvFile(self):
        """Test create env file."""
        session = boto3.Session()
        env = create_env_file('project_name', 'name', 'email', session)
        self.assertEqual(env['PROJECT_NAME'], 'project_name')

    def testZappaFile(self):
        """Test create zappa settings file."""
        session = boto3.Session(profile_name="default")
        role_info = {
            'role_name': 'role_name',
            'subnet_ids': [],
            'security_group': 'sg'
        }
        zappa = create_zappa_settings('project_name', role_info, session)
        self.assertEqual(zappa['dev']['project_name'], 'project_name')

    def testCreateStack(self):
        """Test create AWS CloudFormation stack."""
        session = boto3.Session(profile_name="default")
        pill = placebo.attach(
            session,
            data_path='placebo'
        )
        pill.record()
        aws_lambda = session.client('lambda')
        aws_lambda.list_functions()
        foo = pill.playback()
        print(foo)


if __name__ == '__main__':
    unittest.main()
