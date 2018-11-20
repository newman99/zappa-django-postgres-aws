# Zappa - Django - AWS - Lambda, RDS, S3

This project allows you to deploy a Django project on AWS using Lambda, RDS (PostgreSQL), and S3.

## Getting Started


### Prerequisites

Install [Docker](https://www.docker.com/get-started).

Install boto3, botocore, click, urllib, troposphere:

`pip install boto3 botocore click urllib troposphere`

### Installing

```wget https://gitlab.com/newman99/zappa-django-postgres-aws/-/archive/master/zappa-django-postgres-aws-master.zip```

`unzip zappa-django-postgres-aws-master.zip`

`cd zappa-django-postgres-aws-master.zip`

## Deployment

`python3 setup.py project_name`

## Authors

* **Matthew Newman**

## License

This project is licensed under The Unlicense - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* [Zappa](https://github.com/Miserlou/Zappa)
