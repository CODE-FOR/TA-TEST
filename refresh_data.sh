#!/bin/bash

find data/outbox -type f -exec rm -f {} \;
find data/inbox -type f -exec rm -f {} \;

python data_generator.py