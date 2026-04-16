docker build -t levelup-copilot-maf .

docker stop levelup-copilot-maf
docker rm levelup-copilot-maf

docker run -d -p 3978:3978 --env-file .env --name levelup-copilot-maf levelup-copilot-maf
docker logs -f levelup-copilot-maf