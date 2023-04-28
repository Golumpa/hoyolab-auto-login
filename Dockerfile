FROM python:3.10-alpine

ADD Pipfile Pipfile.lock hoyolab.py log.py request.py /
RUN apk update && pip install pipenv && pipenv install
ENV USING_DOCKER True
CMD ["pipenv", "run", "login"]
