#!/bin/sh
export $(egrep -v '^#' .env | xargs)
AWS_REGION=$(egrep region ~/.aws/config | cut -d '=' -f2)

S3_BUCKET="zappa-"`cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 9 | head -1`

sed -e "s/PROJECT_NAME/$PROJECT_NAME/g; s/S3_BUCKET/$S3_BUCKET/g; s/AWS_REGION/$AWS_REGION/g; s/SUBNET_ID/$SUBNET_ID/g; s/SECURITY_GROUP_ID/$SECURITY_GROUP_ID/g" zappa_settings.sample.json > zappa_settings.json

django-admin startproject $PROJECT_NAME --template https://gitlab.com/newman99/django-project-template/-/archive/master/django-project-template-master.zip 

docker-compose build

exit 0
