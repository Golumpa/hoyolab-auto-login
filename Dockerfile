FROM python:3.10-alpine as py

FROM py as build

COPY requirements.txt /
RUN apk update && pip install --prefix=/inst -U -r /requirements.txt

FROM py

COPY --from=build /inst /usr/local

WORKDIR /script
CMD ["python", "hoyolab.py"]
COPY . /script