FROM python:3.12-bookworm

ENV ACCEPT_EULA=Y

RUN apt-get update && apt-get install -y curl tcpdump net-tools vim unixodbc

RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && . /etc/os-release \
    && curl -fsSL "https://packages.microsoft.com/config/${ID}/${VERSION_ID}/prod.list" | tee /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18

WORKDIR /code

COPY ./agent/requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./agent /code/app

CMD ["fastapi", "run", "app/server.py", "--port", "80"]