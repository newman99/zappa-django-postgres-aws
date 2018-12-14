"""Test setup.py file."""
import unittest
import boto3
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
        session = boto3.Session()
        role_info = {
            'role_name': 'role_name',
            'subnet_ids': [],
            'security_group': 'sg'
        }
        zappa = create_zappa_settings('project_name', role_info, session)
        self.assertEqual(zappa['dev']['project_name'], 'project_name')


if __name__ == '__main__':
    unittest.main()
