#!/bin/sh
export $(egrep -v '^#' .env | xargs)

django-admin startproject $PROJECT_NAME --template https://gitlab.com/newman99/django-project-template/-/archive/master/django-project-template-master.zip 

docker-compose build

sed -e "s/PROJECT_NAME/$PROJECT_NAME/g; s/S3_BUCKET/$S3_BUCKET/g" zappa_settings.sample.json > zappa_settings.json

exit 0
