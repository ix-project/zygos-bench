## Overview

This repository contains all the scripts and repositories that were developed and used for the paper:

> ZygOS: Achieving Low Tail Latency for Microsecond-scale Networked Tasks
> George Prekas, Marios Kogias, Edouard Bugnion
> 26th ACM Symposium on Operating Systems Principles (SOSP) (2017)

You can view the paper here:

https://infoscience.epfl.ch/record/231395

In order to reproduce the results of the above mentioned paper, you can do the following:

```
git submodule update --init --recursive
make
cd bench
./bench.sh
./plot.sh

# For the simulation results
go get github.com/epfl-dcsl/schedsim
./sim_run.py single_queue
./sim_run.py multi_queue
./sim_plot.py
```
