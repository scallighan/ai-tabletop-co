docker build -t graph-tagger-agent .

docker stop gta
docker rm gta

#docker run -d --env-file .env -p 8888:80 --name gta graph-tagger-agent
docker run -d -p 8888:80 --name gta graph-tagger-agent