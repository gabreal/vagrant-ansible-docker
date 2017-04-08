#!/bin/sh -e

APP_PATH="/srv/application"



apt-get update

# still need python-pip for consul
apt-get -y install curl python python-flask python-gevent python-pip python-pygresql
pip install python-consul


#TODO switch to unprivileged user

python ${APP_PATH}/server.py

