#!/bin/bash

docker stop ta
docker image rm ta
docker build -t ta .
docker run --rm -d --name ta -v ~/SourceCode/TA-test/data:/app/data ta