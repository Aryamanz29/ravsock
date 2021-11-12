FROM python:3.8.12
ARG DEBIAN_FRONTEND=noninteractive

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . /
RUN python -m ensurepip --upgrade
RUN python -m pip install --upgrade pip

RUN pip install -r requirements.txt

EXPOSE 9999

CMD ["run_socket_server.py"]
ENTRYPOINT ["python"]