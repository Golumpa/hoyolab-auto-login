FROM python:3.11-alpine

ADD Pipfile Pipfile.lock hoyolab.py /
RUN apk update && pip install pipenv && pipenv install
ENV USING_DOCKER True
CMD ["pipenv", "run", "login"]
