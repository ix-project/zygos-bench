#!/usr/bin/env python3
# encoding: utf-8

from io import StringIO
import functools
import glob
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import re
import sys

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))
BASEDIR = SCRIPTDIR + '/results'
if os.getlogin() == 'prekas':
  PAPERDIR = '/home/prekas/paper/'
elif os.getlogin() == 'prekageo':
  PAPERDIR = '/mnt/d/home/prekageo/paper/'
elif os.getlogin() == 'marioskogias':
  PAPERDIR = "/Users/marioskogias/epfl/ix-papers/papers/sosp2017/"

CORES=16

metrics = {
  'QPS_TARGET': { 'mutilate_continuous': 13 },
  'QPS': {'mutilate': 2,  'mutilate_continuous': 12, 'kernel': 2,  'sim': 1},
  'AVG': {'mutilate': 3,  'mutilate_continuous': 3,  'kernel': 13, 'sim': 2},
  'MIN': {'mutilate': 5,  'mutilate_continuous': -1, 'kernel': -1, 'sim': -1},
  'P90': {'mutilate': 9,  'mutilate_continuous': 9,  'kernel': -1, 'sim': 4},
  'P95': {'mutilate': 10, 'mutilate_continuous': 10,  'kernel': -1, 'sim': 5},
  'P99': {'mutilate': 11, 'mutilate_continuous': 11, 'kernel': 27, 'sim': 6},
}

def arr_from_str(input):
  ret = []
  max_columns = 0
  for line in input.splitlines():
    ret.append([])
    columns = 0
    for word in line.split():
      columns += 1
      try:
        v = float(word)
      except ValueError:
        v = 0
      ret[-1].append(v)
    max_columns = max(max_columns, columns)
  for row in ret:
    while len(row) < max_columns:
      row.append(0)
  return np.asarray(ret)

def get_xy_sim2(metric, svc_time_src, svc_time_dst, filename):
  arr = arr_from_str(open(filename).read())
  scale = svc_time_dst / float(svc_time_src)
  x = arr[:, 0] / scale / 1e6
  y = arr[:, metrics[metric]['sim'] - 1] * scale
  return x, y

def cmd_mutilate(x):
  ret = []
  f = open('%(x)s/results.mutilate' % { 'x': x })
  for line in f:
    parts = line.split()
    if '# start_time' in line:
      return np.asarray([])
    elif '==' in line:
      qps = parts[2]
    elif 'read' in line:
      lat = parts[1:]
    elif 'Total' in line:
      ach = parts[3]
      ret.append(list(map(float, [qps, ach] + lat)))
  f.close()
  ret.sort()
  return np.asarray(ret)

def filter_spikes(x, y):
  while True:
    delete = []
    for i in range(len(x) - 1):
      if y[i+1] > 0 and y[i+1] < 1000 and (y[i+1] - y[i]) / y[i] < -0.05:
        delete.append(i)
    if len(delete) == 0:
      break
    x = np.delete(x, delete)
    y = np.delete(y, delete)
  return x, y

def get_xy(cmd, dir, column, xscale = 1e6, yscale = 1):
  arr = eval(cmd)(dir)
  try:
    x = arr[:, 1] / xscale
    y = arr[:, column - 1] / yscale
  except IndexError:
    return np.array([]), np.array([])

  x, y = filter_spikes(x, y)

  return x, y

def get_xy_continuous(filename, column, filter = True):
  arr = arr_from_str(open(filename).read())
  d = {}
  x = []
  y = []
  for i in range(arr.shape[0]):
    if arr[i,metrics['QPS']['mutilate_continuous'] - 1] == 0:
      continue
    qps_target = arr[i,metrics['QPS_TARGET']['mutilate_continuous'] - 1]
    if qps_target not in d:
      d[qps_target] = []
    d[qps_target].append((arr[i, metrics['QPS']['mutilate_continuous'] - 1], arr[i,column - 1]))
  for i in sorted(d):
    d[i].sort(key=lambda x:x[1])
    x0, y0 = d[i][int(len(d[i]) / 2)]
    x.append(x0/1e3)
    y.append(y0)
  if filter:
    x, y = filter_spikes(x, y)
  return x, y

MARKERS = ['.', '+', 'x', '*', '^', 'o']
MARKERSIZE = [5, 5, 5, 5, 3, 5]
SYSTEMS = ['IX', 'ZygOS', 'ZygOS (no interrupts)', 'Linux (floating connections)', 'Linux (partitioned connections)', 'Linux (floating connections - exclusive)']
COLORS = ['b', 'g', 'orange', 'c', 'm', 'r']
CONFIG_PLOT = {it[0]:{'color': it[1], 'marker': it[2], 'linestyle': None, 'markersize': it[3]} for it in zip(SYSTEMS, COLORS, MARKERS, MARKERSIZE)}
SLO_MULTIPLIER = 10
MICROB_PERC = 'P99'
SILO_PERC = 'P99'

def calc_max_load_from_simulation(filename, latency):
  svc_time = 2
  for line in open(SCRIPTDIR + '/' + filename).readlines():
    if line[0] == '#':
      continue
    line = list(map(float, line.split()))
    if line[metrics[latency]['sim'] - 1] < svc_time * SLO_MULTIPLIER:
      max_throughput = line[metrics['QPS']['sim'] - 1]
  return max_throughput / (16e6 / svc_time)

def get_max_throughput_under_slo(graph, latency, distribution, svc_time):
  try:
    try:
      x, y = get_xy_continuous(graph % (distribution, svc_time)+'/results.mutilate', metrics[latency]['mutilate'])
      x = np.asarray(x)
      y = np.asarray(y)
      x /= 1e3
    except:
      x, y = get_xy('cmd_mutilate', graph % (distribution, svc_time), metrics[latency]['mutilate'])
  except FileNotFoundError:
    x = np.asarray([])
    y = np.asarray([])
  max_throughput = 0
  for j in range(len(x)):
    if y[j] != 0 and y[j] < svc_time * SLO_MULTIPLIER:
      max_throughput = x[j] / (CORES / svc_time)
  return max_throughput

def get_svc_time_vs_throughput_sla_xy(graph, latency, distribution, svc_times):
  max_throughput = {}
  for svc_time in svc_times:
    max_throughput[svc_time] = get_max_throughput_under_slo(graph, latency, distribution, svc_time)

  if len(max_throughput) == 0:
    return (0,0)
  return np.transpose(sorted(max_throughput.items()))

def get_svc_time_vs_throughput_sla_axis(svc_times, labels, graphs, ax, latency, distribution = 'exponential'):
  ax.set_xlabel('Service time (µs)')

  if distribution == 'exponential':
    mm1x16_load = calc_max_load_from_simulation('16xMM1.txt', latency)
    mm16_load = calc_max_load_from_simulation('MM16.txt', latency)
    ax.axhline(mm16_load, linestyle = '--', label = 'M/M/16', color = '#cccccc')
    ax.axhline(mm1x16_load, linestyle = '--', label = '16xM/M/1', color = '#888888')
  elif distribution == 'fixed':
    mm1x16_load = calc_max_load_from_simulation('16xMD1.txt', latency)
    mm16_load = calc_max_load_from_simulation('MD16.txt', latency)
    ax.axhline(mm16_load, linestyle = '--', label = 'M/D/16', color = '#cccccc')
    ax.axhline(mm1x16_load, linestyle = '--', label = '16xM/D/1', color = '#888888')
  elif distribution == 'bimodal90linear':
    mm1x16_load = calc_max_load_from_simulation('16xMB1.txt', latency)
    mm16_load = calc_max_load_from_simulation('MB16.txt', latency)
    ax.axhline(mm16_load, linestyle = '--', label = 'M/G/16/FCFS', color = '#cccccc')
    ax.axhline(mm1x16_load, linestyle = '--', label = '16xM/G/1/FCFS', color = '#888888')
  elif distribution == 'bimodal99linear':
    mm1x16_load = calc_max_load_from_simulation('16xMB21.txt', latency)
    mm16_load = calc_max_load_from_simulation('MB216.txt', latency)
    ax.axhline(mm16_load, linestyle = '--', label = 'M/G/16/FCFS', color = '#cccccc')
    ax.axhline(mm1x16_load, linestyle = '--', label = '16xM/G/1/FCFS', color = '#888888')

  graphs = [BASEDIR + '/' + graph for graph in graphs]
  for i, graph in enumerate(graphs):
    x, y = get_svc_time_vs_throughput_sla_xy(graph, latency, distribution, svc_times)
    ax.plot(x, y, label = labels[i], marker = CONFIG_PLOT[labels[i]]['marker'], color = CONFIG_PLOT[labels[i]]['color'], markersize=CONFIG_PLOT[labels[i]]['markersize'], linestyle=CONFIG_PLOT[labels[i]]['linestyle'])
  ax.set_xlim(xmin = 0)
  ax.set_ylim([0, 1])
  return ax

def __plot_svc_time_vs_throughput_sla(x, labels, graphs, suffix, motivation, latency):
  ylabel_width = 0.15
  if latency != MICROB_PERC:
    suffix += '-' + latency
  for i, distribution in enumerate(['fixed', 'exponential', 'bimodal90linear']):
    width = (7 - ylabel_width) / 3
    if i == 0:
      width += ylabel_width
    fig, ax = plt.subplots(1, 1, figsize=(width,2))
    get_svc_time_vs_throughput_sla_axis(x, labels, graphs, ax, latency, distribution = distribution)
    if i == 0:
      ax.set_ylabel('Load')
    if motivation:
      ax.set_xlim(xmax = 200)
    plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
    plt.savefig(PAPERDIR + 'figs/svc-time-vs-throughput-sla%s%s-%s%s.eps' % ('-mot' if motivation else '', '-%d' % max(x) if not motivation and max(x) != 500 else '', distribution, suffix))
  fig_legend = plt.figure(figsize=(6.67,0.2))
  fig_legend.legend(*ax.get_legend_handles_labels(), loc='center', ncol=9)
  plt.savefig(PAPERDIR + 'figs/svc-time-vs-throughput-sla%s-key%s.eps' % ('-mot' if motivation else '', suffix), bbox_inches='tight')

def calc_cdf(tuples, CCDF = False):
  cdf = {}
  total = 0
  prv_svc_time = -1
  for count, svc_time in tuples:
    assert svc_time > prv_svc_time, (svc_time, prv_svc_time)
    prv_svc_time = svc_time
    total += count
    cdf[svc_time] = total
  for svc_time in cdf:
    cdf[svc_time] /= 1.0 * total
    if CCDF:
      cdf[svc_time] = 1.0 - cdf[svc_time]
  return cdf

def get_silo_service_times():
  svc_times = {-1: [(0,0)], 0: [], 1: [], 2: [], 3: [], 4: []}
  for line in open('silo/silo-tpcc-service-times-v2.txt').readlines():
    count, svc_time, transaction = map(int, line.split())
    svc_times[transaction].append((count, svc_time))
    if svc_times[-1][-1][1] == svc_time:
      svc_times[-1][-1][0] += count
    else:
      svc_times[-1].append([count, svc_time])
  return svc_times

def read_stats(filename):
  ret = {}
  if not os.path.exists(filename):
    print('%s: Not found' % filename, file=sys.stderr)
    return ret
  for line in open(filename).readlines():
    parts = line.split()
    qps = int(parts[0])
    if qps not in ret:
      ret[qps] = {}
    if ' avg ' in line:
      ret[qps][parts[1]] = float(parts[5])
    else:
      ret[qps][parts[1]] = float(parts[3])
  return ret

def get_steals_vs_throughput(graph, normalized):
  stats = read_stats('%s/%s/results.stats' % (BASEDIR, graph))
  real_thoughputs, _ = get_xy_continuous('%s/%s/results.mutilate' % (BASEDIR, graph), metrics['P99']['mutilate'], filter=False)
  x = []
  y = []
  for i, qps in enumerate(sorted(stats)[:-1]):
    x.append(real_thoughputs[i] / 1e3)
    if normalized:
      if stats[qps]['events'] != 0:
        y.append(stats[qps]['steals'] / stats[qps]['events'])
      else:
        y.append(0)
    else:
      y.append(stats[qps]['steals'] / 5e3)
  return x, y

def plot_latency_vs_load_real_system(svc_time, latency = MICROB_PERC):
  graphs = []
  labels = ['Linux (floating connections)', 'IX',  'ZygOS (no interrupts)', 'ZygOS']
  graphs = ['linux-tcp-busypoll0-epollall-maxevents1-%s-%d', 'ix-batch1-%s-%d', 'zygos-batch64-%s-%d', 'zygos-batch64-interrupts-%s-%d']
  graphs = [BASEDIR + '/' + graph for graph in graphs]
  ylabel_width = 0.15
  suffix = ''
  if latency != MICROB_PERC:
    suffix += '-' + latency
  for i, distribution in enumerate(['fixed', 'exponential', 'bimodal90linear']):
    width = (6.67 - ylabel_width) / 3
    if i == 0:
      width += ylabel_width
    fig, ax = plt.subplots(1, 1, figsize=(width,2))
    slo_latency = svc_time * SLO_MULTIPLIER
    ax.axhline(slo_latency, 0, 2, linestyle = '--', color = '#cccccc', label='SLO')
    ax.set_xlabel('Throughput (MRPS)')
    ax.set_ylim([0, slo_latency * 1.5])

    for j, graph in enumerate(graphs):
      try:
        try:
          x, y = get_xy_continuous(graph % (distribution, svc_time)+'/results.mutilate', metrics[latency]['mutilate'])
          x = np.asarray(x) / 1e3
        except:
          x, y = get_xy('cmd_mutilate', graph % (distribution, svc_time), metrics[latency]['mutilate'])
      except FileNotFoundError:
        print('failed ' + graph % (distribution, svc_time)+'/results.mutilate')
        x = []
        y = []
      ax.plot(x, y, label = labels[j], marker = CONFIG_PLOT[labels[j]]['marker'], color = CONFIG_PLOT[labels[j]]['color'], markersize=CONFIG_PLOT[labels[j]]['markersize'])
    if distribution == 'fixed':
      x, y = get_xy_sim2(latency, 2, svc_time, SCRIPTDIR + '/MD16.txt')
      ax.plot(x[1:], y[1:], label = "Theoretical M/G/16/FCFS", color='k', linewidth=1)
    if distribution == 'exponential':
      x, y = get_xy_sim2(latency, 2, svc_time, SCRIPTDIR + '/MM16.txt')
      ax.plot(x[1:], y[1:], label = "Theoretical M/G/16/FCFS", color='k', linewidth=1)
    if distribution == 'bimodal90linear':
      x, y = get_xy_sim2(latency, 2, svc_time, SCRIPTDIR + '/MB16.txt')
      ax.plot(x[1:], y[1:], label = "Theoretical M/G/16/FCFS", color='k', linewidth=1)
    ax.set_xlim(xmin = 0)
    if i == 0:
      ax.set_ylabel('Latency (µs)')
    plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
    plt.savefig(PAPERDIR + 'figs/latency-vs-load-real-system-%s-%d%s.eps' % (distribution, svc_time, suffix))
  fig_legend = plt.figure(figsize=(6.67,0.2))
  fig_legend.legend(*ax.get_legend_handles_labels(), loc='center', ncol=9)
  plt.savefig(PAPERDIR + 'figs/latency-vs-load-real-system-key.eps')

def plot_svc_time_vs_throughput_sla(x, motivation = False, latency = MICROB_PERC):
  if motivation:
    labels = ['Linux (floating connections)', 'IX', 'Linux (partitioned connections)']
    graphs = ['linux-tcp-busypoll0-epollall-maxevents1-%s-%d', 'ix-batch1-%s-%d', 'linux-tcp-busypoll0-epolloriginal-maxevents1-%s-%d']
  else:
    labels = [ 'ZygOS', 'Linux (floating connections)','IX', 'Linux (partitioned connections)']
    graphs = ['zygos-batch64-interrupts-%s-%d', 'linux-tcp-busypoll0-epollall-maxevents1-%s-%d', 'ix-batch1-%s-%d', 'linux-tcp-busypoll0-epolloriginal-maxevents1-%s-%d']
  __plot_svc_time_vs_throughput_sla(x, labels, graphs, '', motivation, latency)

def plot_silo_latency_vs_load(latency = SILO_PERC):
  fig, ax = plt.subplots(1, 1, figsize=(3.33,2))
  ax.set_xlabel('Throughput (KRPS)')
  ax.set_ylabel('Latency (µs)')
  ax.set_xlim([0, 400])
  ax.set_ylim([0, 1500])
  suffix = ''
  if latency != SILO_PERC:
    suffix += '-' + latency

  CONFIG_PLOT['Linux'] = CONFIG_PLOT['Linux (floating connections)']
  labels = ['Linux', 'IX', 'ZygOS']
  graphs = ['linux-tcp-busypoll0-epollall-maxevents1-connections2720-silo-tpcc', 'ix-batch64-connections2720-silo-tpcc', 'zygos-batch64-connections2720-interrupts-silo-tpcc']
  graphs = [BASEDIR + '/' + graph for graph in graphs]
  ax.axhline(1000, linestyle = '--', color = '#cccccc', label='SLO')
  for i, graph in enumerate(graphs):
    try:
      x, y = get_xy('cmd_mutilate', graph, metrics[latency]['mutilate'])
      x *= 1e3
      if len(x) < 1:
        x, y = get_xy_continuous(graph+'/results.mutilate', metrics[latency]['mutilate'])
    except FileNotFoundError:
      continue
    except IndexError:
      continue
    ax.plot(x, y, label = labels[i], marker = CONFIG_PLOT[labels[i]]['marker'], color = CONFIG_PLOT[labels[i]]['color'], markersize=CONFIG_PLOT[labels[i]]['markersize'], linestyle = CONFIG_PLOT[labels[i]]['linestyle'])
  ax.legend()
  plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
  plt.savefig(PAPERDIR + 'figs/silo-latency-vs-load%s.eps' % (suffix,))

def plot_steals_vs_throughput(normalized = False):
  fig, ax = plt.subplots(1, 1, figsize=(3.33,2))
  ax.set_xlabel('Throughput (MRPS)')
  if normalized:
    ax.set_ylabel('Steals / event (%)')
  else:
    ax.set_ylabel('Steals (x 10^3 / second)')

  labels = ['ZygOS', 'ZygOS (no interrupts)']
  graphs = ['zygos-batch64-interrupts-exponential-25', 'zygos-batch64-exponential-25']
  for i, graph in enumerate(graphs):
    x, y = get_steals_vs_throughput(graph, normalized)
    y = list(map(lambda x: x*100, y))
    ax.plot(x, y, label = labels[i], marker = CONFIG_PLOT[labels[i]]['marker'], color=CONFIG_PLOT[labels[i]]['color'], markersize=CONFIG_PLOT[labels[i]]['markersize'])
  ax.legend()
  plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
  plt.savefig(PAPERDIR + 'figs/steals-vs-throughput%s.eps' % ('-normalized' if normalized else ''))

def plot_silo_service_time(CCDF, logx = False):
  fig, ax = plt.subplots(1, 1, figsize=(3.33,2))
  ax.set_xlabel('Service time (µs)')
  if CCDF and not logx:
    ax.set_ylabel('CCDF')
    ax.set_xlim(xmax = 550)
    ax.set_ylim(ymin = 1e-4)
  elif CCDF and logx:
    ax.set_ylabel('CCDF')
    ax.set_xlim([0, 50000])
    ax.set_xlim(xmin = 0)
    ax.set_ylim(ymin = 0)
  else:
    ax.set_ylabel('CDF')
    ax.set_xlim([0, 300])
    ax.set_xlim(xmin = 0)
    ax.set_ylim(ymin = 0)

  ax.axhline(1 - 0.99, linestyle = '--', color = '#cccccc', label='99th percentile')
  ids = [3,1,0,4,2,-1]
  names = ['OrderStatus', 'Payment', 'NewOrder', 'StockLevel', 'Delivery', 'Mix']
  color = ['r', 'b', 'g', 'c', 'm', 'k']
  svc_times = get_silo_service_times()
  for i, id in enumerate(ids):
    cdf = calc_cdf(svc_times[id], CCDF)
    x, y = np.transpose(sorted(cdf.items()))
    if CCDF and not logx:
      ax.semilogy(x, y, '', label=names[i], color=color[i])
    elif CCDF and logx:
      ax.loglog(x, y, '', label=names[i], color=color[i])
    else:
      ax.plot(x, y, '', label=names[i], color=color[i])
  plt.legend()
  plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
  if CCDF and not logx:
    plt.savefig(PAPERDIR + 'figs/silo-service-time-ccdf.eps')
  elif CCDF and logx:
    plt.savefig(PAPERDIR + 'figs/silo-service-time-ccdf-logx.eps')
  else:
    plt.savefig(PAPERDIR + 'figs/silo-service-time.eps')

def plot_memcached():
  graphs = []
  graphs.append('linux-memcached-%s')
  graphs.append('ix-batch1-memcached-%s')
  graphs.append('zygos-batch64-interrupts-memcached-%s')
  graphs.append('ix-batch64-memcached-%s')
  labels = []
  labels.append('Linux')
  labels.append('IX B=1')
  labels.append('ZygOS')
  labels.append('IX B=64')
  CONFIG_PLOT['Linux'] = CONFIG_PLOT['Linux (partitioned connections)']
  CONFIG_PLOT['IX B=64'] = CONFIG_PLOT['IX']
  CONFIG_PLOT['IX B=1'] = CONFIG_PLOT['IX'].copy()
  CONFIG_PLOT['IX B=1']['linestyle'] = ':'

  for kv in ['usr', 'etc']:
    fig = plt.figure(figsize=(3.33,2))
    if kv == 'usr':
      plt.xlim(0, 6)
    else:
      plt.xlim(0, 4)
      plt.xticks(np.arange(4))
    plt.ylim(0, 750)
    plt.xlabel('Throughput (MRPS)')
    plt.ylabel('Latency (µs)')
    for i,graph in enumerate(graphs):
      if graph[0] == '/':
        path = graph
      else:
        path = BASEDIR+'/'+graph+'/results.mutilate'
      try:
        x, y = get_xy_continuous(path % kv, metrics['P99']['mutilate'])
      except FileNotFoundError:
        x, y = [], []
      except IndexError:
        x, y = [], []
      x = np.asarray(x) / 1e3
      cfg = CONFIG_PLOT[labels[i]]
      plt.plot(x, y, label=labels[i], marker = cfg['marker'], color = cfg['color'], linestyle = cfg['linestyle'], markersize=cfg['markersize'])
    plt.axhline(500, linestyle = '--', color = '#cccccc', label='SLO')
    plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
    plt.savefig(PAPERDIR + 'figs/memcached-%s.eps' % kv)

    legends = plt.gca().get_legend_handles_labels()
    fig_legend = plt.figure(figsize=(6.67,0.2))
    fig_legend.legend(*legends, loc='center', ncol=9)
    plt.savefig(PAPERDIR + 'figs/memcached-key.eps')

def plot_fixed10slos():
  graphs = []
  graphs.append('ix-batch64-fixed-10')
  graphs.append('ix-batch1-fixed-10')
  graphs.append('zygos-batch64-interrupts-fixed-10')
  labels = []
  labels.append('IX B=64')
  labels.append('IX B=1')
  labels.append('ZygOS')
  CONFIG_PLOT['IX B=64'] = CONFIG_PLOT['IX']
  CONFIG_PLOT['IX B=1'] = CONFIG_PLOT['IX'].copy()
  CONFIG_PLOT['IX B=1']['linestyle'] = ':'
  latency = 'P99'

  for slo_latency in [100, 1000]:
    plt.figure(figsize=(3.33,2))
    plt.axhline(slo_latency, 0, 2, linestyle = '--', color = '#cccccc', label='SLO')
    plt.xlabel('Throughput (MRPS)')
    plt.ylabel('Latency (µs)')
    plt.ylim([0, slo_latency * 1.5])
    plt.xlim([0, 1.4])
    for i, graph in enumerate(graphs):
      try:
        x, y = get_xy_continuous(BASEDIR+'/%s/results.mutilate' % graph, metrics[latency]['mutilate'])
      except FileNotFoundError:
        x, y = [], []
      x = np.asarray(x) / 1e3
      cfg = CONFIG_PLOT[labels[i]]
      plt.plot(x, y, label=labels[i], marker = cfg['marker'], color = cfg['color'], linestyle = cfg['linestyle'], markersize=cfg['markersize'])
    if slo_latency == 1000:
      plt.legend()
    plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
    plt.savefig(PAPERDIR + 'figs/fixed10slos-%d.eps' % slo_latency)

def main():
  matplotlib.rcParams.update({'font.size': 6})
  matplotlib.rcParams['ps.useafm'] = True
  plot_latency_vs_load_real_system(svc_time = 10)
  plot_latency_vs_load_real_system(svc_time = 25)
  plot_svc_time_vs_throughput_sla([2,4,6,8,10,12,14,16,18,20,25,30,40,50])
  plot_svc_time_vs_throughput_sla([2,4,6,8,10,12,14,16,18,20,25,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200], motivation = True)
  plot_silo_latency_vs_load()
  plot_steals_vs_throughput(normalized = True)
  plot_silo_service_time(CCDF = True)
  plot_memcached()
  plot_fixed10slos()

if __name__ == '__main__':
  main()
