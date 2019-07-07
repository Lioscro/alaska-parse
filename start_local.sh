#!/bin/bash
# Script to easily start local server.
source environment.env

docker pull --all-tags lioscro/alaska

docker-compose up
