CC = gcc
CFLAGS = -O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)
ARCH := $(shell $(CC) -dumpmachine)
ifneq (,$(findstring aarch64,$(ARCH)))
SOURCE = src/cache_bench_aarch64.c
OBJDUMP_FLAGS =
else
SOURCE = src/cache_bench.c
OBJDUMP_FLAGS = -Mintel
endif
BINARY = $(BUILD)/cache_capacity

all: capacity

capacity: $(BINARY)

$(BINARY): $(SOURCE) Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(SOURCE) -o $@

assembly: $(BINARY)
	objdump -d $(OBJDUMP_FLAGS) $(BINARY) > $(BUILD)/cache_capacity.dis

check:
	python3 -m unittest discover -s tests -v

clean:
	rm -f $(BINARY) $(BUILD)/cache_capacity.dis

.PHONY: all capacity assembly check clean
