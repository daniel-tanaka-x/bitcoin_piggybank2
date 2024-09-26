#!/bin/bash

# dca
source /home/daniel/myenv/bin/activate
cd /home/daniel
python dca.py
deactivate

# piggybank
source /home/daniel/venv/bin/activate
cd /home/daniel/
python piggybank.py
