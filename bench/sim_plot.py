#!/usr/bin/env python3

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))
if os.getlogin() == 'prekas':
  PAPERDIR = '/home/prekas/paper/'
elif os.getlogin() == 'marioskogias':
  PAPERDIR = "/Users/marioskogias/epfl/ix-papers/papers/sosp2017/"

def parse_file(fname):
    # print fname
    res = []
    with open(fname, 'r') as f:
        l = f.readline()
        while l:
            l = f.readline()
            data = l.split("\t")
            cores = int(data[0].split(":")[1])
            mu = float(data[1].split(":")[1])
            intr_lambda = float(data[0].split(":")[1])

            l = f.readline() # skip the collector name
            l = f.readline() # skip label
            l = f.readline()
            tmp = l.split("\t")

            avg = float(tmp[2])
            p50 = float(tmp[4])
            p90 = float(tmp[5])
            p95 = float(tmp[6])
            p99 = float(tmp[7])
            qps = float(tmp[8])

            # compute rho
            res.append((cores, mu, intr_lambda, qps, avg, p50, p90, p95, p99))

            l = f.readline()
    return res

def plot_data(data, name, p, f=None):
    cores, mu, intr_lambda, qps, avg, p50, p90, p95, p99 = zip(*data)

    if p == "avg":
        to_plot = avg
    elif p == 50:
        to_plot = p50
    elif p == 90:
        to_plot = p90
    elif p == 95:
        to_plot = p95
    elif p == 99:
        to_plot = p99

    # Assuming mu and cores are always the same
    cores = cores[0]
    mu = mu[0]

    y = list(map(lambda a: a*mu, to_plot))
    x = list(map(lambda a: a/(cores*mu), qps))
    if f:
        #f.plot(x, y, label="{} {}".format(name, p))
        f.plot(x, y, label="{}".format(name))
    else:
        #plt.plot(x, y, label="{} {}".format(name, p))
        plt.plot(x, y, label="{}".format(name))

def plot_togather():
    # subfigures
    #systems = ["16mg1_ps", "16mg1", "mg16", "mg16_ps"]
    systems = ["multi_queue/ps", "multi_queue/rtc", "single_queue/rtc", "single_queue/ps"]
    distributions = ['d', 'm', 'b', 'b2']
    labels = ['16xM/G/1/PS', '16xM/G/1/FCFS', 'M/G/16/FCFS', 'M/G/16/PS']
    percentile = 99
    ylabel_width = 0.15
    for i, distribution in enumerate(distributions):
        width = (7 - ylabel_width) / 4
        if i == 0:
            width += ylabel_width
        fig, ax = plt.subplots(1, 1, figsize=(width,1.8))
        ax.set_xlabel("Load", fontsize=6)
        ax.set_ylim([0,15])
        for j, s in enumerate(systems):
            data = parse_file(SCRIPTDIR + "/data/{}_{}.dat".format(s, distribution))
            plot_data(data,labels[j], percentile, ax)
        if i == 0:
            ax.set_ylabel('Latency', fontsize=6)
        plt.tick_params(labelsize=6)
        plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
        plt.savefig(PAPERDIR + 'figs/sim-{}.eps'.format(distribution))
    fig_legend = plt.figure(figsize=(6.67,0.2))
    fig_legend.legend(*ax.get_legend_handles_labels(), loc='center', ncol=9, fontsize=6)
    plt.savefig(PAPERDIR + 'figs/sim-key.eps')

def main():
    matplotlib.rcParams['ps.useafm'] = True
    plot_togather()

if __name__ == "__main__":
    main()
