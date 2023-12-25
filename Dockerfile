FROM python:3.11-alpine as base

RUN apk update && pip install --upgrade pip && \
	adduser -D -h /home/autologin -g 'HAL' autologin

WORKDIR /home/autologin

FROM base as builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN apk add build-base libffi-dev && \
	pip install -U poetry

COPY --chown=autologin:autologin poetry.lock pyproject.toml /home/autologin/

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --no-root

FROM base as runtime

ENV VIRTUAL_ENV=/home/autologin/.venv \
    PATH="/home/autologin/.venv/bin:$PATH"

COPY --from=builder --chown=autologin:autologin ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY --chown=autologin:autologin . .

USER autologin

CMD ["python", "hoyolab.py"]