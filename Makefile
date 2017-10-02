all:
	$(MAKE) -C ix/deps/dune
	$(MAKE) -C silo dbtest
	$(MAKE) -C zygos/deps/dune
	$(MAKE) -C zygos/deps/pcidma
	$(MAKE) -C memcached memcached
	$(MAKE) -C ix
	$(MAKE) -C zygos
	$(MAKE) -C memcached-ix memcached
	DPDK=../zygos/deps/dpdk/build scons -sj64 -C mutilate
	$(MAKE) -C servers

clean:
	$(MAKE) -C ix clean
	$(MAKE) -C ix/deps/dune clean
	$(MAKE) -C servers clean
	$(MAKE) -C silo clean
	$(MAKE) -C zygos clean
	$(MAKE) -C zygos/deps/dune clean
	$(MAKE) -C zygos/deps/pcidma clean
	scons -sj64 -C mutilate --clean
	[ ! -f memcached-ix/Makefile ] || $(MAKE) -C memcached-ix clean
	[ ! -f memcached/Makefile ] || $(MAKE) -C memcached clean
	rm -fr ix/deps/dpdk/build
	rm -fr zygos/deps/dpdk/build

full:
	$(MAKE) -C zygos/deps/dpdk config T=x86_64-native-linuxapp-gcc
	sed -i 's/CONFIG_RTE_KNI_KMOD=y/CONFIG_RTE_KNI_KMOD=n/' zygos/deps/dpdk/build/.config
	$(MAKE) -C ix/deps/dpdk config T=x86_64-native-linuxapp-gcc
	sed -i 's/CONFIG_RTE_KNI_KMOD=y/CONFIG_RTE_KNI_KMOD=n/' ix/deps/dpdk/build/.config
	cd memcached && ./autogen.sh && ./configure
	cd memcached-ix && ./autogen.sh && ./configure --with-ix=../zygos
	$(MAKE) -C ix/deps/dpdk
	$(MAKE) -C zygos/deps/dpdk
	$(MAKE) all

full-clean: clean
	rm -fr ix/deps/dpdk/build
	rm -fr zygos/deps/dpdk/build
