#!/usr/bin/python

import os
import sys
import numpy as np
from subprocess import call
from multiprocessing import Process


mu = 0.5  # service time of 2
mm116_lambdas = np.arange(0.5, 8.1, 0.2) # 16 servers average service time 2
duration = 1000000
intr_trhesholds = [2, 4, 10, 20]

GENTYPES = ['m', 'd', 'b', 'b2']  # exponential, deterministic, bimodal{1-2}
PROCTYPES = ['rtc', 'ps', 'push', 'pull', 'pull_intr']

def execute_topology(topo, lambdas, g, p, path, threshold=None):
    pathname = "{}/{}_{}.dat".format(path, PROCTYPES[p], GENTYPES[g])
    cmd = ["schedsim", "--mu={}".format(mu), "--duration={}".format(duration),
            "--topo={}".format(topo), "--genType={}".format(g)]
    if p:
        cmd.append("--procType={}".format(p))
    if threshold:
        cmd.append("--threshold={}".format(threshold))

    with open(pathname, 'w') as f:
        for l in lambdas:
            exec_cmd = cmd + ["--lambda={}".format(l)]
            call(exec_cmd, stdout=f)

def parallel_exec(args):
    '''
        args = [(topo, lambdas, genType, procType, path, <optinal threshold>)...]
    '''
    pids = []
    for run in args:
        p = Process(target=execute_topology, args=run)
        p.start()
        pids.append(p)
    for p in pids:
        p.join()

def single_queue():
    directory = "data/single_queue"
    if not os.path.exists(directory):
            os.makedirs(directory)
    genTypes = range(4) * 2
    pTypes = [0] * 4 + [1] * 4
    topologies = [0] * 8
    lambdas = [mm116_lambdas] * 8
    names = [directory] * 8
    parallel_exec(zip(topologies, lambdas, genTypes, pTypes, names))

def multi_queue():
    directory = "data/multi_queue"
    if not os.path.exists(directory):
            os.makedirs(directory)
    genTypes = range(4) * 2
    pTypes = [0] * 4 + [1] * 4
    topologies = [1] * 8
    lambdas = [mm116_lambdas] * 8
    names = [directory] * 8
    parallel_exec(zip(topologies, lambdas, genTypes, pTypes, names))

def main():
    if len(sys.argv) != 2:
        print "Usage: python run.py <function_name>"
        return
    if sys.argv[1] == "single_queue":
        single_queue()
    elif sys.argv[1] == "multi_queue":
        multi_queue()
    else:
        print "Unknown function name"

if __name__ == "__main__":
    main()
