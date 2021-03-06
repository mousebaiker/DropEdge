from __future__ import division
from __future__ import print_function

import os

import ipdb

import time
import argparse
import numpy as np

import torch
import torch.nn.functional as F
import torch.optim as optim
from tensorboardX import SummaryWriter

from earlystopping import EarlyStopping
from sample import Sampler
from metric import accuracy, roc_auc_compute_fn
# from deepgcn.utils import load_data, accuracy
# from deepgcn.models import GCN

from utils import load_citation, load_reddit_data
from models import *

np.seterr('ignore')

# Training settings
parser = argparse.ArgumentParser()
# Training parameter
parser.add_argument('--no_cuda', action='store_true', default=False,
                    help='Disables CUDA training.')
parser.add_argument('--fastmode', action='store_true', default=False,
                    help='Disable validation during training.')
parser.add_argument('--seed', type=int, default=42, help='Random seed.')
parser.add_argument('--epochs', type=int, default=800,
                    help='Number of epochs to train.')
parser.add_argument('--lr', type=float, default=0.02,
                    help='Initial learning rate.')
parser.add_argument('--lradjust', action='store_true',
                    default=False, help='Enable leraning rate adjust.(ReduceLROnPlateau or Linear Reduce)')
parser.add_argument('--weight_decay', type=float, default=5e-4,
                    help='Weight decay (L2 loss on parameters).')
parser.add_argument("--mixmode", action="store_true",
                    default=False, help="Enable CPU GPU mixing mode.")
parser.add_argument("--warm_start", default="",
                    help="The model name to be loaded for warm start.")
parser.add_argument('--debug', action='store_true',
                    default=False, help="Enable the detialed training output.")
parser.add_argument('--dataset', default="cora", help="The data set")
parser.add_argument('--datapath', default="data/", help="The data path.")
parser.add_argument("--early_stopping", type=int,
                    default=0, help="The patience of earlystopping. Do not adopt the earlystopping when it equals 0.")
parser.add_argument("--no_tensorboard", default=False, help="Disable writing logs to tensorboard")

# Model parameter
parser.add_argument('--type',
                    help="Choose the model to be trained.(mutigcn, resgcn, densegcn, inceptiongcn)")
parser.add_argument('--inputlayer', default='gcn',
                    help="The input layer of the model.")
parser.add_argument('--outputlayer', default='gcn',
                    help="The output layer of the model.")
parser.add_argument('--hidden', type=int, default=128,
                    help='Number of hidden units.')
parser.add_argument('--dropout', type=float, default=0.5,
                    help='Dropout rate (1 - keep probability).')
parser.add_argument('--withbn', action='store_true', default=False,
                    help='Enable Bath Norm GCN')
parser.add_argument('--withloop', action="store_true", default=False,
                    help="Enable loop layer GCN")
parser.add_argument('--nhiddenlayer', type=int, default=1,
                    help='The number of hidden layers.')
parser.add_argument("--normalization", default="AugNormAdj",
                    help="The normalization on the adj matrix.")
parser.add_argument("--sampling_percent", type=float, default=1.0,
                    help="The percent of the preserve edges. If it equals 1, no sampling is done on adj matrix.")
parser.add_argument("--baseblock", default="res", help="The base building block (resgcn, densegcn, mutigcn, inceptiongcn).")
parser.add_argument("--nbaseblocklayer", type=int, default=1,
                    help="The number of layers in each baseblock")
parser.add_argument("--aggrmethod", default="default",
                    help="The aggrmethod for the layer aggreation. The options includes add and concat. Only valid in resgcn, densegcn and inecptiongcn")
parser.add_argument("--task_type", default="full", help="The node classification task type (full and semi). Only valid for cora, citeseer and pubmed dataset.")
parser.add_argument("--init_func", default="", help="Initialization function from torch.nn.init. By default, scaled uniform is used.")
parser.add_argument("--skip_connections", action='store_true', default=False, help="Enable skip connections via concatenations.")
parser.add_argument("--experiment_name", default="", help="Name of the experiment. Used to create directories with results of experiments.")

args = parser.parse_args()
if args.debug:
    print(args)
# pre setting
args.cuda = not args.no_cuda and torch.cuda.is_available()
args.mixmode = args.no_cuda and args.mixmode and torch.cuda.is_available()
if args.aggrmethod == "default":
    if args.type == "resgcn":
        args.aggrmethod = "add"
    else:
        args.aggrmethod = "concat"
if args.fastmode and args.early_stopping > 0:
    args.early_stopping = 0
    print("In the fast mode, early_stopping is not valid option. Setting early_stopping = 0.")
if args.type == "mutigcn":
    print("For the multi-layer gcn model, the aggrmethod is fixed to nores and nhiddenlayers = 1.")
    args.nhiddenlayer = 1
    args.aggrmethod = "nores"

init_func = None
if args.init_func:
  init_func = getattr(torch.nn.init, args.init_func)

# random seed setting
np.random.seed(args.seed)
torch.manual_seed(args.seed)
if args.cuda or args.mixmode:
    torch.cuda.manual_seed(args.seed)

# should we need fix random seed here?
sampler = Sampler(args.dataset, args.datapath, args.task_type)

# get labels and indexes
labels, idx_train, idx_val, idx_test = sampler.get_label_and_idxes(args.cuda)
nfeat = sampler.nfeat
nclass = sampler.nclass
print("nclass: %d\tnfea:%d" % (nclass, nfeat))

# The model
model = None
if args.skip_connections:
  model = SkipGCN(nfeat=nfeat,
                   nhid=args.hidden,
                   nclass=nclass,
                   nhidlayer=args.nhiddenlayer,
                   dropout=args.dropout,
                   baseblock=args.type,
                   inputlayer=args.inputlayer,
                   outputlayer=args.outputlayer,
                   nbaselayer=args.nbaseblocklayer,
                   activation=F.relu,
                   withbn=args.withbn,
                   withloop=args.withloop,
                   aggrmethod=args.aggrmethod,
                   mixmode=args.mixmode,
                   init_func=init_func)
else:
  model = GCNModel(nfeat=nfeat,
                   nhid=args.hidden,
                   nclass=nclass,
                   nhidlayer=args.nhiddenlayer,
                   dropout=args.dropout,
                   baseblock=args.type,
                   inputlayer=args.inputlayer,
                   outputlayer=args.outputlayer,
                   nbaselayer=args.nbaseblocklayer,
                   activation=F.relu,
                   withbn=args.withbn,
                   withloop=args.withloop,
                   aggrmethod=args.aggrmethod,
                   mixmode=args.mixmode,
                   init_func=init_func)

optimizer = optim.Adam(model.parameters(),
                       lr=args.lr, weight_decay=args.weight_decay)

# scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=50, factor=0.618)
scheduler = optim.lr_scheduler.MultiStepLR(optimizer, milestones=[200, 300, 400, 500, 600, 700], gamma=0.5)
# convert to cuda
if args.cuda:
    model.cuda()

# For the mix mode, lables and indexes are in cuda.
if args.cuda or args.mixmode:
    labels = labels.cuda()
    idx_train = idx_train.cuda()
    idx_val = idx_val.cuda()
    idx_test = idx_test.cuda()

if args.warm_start is not None and args.warm_start != "":
    early_stopping = EarlyStopping(fname=args.warm_start, verbose=False)
    print("Restore checkpoint from %s" % (early_stopping.fname))
    model.load_state_dict(early_stopping.load_checkpoint())

# set early_stopping
if args.early_stopping > 0:
    early_stopping = EarlyStopping(patience=args.early_stopping, verbose=False)
    print("Model is saving to: %s" % (early_stopping.fname))

if args.no_tensorboard is False:
  logdir = None
  if args.experiment_name:
    logdir = f'runs/{args.experiment_name}-layers_{args.nbaseblocklayer}-seed_{args.seed}'
  tb_writer = SummaryWriter(
      logdir=logdir,
      comment=f"-dataset_{args.dataset}-type_{args.type}"
  )

def get_lr(optimizer):
    for param_group in optimizer.param_groups:
        return param_group['lr']


# define the training function.
def train(epoch, train_adj, train_fea, idx_train, val_adj=None, val_fea=None):
    if val_adj is None:
        val_adj = train_adj
        val_fea = train_fea

    t = time.time()
    model.train()
    optimizer.zero_grad()
    output = model(train_fea, train_adj)
    # special for reddit
    if sampler.learning_type == "inductive":
        loss_train = F.nll_loss(output, labels[idx_train])
        acc_train = accuracy(output, labels[idx_train])
    else:
        loss_train = F.nll_loss(output[idx_train], labels[idx_train])
        acc_train = accuracy(output[idx_train], labels[idx_train])

    loss_train.backward()
    optimizer.step()
    train_t = time.time() - t
    val_t = time.time()
    # We can not apply the fastmode for the reddit dataset.
    # if sampler.learning_type == "inductive" or not args.fastmode:

    grads = [np.linalg.norm(l.grad.cpu().numpy()) for l in model.midlayer[0].model.weights]
    norms = [np.linalg.norm(l.detach().cpu().numpy()) for l in model.midlayer[0].model.weights]
    # print("Grads:", grads)
    # print("Norms", norms)
    # print(np.array(norms)/np.array(grads))

    if args.early_stopping > 0 and sampler.dataset != "reddit":
        loss_val = F.nll_loss(output[idx_val], labels[idx_val]).item()
        early_stopping(loss_val, model)

    if not args.fastmode:
        #    # Evaluate validation set performance separately,
        #    # deactivates dropout during validation run.
        model.eval()
        output = model(val_fea, val_adj)
        loss_val = F.nll_loss(output[idx_val], labels[idx_val]).item()
        acc_val = accuracy(output[idx_val], labels[idx_val]).item()
        if sampler.dataset == "reddit":
            early_stopping(loss_val, model)
    else:
        loss_val = 0
        acc_val = 0

    if args.lradjust:
        scheduler.step()

    val_t = time.time() - val_t
    return (loss_train.item(), acc_train.item(), loss_val, acc_val, get_lr(optimizer), train_t, val_t, grads, norms)


def test(test_adj, test_fea):
    model.eval()
    output = model(test_fea, test_adj)
    loss_test = F.nll_loss(output[idx_test], labels[idx_test])
    acc_test = accuracy(output[idx_test], labels[idx_test])
    auc_test = roc_auc_compute_fn(output[idx_test], labels[idx_test])
    if args.debug:
        print("Test set results:",
              "loss= {:.4f}".format(loss_test.item()),
              "auc= {:.4f}".format(auc_test),
              "accuracy= {:.4f}".format(acc_test.item()))
        print("accuracy=%.5f" % (acc_test.item()))
    return (loss_test.item(), acc_test.item())


# Train model
t_total = time.time()
loss_train = np.zeros((args.epochs,))
acc_train = np.zeros((args.epochs,))
loss_val = np.zeros((args.epochs,))
acc_val = np.zeros((args.epochs,))
print(args.nbaseblocklayer)
grads = np.zeros((args.epochs, args.nbaseblocklayer))
norms = np.zeros((args.epochs, args.nbaseblocklayer))

sampling_t = 0

for epoch in range(args.epochs):
    input_idx_train = idx_train
    sampling_t = time.time()
    # no sampling
    # randomedge sampling if args.sampling_percent >= 1.0, it behaves the same as stub_sampler.
    (train_adj, train_fea) = sampler.randomedge_sampler(percent=args.sampling_percent, normalization=args.normalization,
                                                        cuda=args.cuda)
    if args.mixmode:
        train_adj = train_adj.cuda()

    sampling_t = time.time() - sampling_t

    # The validation set is controlled by idx_val
    # if sampler.learning_type == "transductive":
    if False:
        outputs = train(epoch, train_adj, train_fea, input_idx_train)
    else:
        (val_adj, val_fea) = sampler.get_test_set(normalization=args.normalization, cuda=args.cuda)
        if args.mixmode:
            val_adj = val_adj.cuda()
        outputs = train(epoch, train_adj, train_fea, input_idx_train, val_adj, val_fea)

    if args.debug and epoch % 1 == 0:
        print('Epoch: {:04d}'.format(epoch + 1),
              'loss_train: {:.4f}'.format(outputs[0]),
              'acc_train: {:.4f}'.format(outputs[1]),
              'loss_val: {:.4f}'.format(outputs[2]),
              'acc_val: {:.4f}'.format(outputs[3]),
              'cur_lr: {:.5f}'.format(outputs[4]),
              's_time: {:.4f}s'.format(sampling_t),
              't_time: {:.4f}s'.format(outputs[5]),
              'v_time: {:.4f}s'.format(outputs[6]))

    if args.no_tensorboard is False:
        tb_writer.add_scalars('Loss', {'train': outputs[0], 'val': outputs[2]}, epoch)
        tb_writer.add_scalars('Accuracy', {'train': outputs[1], 'val': outputs[3]}, epoch)
        tb_writer.add_scalar('lr', outputs[4], epoch)
        tb_writer.add_scalars('Time', {'train': outputs[5], 'val': outputs[6]}, epoch)
        norms_dict = dict()
        grads_dict = dict()
        for i in range(np.asarray(outputs[7]).shape[0]):
            norms_dict[str(i)] = outputs[8][i]
            grads_dict[str(i)] = outputs[7][i]
        tb_writer.add_scalars('Grads', grads_dict, epoch)
        tb_writer.add_scalars('Norms', norms_dict, epoch)
        norms_dict.clear()
        grads_dict.clear()

    loss_train[epoch], acc_train[epoch], loss_val[epoch], acc_val[epoch], grads[epoch,:], norms[epoch,:] = outputs[0], outputs[1], outputs[2], outputs[3], outputs[7], outputs[8]

    if args.early_stopping > 0 and early_stopping.early_stop:
        print("Early stopping.")
        model.load_state_dict(early_stopping.load_checkpoint())
        break


if args.early_stopping > 0:
    model.load_state_dict(early_stopping.load_checkpoint())

if args.debug:
    print("Optimization Finished!")
    print("Total time elapsed: {:.4f}s".format(time.time() - t_total))

# Testing
(test_adj, test_fea) = sampler.get_test_set(normalization=args.normalization, cuda=args.cuda)
if args.mixmode:
    test_adj = test_adj.cuda()
(loss_test, acc_test) = test(test_adj, test_fea)
print("%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f" % (
loss_train[-1], loss_val[-1], loss_test, acc_train[-1], acc_val[-1], acc_test))


loss_folder = os.path.join('losses', early_stopping.fname)
if args.experiment_name:
  loss_folder = os.path.join('losses', args.experiment_name, f'layers_{args.nbaseblocklayer}-seed_{args.seed}')

os.makedirs(loss_folder, exist_ok=True)

np.save(os.path.join(loss_folder, 'loss_train'), loss_train)
np.save(os.path.join(loss_folder, 'loss_test'), loss_test)
np.save(os.path.join(loss_folder, 'loss_val'), loss_val)
np.save(os.path.join(loss_folder, 'acc_train'), acc_train)
np.save(os.path.join(loss_folder, 'acc_val'), acc_val)
np.save(os.path.join(loss_folder, 'weight_norms'), grads)
np.save(os.path.join(loss_folder, 'grad_norms'), norms)
np.save(os.path.join(loss_folder, 'acc_test'), acc_test)
