#!/bin/bash

set -eu -o pipefail

trap on_exit EXIT

on_exit() {
  echo '== Bench stop ==========================================================='
  stop_ix
  pkill -f spin-linux || true
  pkill -f memcached || true
  for i in $agents ${master_agent-}; do
    ( ssh $i 'pkill mutilate; sudo pkill mutilatedpdk' || true & )
  done
  wait
}

reset_env() {
  unset `compgen -v | grep -v -e SCRIPTNAME -e DIR -e agents -e master_agent -e PATH -e server_ip -e server_port -e TERM -e kv_dists_ -e PARAM_` 2>/dev/null || true
}

set_protocol() {
  protocol=$1
  if [ $protocol == udp ]; then
    udpparam=--udp
  else
    udpparam=
  fi
}

set_svctime() {
  svc_time_distribution=$1
  svc_time=$2 # microseconds
  if [ $svc_time_distribution = fixed ]; then
    lambda=$svc_time
  elif [ $svc_time_distribution = exponential ]; then
    lambda=`bc -l<<<1/$svc_time`
  elif [ $svc_time_distribution = bimodal90 ]; then
    lambda=0.9,`bc -l<<<"$svc_time-(sqrt($svc_time)/sqrt(2))"`,`bc -l<<<"(9*sqrt($svc_time))/sqrt(2)+$svc_time"`
  elif [ $svc_time_distribution = bimodal99 ]; then
    lambda=0.99,`bc -l<<<"$svc_time-(sqrt($svc_time)/sqrt(2))"`,`bc -l<<<"(99*sqrt($svc_time))/sqrt(2)+$svc_time"`
  elif [ $svc_time_distribution = bimodal90linear ]; then
    lambda=0.9,`bc -l<<<0.5*$svc_time`,`bc -l<<<5.5*$svc_time`
  elif [ $svc_time_distribution = bimodal99linear ]; then
    lambda=0.99,`bc -l<<<0.5*$svc_time`,`bc -l<<<50.5*$svc_time`
  elif [ $svc_time_distribution = silo ]; then
    svc_time=25
    lambda=$DIR/bench/silo-tpcc-trace
    svc_time_distribution=file
  else
    >&2 echo "svc_time_distribution $svc_time_distribution not supported."
    exit 1
  fi
}

set_connections() {
  connections_per_thread=$[$1 / 16 / `wc -w<<<$agents`]
  set_mutilate_options
}

set_mutilate_options() {
  common_options="--server=$server_ip:$server_port --noload --master-agent=$master_agent --threads=1 --depth=4 --measure_depth=1 --connections=$connections_per_thread --measure_connections=$master_agent_conns --measure_qps=2000 --agent=$agents_comma --binary"
}

set_batch() {
  sed -i -e "s/batch.*/batch=$1/" /tmp/ix.conf
}

set_cpus() {
  CPUS=$1
  local CPUSTR=`awk '/^cpu/{$0=substr($0,1+index($0,"["));print substr($0,0,length($0)-1)}' /tmp/ix.conf | cut -d, -f-$CPUS`
  awk '/^cpu/{$0="cpu=['$CPUSTR']"}{print}' /tmp/ix.conf > /tmp/ix.conf.tmp
  mv /tmp/ix.conf.tmp /tmp/ix.conf
}

set_busy_poll() {
  sudo sysctl net.core.busy_poll=$1
}

set_agents() {
  if [ $# -lt 2 ]; then
    >&2 echo "At least two agents are required."
    exit 1
  fi
  local all_agents="$*"
  master_agent=`cut -d' ' -f1<<<$all_agents`
  agents=`cut -d' ' -f2- <<<$all_agents`
  agents_comma=`tr ' ' , <<<$agents`
}

build_ix() {
  git -C $DIR/zygos checkout inc/ix/config.h
  while [ ${1+x} ]; do
    sed -i -e "s/\(#define $1\).*/\1 1/" $DIR/zygos/inc/ix/config.h
    shift
  done
  make -sj64 -C $DIR || exit 1
}

build_opensource_ix() {
  local BRANCH=$1

  build_ix
  git -C $OPENSOURCE_DIR/deps/dune checkout $BRANCH
  git -C $OPENSOURCE_DIR checkout $BRANCH
  make -sj64 -C $OPENSOURCE_DIR/deps/dune || exit 1
  make -sj64 -C $OPENSOURCE_DIR clean || exit 1
  make -sj64 -C $OPENSOURCE_DIR || exit 1
}

build_linux() {
  git -C $DIR/servers checkout config.h
  while [ ${1+x} ]; do
    sed -i -e "s/\(#define ${1%=*}\).*/\1 ${1#*=}/" $DIR/servers/config.h
    shift
  done
  make -sj64 -C $DIR || exit 1
}

set_outdir() {
  local APPEND=0
  while true; do
    if [ ${1-x} == --append ]; then
      shift
      APPEND=1
    else
      break
    fi
  done
  OUTDIR=$1
  if [ $APPEND -eq 0 -a -d $OUTDIR ]; then
    >&2 echo "$OUTDIR exists. Skipping."
    exit 1
  fi
  if [ $OUTDIR ]; then
    mkdir -p $OUTDIR
  fi
  echo Output directory $OUTDIR
}

_init() {
  echo '#' _REAL_ connection count = $[$connections_per_thread * 16 * `wc -w<<<$agents`]
  echo "# `date`"
  echo "# `uname -a`"
  echo "# `git describe --match=NeVeRmAtCh --always --abbrev=40 --dirty`"
  if [ ${OUTDIR+x} ]; then
    sysctl net.core.busy_poll
    git status
    git diff --color=always -- ':/' ':!/bench/results3'
    cat /tmp/ix.conf
    cat $DIR/zygos/inc/ix/config.h
    cat $DIR/servers/config.h
    cat $0
    set
  fi
}

prepare_machines() {
  prep_script() {
    local IGNORE_SCRIPTNAME=$1
    local IGNORE_COUNT=$2
    local IGNORED=''
    IGNORED+=' -e /lib/systemd/systemd-journald'
    IGNORED+=' -e /lib/systemd/systemd-logind'
    IGNORED+=' -e /lib/systemd/systemd-udevd'
    IGNORED+=' -e /sbin/agetty'
    IGNORED+=' -e /sbin/dhclient'
    IGNORED+=' -e /sbin/init'
    IGNORED+=' -e /sbin/rpc.statd'
    IGNORED+=' -e /sbin/rpcbind'
    IGNORED+=' -e /usr/bin/dbus-daemon'
    IGNORED+=' -e /usr/lib/accountsservice/accounts-daemon'
    IGNORED+=' -e /usr/sbin/automount'
    IGNORED+=' -e /usr/sbin/cron'
    IGNORED+=' -e /usr/sbin/nscd'
    IGNORED+=' -e /usr/sbin/nslcd'
    IGNORED+=' -e /usr/sbin/ntpd'
    IGNORED+=' -e /usr/sbin/rsyslogd'
    IGNORED+=' -e /usr/sbin/sshd'
    IGNORED+=' -e sshd:'
    IGNORED+=' -e /bin/ps'
    IGNORED+=" -e '`whoami`.*tmux'"
    IGNORED+=" -e '`whoami`.*-bash'"
    if [ $IGNORE_SCRIPTNAME == yes ]; then
      IGNORED+=" -e $SCRIPTNAME"
    fi
    echo '''
PSOUT=`/bin/ps --ppid 2 -p 2 --deselect -f | grep --color=auto -v '''$IGNORED'''`
if [ `echo "$PSOUT" | wc -l` -ne '''$[1+$IGNORE_COUNT]''' ]; then
  echo "`hostname`: Running unknown processes:\n$PSOUT"
  exit 1
fi

FREQ=`cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq`
for i in /sys/devices/system/cpu/cpu*/cpufreq; do
  echo userspace > $i/scaling_governor
  echo $FREQ > $i/scaling_setspeed
done
if [ -e /sys/devices/system/cpu/cpufreq/boost ]; then
  echo 0 > /sys/devices/system/cpu/cpufreq/boost
fi
echo never > /sys/kernel/mm/transparent_hugepage/enabled
'''
  }

  sudo sh -c "`prep_script yes 1`" || exit 1
  local AGENT
  for AGENT in $master_agent $agents; do
    ssh $AGENT "sudo sh -c '`prep_script no 0`'" &
  done
  for AGENT in $master_agent $agents; do
    wait -n || exit 1
  done
}

init_ix() {
  local PAGES=${1:-4096}
  sudo modprobe -r ixgbe
  sudo modprobe -r i40e
  sudo rmmod dune 2> /dev/null || true
  sudo rmmod pcidma 2> /dev/null || true
  sudo insmod $DIR/zygos/deps/dune/kern/dune.ko || true
  sudo insmod $DIR/zygos/deps/pcidma/pcidma.ko || true
  sudo modprobe uio
  sudo insmod $DIR/zygos/deps/dpdk/build/kmod/igb_uio.ko 2> /dev/null || true
  sudo $DIR/zygos/deps/dpdk/tools/dpdk_nic_bind.py -b igb_uio $PARAM_NIC_PCI > /dev/null
  sudo sh -c "echo $PAGES > /sys/devices/system/node/node$PARAM_NUMA_NODE/hugepages/hugepages-2048kB/nr_hugepages"
  cp /etc/ix.conf /tmp/ix.conf
}

init_linux() {
  local PAGES=${1:-4096}
  sudo rmmod dune 2> /dev/null || true
  sudo rmmod pcidma 2> /dev/null || true
  sudo sh -c "echo $PAGES > /sys/devices/system/node/node$PARAM_NUMA_NODE/hugepages/hugepages-2048kB/nr_hugepages"
  sudo rmmod igb_uio 2> /dev/null || true
  sudo modprobe -r uio
  sudo modprobe ixgbe
  sudo modprobe i40e
  sudo $DIR/zygos/deps/dpdk/tools/dpdk_nic_bind.py --force -b $PARAM_NIC_DRIVER $PARAM_NIC_PCI > /dev/null
  sudo sysctl net.ipv4.tcp_syncookies=1 > /dev/null
  cp /etc/ix.conf /tmp/ix.conf
  sudo ip neigh add 10.90.44.201 lladdr b8:ca:3a:6a:b9:18 dev cu0
  sleep 3
}

init() {
  if [ ${OUTDIR+x} ]; then
    _init >> $OUTDIR/info
  else
    _init
  fi
}

start_ix() {
  sudo rm -f /var/run/.rte_config
  sudo find /dev/hugepages -delete 2> /dev/null || true
  if [ $ix_app = spin ]; then
    sudo -E stdbuf -oL numactl -m$PARAM_NUMA_NODE nice -20 $IX_DIR/dp/ix -c /tmp/ix.conf -- $DIR/servers/spin-ix $udpparam $svc_time_distribution:$lambda >> /tmp/ix.log &
  elif [ $ix_app = memcached -o $ix_app = memcached-noload ]; then
    sudo -E stdbuf -oL numactl -m$PARAM_NUMA_NODE nice -20 $IX_DIR/dp/ix -c /tmp/ix.conf -- $DIR/memcached-ix/memcached -k -Mm 1024 -c 4096 -o hashpower=20 >> /tmp/ix.log &
  elif [ $ix_app = silo ]; then
    sudo -E stdbuf -oL numactl -m$PARAM_NUMA_NODE nice -20 $IX_DIR/dp/ix -c /tmp/ix.conf -- $DIR/servers/silotpcc-ix >> /tmp/ix.log &
  else
    >&2 echo "ix_app $ix_app not supported."
    exit 1
  fi
  ssh $master_agent 'sudo /tmp/prekas/dpdk_nic_bind.py -b ixgbe 0000:01:00.0 && sudo ifup cu0'
  ssh $master_agent "while ! nc -w 1 $server_ip $server_port; do echo waiting...; sleep 1; i=\$[i+1]; if [ \$i -eq 60 ]; then exit 1; fi; done" || exit 1
  if [ $ix_app = memcached ]; then
    timeout 100 $DIR/mutilate/ez_mutilate.py --server=$server_ip:$server_port $kv_dist --binary --records=$RECORDS --loadonly --master-agent=$master_agent || >&2 echo "load timeout"
  fi
}

stop_ix() {
  sudo pkill ix || true
  sleep 1
}

start_linux() {
  if [ $linux_app = spin ]; then
    numactl -N$PARAM_NUMA_NODE -m$PARAM_NUMA_NODE nice -20 taskset -c $PARAM_CORES $DIR/servers/spin-linux $svc_time_distribution:$lambda &
  elif [ $linux_app = silo ]; then
    numactl -N$PARAM_NUMA_NODE -m$PARAM_NUMA_NODE nice -20 taskset -c $PARAM_CORES $DIR/servers/silotpcc-linux &
    ssh $master_agent 'sudo /tmp/prekas/dpdk_nic_bind.py -b ixgbe 0000:01:00.0 && sudo ifup cu0'
    ssh $master_agent "while ! nc -w 1 $server_ip $server_port; do echo waiting...; sleep 1; i=\$[i+1]; if [ \$i -eq 60 ]; then exit 1; fi; done"
  elif [ $linux_app = memcached ]; then
    numactl -N$PARAM_NUMA_NODE -m$PARAM_NUMA_NODE nice -20 taskset -c $PARAM_CORES $DIR/memcached/memcached -k -Mm 1024 -c 4096 -o hashpower=20 -b 8192 -t $PARAM_CPUS -T $PARAM_CORES &
    ssh $master_agent 'sudo /tmp/prekas/dpdk_nic_bind.py -b ixgbe 0000:01:00.0 && sudo ifup cu0'
    timeout 100 $DIR/mutilate/ez_mutilate.py --server=$server_ip:$server_port $kv_dist --binary --records=$RECORDS --loadonly --master-agent=$master_agent || >&2 echo "load timeout"
  else
    >&2 echo "linux_app $linux_app not supported."
    exit 1
  fi
}

stop_linux() {
  if [ $linux_app = spin ]; then
    pkill -f spin-linux || true
  elif [ $linux_app = silo ]; then
    pkill -f silotpcc-linux || true
  elif [ $linux_app = memcached ]; then
    pkill -f memcached || true
  else
    >&2 echo "linux_app $linux_app not supported."
    exit 1
  fi
}

go_ix() {
  qps=$1
  echo "== QPS $qps" >> $OUTDIR/results.mutilate
  timeout 60 $DIR/mutilate/ez_mutilate.py --dpdk --cpu-core 0 --my-ip 10.90.44.201 --my-mac b8:ca:3a:6a:b9:18 --server-mac A0:36:9F:27:3C:16 $common_options $kv_dist $EXTRA_MUTILATE_PARAMS --records=$RECORDS --time=$time --qps=$qps >> $OUTDIR/results.mutilate || >&2 echo "mutilate timeout"
}

go_linux() {
  qps=$1
  echo "== QPS $qps" >> $OUTDIR/results.mutilate
  $DIR/mutilate/ez_mutilate.py --dpdk --cpu-core 0 --my-ip 10.90.44.201 --my-mac b8:ca:3a:6a:b9:18 --server-mac A0:36:9F:27:3C:16 $common_options $kv_dist $EXTRA_MUTILATE_PARAMS --records=$RECORDS --time=$time --qps=$qps >> $OUTDIR/results.mutilate
}

go_loop() {
  ssh $master_agent 'mkdir -p /tmp/prekas'
  scp -q $DIR/zygos/deps/dpdk/tools/dpdk_nic_bind.py $master_agent:/tmp/prekas
  scp -q $DIR/zygos/deps/dpdk/build/kmod/igb_uio.ko $master_agent:/tmp/prekas

  local STATS=0
  if [ $1 == --stats ]; then
    shift
    STATS=1
  fi
  local QPSES=`python -c "print ' '.join([str(int(1e6*$CPUS*i/$svc_time/$STEPS)) for i in range(1,$STEPS+1)])"`
  local QPS_START=`awk '{print$1}' <<<$QPSES`
  local QPS_STOP=`awk '{print$NF}' <<<$QPSES`
  local QPS_STEP=`awk '{print$2-$1}' <<<$QPSES`
  if [ $QPS_START -lt 3000 ]; then
    QPS_START=3000
  fi
  if [ $1 == ix_continuous ]; then
    if [ -s $OUTDIR/results.mutilate ]; then
      exit 1
    fi
    start_ix
    if [ $STATS -eq 1 ]; then
      sudo chmod a+rw /dev/shm/ix-stats
    fi
    ssh $master_agent 'sudo modprobe uio; sudo insmod /tmp/prekas/igb_uio.ko; sudo ifdown cu0; sudo /tmp/prekas/dpdk_nic_bind.py -b igb_uio 0000:01:00.0; sudo sh -c "echo 512 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"'
    $DIR/mutilate/ez_mutilate.py --dpdk --cpu-core 0 --my-ip 10.90.44.201 --my-mac b8:ca:3a:6a:b9:18 --server-mac A0:36:9F:27:3C:16 $common_options $kv_dist $EXTRA_MUTILATE_PARAMS --records=$RECORDS --time=$[$STEPS * $time] --qps-function=qtriangle:$QPS_START:$QPS_STOP:$[$STEPS * $time * 2]:$QPS_STEP --report-stats=$time | while read; do
      if [ $STATS -eq 1 ]; then
        if [[ "$REPLY" =~ ' read' ]]; then
          $DIR/zygos/tools/ix-stats-show --reset | awk '{print "'${REPLY##* }'",$0}' >> $OUTDIR/results.stats
        elif [[ "$REPLY" =~ '#time' ]]; then
          $DIR/zygos/tools/ix-stats-show --reset > /dev/null
        fi
      fi
      echo "$REPLY" >> $OUTDIR/results.mutilate
    done
    stop_ix
  elif [ $1 == linux_continuous ]; then
    if [ -s $OUTDIR/results.mutilate ]; then
      exit 1
    fi
    start_linux
    ssh $master_agent 'sudo modprobe uio; sudo insmod /tmp/prekas/igb_uio.ko; sudo ifdown cu0; sudo /tmp/prekas/dpdk_nic_bind.py -b igb_uio 0000:01:00.0; sudo sh -c "echo 512 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"'
    $DIR/mutilate/ez_mutilate.py --dpdk --cpu-core 0 --my-ip 10.90.44.201 --my-mac b8:ca:3a:6a:b9:18 --server-mac A0:36:9F:27:3C:16 $common_options $kv_dist $EXTRA_MUTILATE_PARAMS --records=$RECORDS --time=$[$STEPS * $time] --qps-function=qtriangle:$QPS_START:$QPS_STOP:$[$STEPS * $time * 2]:$QPS_STEP --report-stats=$time > $OUTDIR/results.mutilate
    stop_linux
  else
    for i in $QPSES; do
      if grep -m1 "^== QPS $i\$" $OUTDIR/results.mutilate > /dev/null 2> /dev/null; then
        >&2 echo "$OUTDIR: $i exists. Skipping."
        continue
      fi
      if [ $1 = ix ]; then
        go_ix $i
      elif [ $1 == ix_restart ]; then
        if ! start_ix; then
          stop_ix
          continue
        fi
        ssh $master_agent 'sudo modprobe uio; sudo insmod /tmp/prekas/igb_uio.ko; sudo ifdown cu0; sudo /tmp/prekas/dpdk_nic_bind.py -b igb_uio 0000:01:00.0; sudo sh -c "echo 512 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"'
        go_ix $i
        stop_ix
      elif [ $1 = linux ]; then
        go_linux $i
      elif [ $1 = linux_restart ]; then
        start_linux
        ssh $master_agent 'sudo modprobe uio; sudo insmod /tmp/prekas/igb_uio.ko; sudo ifdown cu0; sudo /tmp/prekas/dpdk_nic_bind.py -b igb_uio 0000:01:00.0; sudo sh -c "echo 512 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages"'
        go_linux $i
        stop_linux
      else
        >&2 echo "go_loop $1 not supported."
        exit 1
      fi
    done

  fi
}

SCRIPTNAME=$0
DIR=`dirname $0`/..

kv_dists_etc='--keysize=fb_key --valuesize=fb_value --iadist=fb_ia --update=0.033'
kv_dists_etc_noupdate='--keysize=fb_key --valuesize=fb_value --iadist=exponential --update=0'
kv_dists_usr='--keysize=19 --valuesize=2 --update=0.002'
kv_dists_usr_noupdate='--keysize=19 --valuesize=2 --update=0'
