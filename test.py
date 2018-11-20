import unittest
import botocore
from pathlib import Path
from setup import create_env_file

class TestSomething(unittest.TestCase):
    def testIt(self):
        session = botocore.session.Session()
        env = create_env_file('project_name', 'name', 'email', session) 
        self.assertEqual(env['PROJECT_NAME'], 'project_name')

if __name__ == '__main__':
    unittest.main()
