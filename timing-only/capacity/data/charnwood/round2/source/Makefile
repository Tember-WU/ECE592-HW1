CC = gcc
CFLAGS = -O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)
SOURCE = src/cache_bench.c
BINARY = $(BUILD)/cache_capacity

all: capacity

capacity: $(BINARY)

$(BINARY): $(SOURCE) Makefile
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(SOURCE) -o $@

assembly: $(BINARY)
	objdump -d -Mintel $(BINARY) > $(BUILD)/cache_capacity.dis

check:
	python3 -m unittest discover -s tests -v

clean:
	rm -f $(BINARY) $(BUILD)/cache_capacity.dis

.PHONY: all capacity assembly check clean
