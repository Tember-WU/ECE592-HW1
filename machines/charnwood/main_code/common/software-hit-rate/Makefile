CC = gcc
CFLAGS = -O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)

all: $(BUILD)/hit_rate $(BUILD)/verify_hit_rate

$(BUILD)/hit_rate: src/hit_rate.c src/kernel.h Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) src/hit_rate.c -o $@
	objdump -d $@ > $@.dis

$(BUILD)/verify_hit_rate: src/hit_rate.c src/kernel.h src/pmu.h Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -DWITH_PMU src/hit_rate.c -o $@
	objdump -d $@ > $@.dis

check: all
	python3 -m unittest discover -s tests -v

.PHONY: all check
