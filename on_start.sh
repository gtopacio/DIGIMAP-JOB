#!/bin/bash
source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate 3DP # change to your conda environment's name
# -u: unbuffered output
python -u $HOME/digimap/DIGIMAP-JOB/server.py
