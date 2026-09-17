CXX = g++
CXXFLAGS = -O0 -g -std=c++11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)
all: $(BUILD)/associativity_pmu
$(BUILD)/associativity_pmu: src/associativity_bench.cpp src/timer_compat.h ../common/pmu.hpp ../common/measurement.hpp Makefile
	mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) src/associativity_bench.cpp -o $@
	objdump -d -Mintel $@ > $(BUILD)/associativity_pmu.dis
.PHONY: all
