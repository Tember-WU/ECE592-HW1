CC = gcc
CFLAGS = -O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)
BINARY = $(BUILD)/latency_bench
ARCH := $(shell $(CC) -dumpmachine)
ifneq (,$(findstring aarch64,$(ARCH)))
OBJDUMP_FLAGS =
else
OBJDUMP_FLAGS = -Mintel
endif

all: benchmark assembly
benchmark: $(BINARY)
$(BINARY): src/latency_bench.c src/timing.h Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) src/latency_bench.c -o $@
assembly: $(BINARY)
	objdump -d $(OBJDUMP_FLAGS) $(BINARY) > $(BUILD)/latency_bench.dis
check: benchmark
	python3 -m unittest discover -s tests -v
clean:
	rm -f $(BINARY) $(BUILD)/latency_bench.dis
.PHONY: all benchmark assembly check clean
