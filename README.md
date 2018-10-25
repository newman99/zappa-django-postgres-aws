`wget https://gitlab.com/newman99/zappa-django-postgres-aws/-/archive/master/zappa-django-postgres-aws-master.zip`

`unzip zappa-django-postgres-aws-master.zip`

`cd zappa-django-postgres-aws-master.zip`

`cp env.example .env`

Enter the values in the .env file.

`sh ./setup.sh`

`docker-compose up -d`

`docker-compose exec web bash`

`cd $PROJECT_NAME`

`./manage.py makemigrations`

`./manage.py migrate`

`./manage.py createsuperuser`

`zappa deploy $ZAPPA_DEPLOYMENT_TYPE`
