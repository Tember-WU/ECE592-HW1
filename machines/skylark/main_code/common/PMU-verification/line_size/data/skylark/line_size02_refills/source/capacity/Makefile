CC = gcc
CFLAGS = -O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)

all: $(BUILD)/cache_capacity_pmu

$(BUILD)/cache_capacity_pmu: src/cache_bench.c src/pmu.h Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) src/cache_bench.c -o $@
	objdump -d -Mintel $@ > $(BUILD)/cache_capacity_pmu.dis

check: all
	python3 -m unittest discover -s tests -v

.PHONY: all check
