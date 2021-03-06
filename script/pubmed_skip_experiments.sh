#!/bin/bash

layers=(2 4 8 10 16)
for layer in "${layers[@]}"
do
  seeds=($RANDOM $RANDOM $RANDOM)
  echo "Random seeds" $seeds[0] $seeds[1] $seeds[2]
  start=`date +%s`
  for seed in "${seeds[@]}"
  do
    python ./src/train_new.py \
        --datapath data// \
        --seed $seed \
        --dataset pubmed \
        --type mutigcn \
        --nhiddenlayer 1 \
        --nbaseblocklayer $layer \
        --hidden 128 \
        --epoch 400 \
        --lr 0.01 \
        --weight_decay 0.001 \
        --early_stopping 400 \
        --sampling_percent 0.3 \
        --dropout 0.5 \
        --normalization BingGeNormAdj \
        --withloop \
        --withbn \
        --experiment_name pubmed_clean

    python ./src/train_new.py \
        --datapath data// \
        --seed $seed \
        --dataset pubmed \
        --type mutigcn \
        --nhiddenlayer 1 \
        --nbaseblocklayer $layer \
        --hidden 128 \
        --epoch 400 \
        --lr 0.01 \
        --weight_decay 0.001 \
        --early_stopping 400 \
        --sampling_percent 0.3 \
        --dropout 0.5 \
        --normalization BingGeNormAdj \
        --withloop \
        --withbn \
        --skip_connections \
        --experiment_name pubmed_skip

        python ./src/train_new.py \
            --datapath data// \
            --seed $seed \
            --dataset pubmed \
            --type mutigcn \
            --nhiddenlayer 1 \
            --nbaseblocklayer $layer \
            --hidden 128 \
            --epoch 400 \
            --lr 0.01 \
            --weight_decay 0.001 \
            --early_stopping 400 \
            --sampling_percent 0.3 \
            --dropout 0.5 \
            --normalization BingGeNormAdj \
            --withloop \
            --withbn \
            --skip_connections \
            --init_func orthogonal_ \
            --experiment_name pubmed_skip_init
    echo Seed ${seed} done.
  done
  end=`date +%s`
  echo Execution time was `expr $end - $start` seconds.
done
