#FROM python:3.6.4-alpine3.7 -- broken install of requirements, known kernel problem
FROM python:3.6.4-slim-jessie

LABEL maintainer="sysadmin@keitaro.com"

COPY . /app
WORKDIR /app

#RUN apt-get install -y python-dev python3-dev

RUN pip install -r requirements.txt

CMD ["python3", "/app/version-check/check.py"]
