# Zappa - Django - AWS - Lambda, RDS, S3

This project allows you to deploy a Django project on AWS using Lambda, RDS (PostgreSQL), and S3.

* [AWS](https://aws.amazon.com/)
  * [CloudFormation](https://aws.amazon.com/cloudformation/)
  * [Lambda](https://aws.amazon.com/lambda/)
  * [S3](https://aws.amazon.com/s3/)
  * [RDS](https://aws.amazon.com/rds/)
    * [PostgreSQL](https://www.postgresql.org/)
* [troposphere](https://github.com/cloudtools/troposphere)
* [Docker](https://www.docker.com/)
* [Docker Compose](https://docs.docker.com/compose/install/)
* [Django](https://www.djangoproject.com/)
  * [split_settings](https://github.com/sobolevn/django-split-settings)
  * [decouple](https://github.com/henriquebastos/python-decouple/)
  * [django-s3-storage](https://github.com/etianen/django-s3-storage)
* [Zappa](https://github.com/Miserlou/Zappa)

## Getting Started


### Prerequisites

[Python 3](https://www.python.org/download/releases/3.0/)

Install [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/).

Install boto3, botocore, click, urllib, and troposphere using pip:

`pip install boto3 botocore click urllib troposphere`

An [AWS](https://aws.amazon.com/) account.

### Installing

```wget https://gitlab.com/newman99/zappa-django-postgres-aws/-/archive/master/zappa-django-postgres-aws-master.zip```

`unzip zappa-django-postgres-aws-master.zip`

`mv zappa-django-postgres-aws-master project_name`

`cd project_name`

## Deployment

`python3 setup.py project_name`

## Authors

* **Matthew Newman**

## License

This project is licensed under The Unlicense - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* [Zappa](https://github.com/Miserlou/Zappa)
* [Guide to using Django with Zappa](https://edgarroman.github.io/zappa-django-guide/)
