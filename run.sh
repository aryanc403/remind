#!/bin/bash

# Get to a predictable directory, the directory of this script
cd "$(dirname "$0")"

while true; do

#    git pull
#    pip install -r requirements.txt
    python -m remind
    (( $? != 42 )) && break

    echo '==================================================================='
    echo '=                       Restarting                                ='
    echo '==================================================================='
done
