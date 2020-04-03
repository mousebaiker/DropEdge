import glob
import os

import numpy as np
import pandas as pd

def get_accuracy_paths(loss_dir, dataset, init, layer):
  prefix = os.path.join(loss_dir, dataset + "_" + init, "layers_" + str(layer))
  suffix = 'acc_test.npy'
  return glob.glob(os.path.join(prefix + '*', suffix))

def build_frame(aggr_func, accuracies, datasets, inits, layers):
  frame = pd.DataFrame(index=layers)
  for dataset in datasets:
    for init in inits:
      name = dataset + "_" + init
      values = []
      for layer in layers:
        values.append(aggr_func(accuracies[dataset][init][layer]))
      frame[name] = values

  return frame

def get_frames():
    loss_dir = 'losses'
    datasets = ['citeseer', 'cora', 'pubmed']
    inits = ['init', 'no_init']
    layers = [2, 4, 8, 10, 16]

    accuracies  = {}
    for dataset in datasets:
      accuracies[dataset] = {}
      for init in inits:
        accuracies[dataset][init] = {}
        for layer in layers:
          accuracies[dataset][init][layer] = []
          paths = get_accuracy_paths(loss_dir, dataset, init, layer)
          for path in paths:
            accuracies[dataset][init][layer].append(np.load(path))
    functions = [np.max, np.mean, np.median, np.std]
    frames = []
    for func in functions:
      frames.append(build_frame(func, accuracies, datasets, inits, layers))
    return frames
def main():
  func_names = ['Max:', 'Average:', 'Median:', 'Std:']
  frames = get_frames()
  for i in range(len(func_names)):
    print(func_names[i])
    print(frames[i])


if __name__ == '__main__':
  main()
