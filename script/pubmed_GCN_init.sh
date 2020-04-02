#!/bin/bash

python ./src/train_new.py \
    --debug \
    --datapath data// \
    --seed 23423 \
    --dataset pubmed \
    --type mutigcn \
    --nhiddenlayer 1 \
    --nbaseblocklayer 7 \
    --hidden 10 \
    --epoch 400 \
    --lr 0.01 \
    --weight_decay 0.001 \
    --early_stopping 400 \
    --sampling_percent 0.3 \
    --dropout 0.5 \
    --normalization BingGeNormAdj \
    --withloop \
    --withbn \
    --init_func orthogonal_
