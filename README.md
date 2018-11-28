# Zappa - Django - AWS - Lambda, RDS, S3

Create local and remote Django development environments in 20 minutes or less.

This project allows you to deploy a Django project on AWS using Lambda, RDS (PostgreSQL), and S3.
It also creates a local development environment using Docker.

This project is built using the following tools and libraries:
* [AWS](https://aws.amazon.com/) - Amazon Web Services
  * [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) - manage your AWS services from the command line
  * [CloudFormation](https://aws.amazon.com/cloudformation/) - model and provision all your cloud infrastructure resources
  * [Lambda](https://aws.amazon.com/lambda/) - run code without provisioning or managing servers
  * [API Gateway](https://aws.amazon.com/api-gateway/) - deliver robust, secure, and scalable mobile and web application backends
  * [S3](https://aws.amazon.com/s3/) - object storage built to store and retrieve any amount of data from anywhere
  * [RDS](https://aws.amazon.com/rds/) - set up, operate, and scale a relational database in the cloud with just a few clicks.
    * [PostgreSQL](https://www.postgresql.org/) - an object-relational database management system
* [botocore](https://github.com/boto/botocore) - the low-level, core functionality of boto 3
* [boto3](https://github.com/boto/boto3) - AWS SDK for Python
* [troposphere](https://github.com/cloudtools/troposphere) - Python library to create AWS CloudFormation descriptions
* [Docker](https://www.docker.com/) - a computer program that performs operating-system-level virtualization
* [Docker Compose](https://docs.docker.com/compose/install/) - a tool for defining and running multi-container Docker applications
* [Django](https://www.djangoproject.com/) - Python-based free and open-source web framework
  * [split_settings](https://github.com/sobolevn/django-split-settings) - organize Django settings into multiple files and directories
  * [decouple](https://github.com/henriquebastos/python-decouple/) - strict separation of settings from code
  * [django-s3-storage](https://github.com/etianen/django-s3-storage) - Django Amazon S3 file storage
* [Zappa](https://github.com/Miserlou/Zappa) - serverless Python
* [Click](https://click.palletsprojects.com/en/7.x/) - a Python package for creating beautiful command line interfaces
* [Git](https://git-scm.com/) - version control (optional)

## Getting Started


### Prerequisites

This project has only been tested with [Python 3](https://www.python.org/download/releases/3.0/).

An [AWS](https://aws.amazon.com/) account is required.
Install and configure [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html).

Install [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/).

Install boto3, botocore, click, urllib, and troposphere using pip:

```bash
pip install boto3 botocore click urllib troposphere```

Install [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) (optional).

### Installing

Download this project:

```bash
wget https://gitlab.com/newman99/zappa-django-postgres-aws/-/archive/master/zappa-django-postgres-aws-master.zip```

Unzip to the directory of your choice:

```bash
unzip zappa-django-postgres-aws-master.zip
```

Change the name of the unzipped directory to the name of your project:

```bash
mv zappa-django-postgres-aws-master project_name
```

Navigate to the new directory:

```bash
cd project_name
```

Initialize git repository (optional):

```bash
git init
```

## Deployment

Run the setup:

```bash
python3 setup.py project_name
```

And answer a few questions.

Your new development environments will be ready in about 20 minutes.

## Authors

* **Matthew Newman**

## License

This project is licensed under The Unlicense - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* [Zappa](https://github.com/Miserlou/Zappa)
* [Guide to using Django with Zappa](https://edgarroman.github.io/zappa-django-guide/)
