#!/bin/bash

server_port=11211
master_agent_conns=32
if [ `hostname` == sciicebpc1 ]; then
  server_ip=10.90.44.200
  agents=`echo icnals01 icnals{03..10} icnals{13..14}`
  PARAM_NIC_PCI=0000:42:00.1
  PARAM_NUMA_NODE=1
  PARAM_NIC_DRIVER=ixgbe
  PARAM_CPUS=16
  PARAM_CORES=1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31
elif [ `hostname` == sciicebpc3 ]; then
  server_ip=10.90.44.251
  agents=`echo icnals01 icnals{03..10} icnals{12..20}`
  PARAM_NIC_PCI=0000:01:00.0
  PARAM_NUMA_NODE=0
  PARAM_NIC_DRIVER=i40e
  PARAM_CPUS=38
  PARAM_CORES=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39
fi

. bench-functions.sh

echo '== Bench start =========================================================='

bench() {
  reset_env
  local INTERRUPTS=''
  local STATS=''
  local OPENSOURCE=0
  while true; do
    if [ $1 == --stats ]; then
      shift
      STATS='--stats'
    elif [ $1 == --interrupts ]; then
      shift
      INTERRUPTS='-interrupts'
    elif [ $1 == --opensource ]; then
      shift
      OPENSOURCE=1
    else
      break
    fi
  done
  local DIST=$1
  local MEAN=$2
  local BATCH=$3
  set_agents $agents
  time=5
  if [ $OPENSOURCE -eq 1 ]; then
    IX_DIR=$DIR/ix
  else
    IX_DIR=$DIR/zygos
  fi
  init_ix
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  set_connections 2720
  kv_dist=$kv_dists_etc_noupdate
  ix_app=spin
  set_protocol tcp
  set_batch $BATCH
  set_cpus $PARAM_CPUS
  set_svctime $DIST $MEAN
  prepare_machines
  if [ $OPENSOURCE -eq 1 ]; then
    set_outdir results/ix-batch$BATCH-$DIST-$MEAN
  else
    set_outdir results/zygos-batch$BATCH$INTERRUPTS-$DIST-$MEAN
  fi
  init
  go_loop $STATS ix_continuous
  on_exit
}

bench_silo() {
  reset_env
  local OPENSOURCE=0
  while true; do
    if [ ${1-x} == --opensource ]; then
      shift
      OPENSOURCE=1
    else
      break
    fi
  done
  local BATCH=$1
  set_agents $agents
  time=20
  if [ $OPENSOURCE -eq 1 ]; then
    IX_DIR=$DIR/ix
  else
    IX_DIR=$DIR/zygos
  fi
  init_ix 24576
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  CONNECTIONS=2720
  set_connections $CONNECTIONS
  kv_dist=$kv_dists_etc_noupdate
  ix_app=silo
  set_protocol tcp
  set_batch $BATCH
  set_cpus $PARAM_CPUS
  set_svctime fixed 45
  prepare_machines
  if [ $OPENSOURCE -eq 1 ]; then
    set_outdir --append results/ix-batch$BATCH-connections$CONNECTIONS-silo-tpcc
  else
    set_outdir --append results/zygos-batch$BATCH-connections$CONNECTIONS-interrupts-silo-tpcc
  fi
  init
  go_loop ix_restart
  on_exit
}

bench_memcached() {
  reset_env
  local INTERRUPTS=''
  local OPENSOURCE=0
  while true; do
    if [ ${1-x} == --opensource ]; then
      shift
      OPENSOURCE=1
    elif [ $1 == --interrupts ]; then
      shift
      INTERRUPTS='-interrupts'
    else
      break
    fi
  done
  local BATCH=$1
  local KVDIST=$2
  set_agents $agents
  time=5
  if [ $OPENSOURCE -eq 1 ]; then
    IX_DIR=$DIR/ix
  else
    IX_DIR=$DIR/zygos
  fi
  init_ix 4096
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  set_connections 2720
  kv_dist=kv_dists_$KVDIST
  kv_dist=${!kv_dist}
  ix_app=memcached
  set_protocol tcp
  set_batch $BATCH
  set_cpus $PARAM_CPUS
  set_svctime fixed 2
  prepare_machines
  if [ $OPENSOURCE -eq 1 ]; then
    set_outdir results/ix-batch$BATCH-memcached-$KVDIST
  else
    set_outdir results/zygos-batch$BATCH$INTERRUPTS-memcached-$KVDIST
  fi
  init
  go_loop ix_continuous
  on_exit
}

bench_linux() {
  reset_env
  local DIST=$1
  local MEAN=$2
  local EPOLL=$3
  set_agents $agents
  time=5
  init_linux
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  set_connections 2720
  kv_dist=$kv_dists_etc_noupdate
  linux_app=spin
  set_protocol tcp
  set_cpus $PARAM_CPUS
  set_svctime $DIST $MEAN
  prepare_machines
  set_outdir results/linux-tcp-busypoll0-epoll$EPOLL-maxevents1-$DIST-$MEAN
  init
  go_loop linux_continuous
  on_exit
}

bench_linux_silo() {
  reset_env
  set_agents $agents
  time=20
  init_linux 24576
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  CONNECTIONS=2720
  set_connections $CONNECTIONS
  kv_dist=$kv_dists_etc_noupdate
  linux_app=silo
  set_protocol tcp
  set_cpus $PARAM_CPUS
  set_svctime fixed 45
  prepare_machines
  set_outdir --append results/linux-tcp-busypoll0-epollall-maxevents1-connections$CONNECTIONS-silo-tpcc
  init
  go_loop linux_restart
  on_exit
}

bench_linux_memcached() {
  reset_env
  local KVDIST=$1
  set_agents $agents
  time=5
  init_linux 0
  STEPS=32
  EXTRA_MUTILATE_PARAMS=
  RECORDS=1000000
  set_connections 2720
  kv_dist=kv_dists_$KVDIST
  kv_dist=${!kv_dist}
  linux_app=memcached
  set_protocol tcp
  set_cpus $PARAM_CPUS
  set_svctime fixed 2
  prepare_machines
  set_outdir results/linux-memcached-$KVDIST
  init
  go_loop linux_continuous
  on_exit
}

bench_silo_service_times_cdf() {
  reset_env
  init_linux 24576
  rm -f worker_*_latencies.txt
  make -sj64 -C $DIR/silo clean
  make -sj64 -C $DIR/silo dbtest ENABLE_INSTR=1
  numactl -N$PARAM_NUMA_NODE -m$PARAM_NUMA_NODE nice -20 taskset -c $PARAM_CORES $DIR/silo/out-perf.masstree/benchmarks/dbtest --bench tpcc --num-threads $PARAM_CPUS --scale-factor $PARAM_CPUS --runtime 30 --numa-memory 40G --disable-gc > silo/output.txt 2>&1
  make -sj64 -C $DIR/silo clean
  cat worker_*_latencies.txt | sort -nk2 -nk1 -S1G | uniq -c | sort -nk2 -S1G > silo/silo-tpcc-service-times-v2.txt
  rm -f worker_*_latencies.txt
}

################################################################################

make -sj64 -C $DIR

################################################################################

make -sj64 -C $DIR/servers clean
make -sj64 -C $DIR/servers
make -sj64 -C $DIR/memcached-ix clean
( cd $DIR/memcached-ix && ./autogen.sh && ./configure --with-ix=../zygos )
make -sj64 -C $DIR/memcached-ix memcached

build_ix CONFIG_STATS
( bench --stats exponential 25 64 ) || true

build_ix CONFIG_STATS CONFIG_RUN_TCP_STACK_IPI
( bench --stats --interrupts exponential 25 64 ) || true

build_ix
for DIST in bimodal90linear fixed exponential; do
  ( bench $DIST 10 64 ) || true
  ( bench $DIST 25 64 ) || true
done

build_ix CONFIG_RUN_TCP_STACK_IPI
for DIST in bimodal90linear fixed exponential; do
  for SVCTIME in {2..20..2} 25 {30..50..10}; do
    ( bench --interrupts $DIST $SVCTIME 64 ) || true
  done
done

build_ix CONFIG_RUN_TCP_STACK_IPI
( bench_silo 64 ) || true

build_ix CONFIG_RUN_TCP_STACK_IPI
( bench_memcached --interrupts 64 etc ) || true
( bench_memcached --interrupts 64 usr ) || true

################################################################################

for EPOLL in original all; do
  if [ $EPOLL = original ]; then
    build_linux CONFIG_REGISTER_FD_TO_ALL_EPOLLS=0 CONFIG_USE_EPOLLEXCLUSIVE=0 CONFIG_MAX_EVENTS=1
  elif [ $EPOLL = all ]; then
    build_linux CONFIG_REGISTER_FD_TO_ALL_EPOLLS=1 CONFIG_USE_EPOLLEXCLUSIVE=0 CONFIG_MAX_EVENTS=1
  else
    continue
  fi
  for DIST in bimodal90linear fixed exponential; do
    for SVCTIME in {2..20..2} {30..200..10} 25; do
      ( bench_linux $DIST $SVCTIME $EPOLL ) || true
    done
  done
done

build_linux CONFIG_REGISTER_FD_TO_ALL_EPOLLS=1 CONFIG_USE_EPOLLEXCLUSIVE=0 CONFIG_MAX_EVENTS=1
( bench_linux_silo ) || true

( bench_linux_memcached etc ) || true
( bench_linux_memcached usr ) || true

################################################################################

OPENSOURCE_DIR=`realpath $DIR/../ix`
make -sj64 -C $DIR/servers clean
make -sj64 -C $DIR/servers IX_DIR=$OPENSOURCE_DIR
make -sj64 -C $DIR/memcached-ix clean
( cd $DIR/memcached-ix && ./autogen.sh && ./configure --with-ix=$OPENSOURCE_DIR )
make -sj64 -C $DIR/memcached-ix memcached

for DIST in bimodal90linear fixed exponential; do
  for SVCTIME in {2..20..2} {30..200..10} 25; do
    ( bench --opensource $DIST $SVCTIME 1 ) || true
  done
done

( bench_silo --opensource 64 ) || true

( bench_memcached --opensource 64 etc ) || true
( bench_memcached --opensource 64 usr ) || true
( bench_memcached --opensource 1 etc ) || true
( bench_memcached --opensource 1 usr ) || true

################################################################################

( bench_silo_service_times_cdf ) || true
