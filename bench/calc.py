#!/usr/bin/env python3

import plot
import sim_plot
import subprocess
import numpy as np

def data(name, fmt, *args, xspace = False):
  return '\\newcommand{\\%s} {\\boxdata{%s}%s}' % (name, fmt % args, '\\xspace' if xspace else '')

def sim_max_load_under_slo(which):
  sim_data = sim_plot.parse_file(plot.BASEDIR + '/../simulations/%s.dat' % which)
  ret = 0
  lat = {}
  for cores, mu, intr_lambda, qps, avg, lat['P50'], lat['P90'], lat['P95'], lat['P99'] in sim_data:
    if lat[plot.MICROB_PERC] < plot.SLO_MULTIPLIER / mu:
      ret = max(ret, qps/(cores*mu))
  return ret * 100

def efficiency_over_sim(system, distribution, svc_time, suffix = ''):
  max_x = 0
  max_x_sim = 0

  try:
    xs, ys = plot.get_xy_continuous('%s/%s-%s-%d%s/results.mutilate' % (plot.BASEDIR, system, distribution, svc_time, suffix), plot.metrics[plot.MICROB_PERC]['mutilate'])
    xs = np.asarray(xs) / 1e3
  except:
    xs, ys = plot.get_xy('cmd_mutilate', '%s/%s-%s-%d%s' % (plot.BASEDIR, system, distribution, svc_time, suffix), plot.metrics[plot.MICROB_PERC]['mutilate'])

  for x, y in zip(xs, ys):
    if y < svc_time * plot.SLO_MULTIPLIER:
      max_x = max(max_x, x)

  sim_distribution = {
    'exponential': 'm',
  }[distribution]

  sim_data = sim_plot.parse_file(plot.BASEDIR + '/../simulations/mg16_%s.dat' % sim_distribution)
  lat = {}
  for cores, mu, intr_lambda, qps, avg, lat['P50'], lat['P90'], lat['P95'], lat['P99'] in sim_data:
    if lat[plot.MICROB_PERC] < plot.SLO_MULTIPLIER / mu:
      max_x_sim = max(max_x_sim, qps/(cores*mu))

  return max_x / (16 / svc_time) / max_x_sim * 100

def min_svc_time_for_efficiency_over_sim(system, distribution, efficiency, one_queue, suffix = ''):
  xs, ys = plot.get_svc_time_vs_throughput_sla_xy(plot.BASEDIR + '/%s-%%s-%%d%s' % (system, suffix), plot.MICROB_PERC, distribution, range(1, 500))
  if distribution == 'fixed':
    mm1x16_load = plot.calc_max_load_from_simulation('MD16.txt' if one_queue else '16xMD1.txt', plot.MICROB_PERC)
  elif distribution == 'exponential':
    mm1x16_load = plot.calc_max_load_from_simulation('MM16.txt' if one_queue else '16xMM1.txt', plot.MICROB_PERC)
  elif distribution == 'bimodal90linear':
    mm1x16_load = plot.calc_max_load_from_simulation('MB16.txt' if one_queue else '16xMB1.txt', plot.MICROB_PERC)
  else:
    assert(0)
  for i in range(len(xs)):
    if ys[i] / mm1x16_load > efficiency:
      return xs[i]
  return 0

def task_size_linux_floating_vs_ix(distribution):
  xs_ix, ys_ix = plot.get_svc_time_vs_throughput_sla_xy(plot.BASEDIR + '/ix-batch1-%s-%d', plot.MICROB_PERC, distribution, range(1, 500))
  xs_linux, ys_linux = plot.get_svc_time_vs_throughput_sla_xy(plot.BASEDIR + '/linux-tcp-busypoll0-epollall-maxevents1-%s-%d', plot.MICROB_PERC, distribution, range(1, 500))

  ret = 0
  for i in range(len(xs_ix)):
    assert xs_ix[i] == xs_linux[i]
    if ys_linux[i] < ys_ix[i]:
      ret = 0
    if ret == 0 and ys_linux[i] > ys_ix[i]:
      ret = xs_ix[i]
  return ret

def get_silo_stats():
  try:
    xs_zygos, ys_zygos = plot.get_xy_continuous('%s/zygos-batch64-connections2720-interrupts-silo-tpcc/results.mutilate' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
  except:
    xs_zygos, ys_zygos = plot.get_xy('cmd_mutilate', '%s/zygos-batch64-connections2720-interrupts-silo-tpcc' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
    xs_zygos = np.asarray(xs_zygos) * 1e3
  try:
    xs_ix, ys_ix = plot.get_xy_continuous('%s/ix-batch64-connections2720-silo-tpcc/results.mutilate' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
  except:
    xs_ix, ys_ix = plot.get_xy('cmd_mutilate', '%s/ix-batch64-connections2720-silo-tpcc' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
    xs_ix = np.asarray(xs_ix) * 1e3
  try:
    xs_linux, ys_linux = plot.get_xy_continuous('%s/linux-tcp-busypoll0-epollall-maxevents1-connections2720-silo-tpcc/results.mutilate' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
  except:
    xs_linux, ys_linux = plot.get_xy('cmd_mutilate', '%s/linux-tcp-busypoll0-epollall-maxevents1-connections2720-silo-tpcc' % plot.BASEDIR, plot.metrics[plot.SILO_PERC]['mutilate'])
    xs_linux = np.asarray(xs_linux) * 1e3

  ret = {
    'linux_max_throughput': max((x for x, y in zip(xs_linux, ys_linux) if y < 1000)),
    'zygos_max_throughput': max((x for x, y in zip(xs_zygos, ys_zygos) if y < 1000)),
  }

  return ret

def expand_service_times(tuples):
  sum = 0
  ret = []
  for count, svc_time in tuples:
    sum += count * svc_time
    for i in range(count):
      ret.append(svc_time)
  return sum / len(ret), ret

def get_silo_stats2(dirname, *percentages):
  xs, ys = plot.get_xy('cmd_mutilate', '%s/%s' % (plot.BASEDIR, dirname), plot.metrics[plot.SILO_PERC]['mutilate'])
  xs = np.asarray(xs) * 1e3
  throughput = 0
  for i in range(len(xs)):
    if ys[i] > 1000:
      continue
    throughput = max(throughput, xs[i])
  latencies = {}
  throughputs = {}
  for percentage in percentages:
    best = 1
    for i in range(len(xs)):
      ratio = xs[i] / throughput
      if abs(ratio - percentage / 100) < best:
        best = abs(ratio - percentage / 100)
        latencies[percentage] = ys[i]
        throughputs[percentage] = xs[i]
  return throughput, latencies, throughputs

def main():
  print(data('dataSLOLoadDistributedExp', '%.1f\\%%', sim_max_load_under_slo('16mg1_m')))
  print(data('dataSLOLoadSingleExp', '%.1f\\%%', sim_max_load_under_slo('mg16_m')))
  print('')

  for name, value in [('Ten', 10), ('TwentyFive', 25)]:
    print(data('dataSLOZygos' + name, '%.0f\\%%', efficiency_over_sim('zygos-batch64-interrupts', 'exponential', value)))

  print(data('dataMinTaskLinuxFloatDet', '$\ge$%d\microsecond', task_size_linux_floating_vs_ix('fixed')))
  print(data('dataMinTaskLinuxFloatExp', '$\ge$%d\microsecond', task_size_linux_floating_vs_ix('exponential')))
  print(data('dataMinTaskLinuxFloatBi', '$\ge$%d\microsecond', task_size_linux_floating_vs_ix('bimodal90linear')))
  print('')

  throughput = open('%s/silo/output.txt' % plot.SCRIPTDIR).readlines()[-1].split()[0]
  print(data('dataSiloCCDFThroughput', '%.0f KTPS', int(throughput)/1e3))
  print('')

  silo_stats = get_silo_stats()
  print(data('dataSiloTPS', '%.0f KTPS', silo_stats['zygos_max_throughput']))
  print(data('dataSiloSpeedup', '%.2f$\\times$', silo_stats['zygos_max_throughput'] / silo_stats['linux_max_throughput']))
  print('')

  svc_times = plot.get_silo_service_times()
  avg, perc = expand_service_times(svc_times[-1])
  silo_99th = perc[len(perc) * 99 // 100]
  print(data('dataSiloTPCCAverage', '%1.f\\microsecond', avg, xspace = False))
  print(data('dataSiloTPCCMedian', '%1.f\\microsecond', perc[len(perc) * 50 // 100], xspace = False))
  print(data('dataSiloTPCCNinetyNine', '%1.f\\microsecond', silo_99th, xspace = False))
  print('')

  tuples = []
  tuples.append(('Linux', 'linux-tcp-busypoll0-epollall-maxevents1-connections2720-silo-tpcc'))
  tuples.append(('IX', 'ix-batch64-connections2720-silo-tpcc'))
  tuples.append(('Zygos', 'zygos-batch64-connections2720-interrupts-silo-tpcc'))
  for name, dirname in tuples:
    throughput, latencies, throughputs = get_silo_stats2(dirname, 50, 75, 90)
    if name == 'Linux':
      linux_throughput = throughput
    print(data('dataSilo%sThroughput' % name, '%.0f KTPS', throughput))
    print(data('dataSilo%sSpeedup' % name, '%.2f$\\times$', throughput / linux_throughput))
    for name2, value in [('Fifty', 50), ('SeventyFive', 75), ('Ninety', 90)]:
      print(data('dataSilo%sLatency%s' % (name, name2), '%.0f\\microsecond', latencies[value], xspace = False))
      print(data('dataSilo%sLatency%sRatio' % (name, name2), '%.1f$\\times$', latencies[value] / silo_99th))
      print(data('dataSilo%sLatency%sThroughput' % (name, name2), '%.0f KTPS', throughputs[value]))
  print('')

  print(data('dataIXEffDet', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('ix-batch1', 'fixed', .9, False), xspace = False))
  print(data('dataIXEffExp', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('ix-batch1', 'exponential', .9, False), xspace = False))
  print(data('dataIXEffBi', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('ix-batch1', 'bimodal90linear', .9, False), xspace = False))
  print(data('dataLinuxPartEffDet', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('linux-tcp-busypoll0-epolloriginal-maxevents1', 'fixed', .9, False, ''), xspace = False))
  print(data('dataLinuxPartEffExp', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('linux-tcp-busypoll0-epolloriginal-maxevents1', 'exponential', .9, False, ''), xspace = False))
  print(data('dataLinuxPartEffBi', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('linux-tcp-busypoll0-epolloriginal-maxevents1', 'bimodal90linear', .9, False, ''), xspace = False))
  print('')

  print(data('dataZygosEffDet', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('zygos-batch64-interrupts', 'fixed', .9, True), xspace = False))
  print(data('dataZygosEffExp', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('zygos-batch64-interrupts', 'exponential', .9, True), xspace = False))
  print(data('dataZygosEffBi', '%1.f\\microsecond', min_svc_time_for_efficiency_over_sim('zygos-batch64-interrupts', 'bimodal90linear', .9, True), xspace = False))
  print('')

if __name__ == '__main__':
  main()
