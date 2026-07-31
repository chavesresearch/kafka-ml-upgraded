# pull official base image
FROM python:3.12-slim

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install dependencies
RUN pip install --upgrade pip
RUN pip install uv
COPY ./requirements.txt /usr/src/app/requirements.txt
# --prerelease=allow: web3 (blockchain feature) depends on a pre-release
# build of ipfshttpclient, same as the original backend's build flags.
RUN uv pip install -r requirements.txt --prerelease=allow --system

# copy project
COPY . /usr/src/app/

EXPOSE 8000

RUN chmod +x ./start.sh
CMD ["./start.sh"]
