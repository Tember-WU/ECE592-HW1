CXX = g++
CXXFLAGS = -O0 -g -std=c++11 -Wall -Wextra -Werror -fno-omit-frame-pointer
MACHINE ?= $(shell hostname -s)
BUILD = build/$(MACHINE)
all: $(BUILD)/line_size_pmu
$(BUILD)/line_size_pmu: src/line_size_bench.cpp src/timer_compat.h ../common/pmu.hpp ../common/measurement.hpp Makefile
	mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) src/line_size_bench.cpp -o $@
	objdump -d -Mintel $@ > $(BUILD)/line_size_pmu.dis
.PHONY: all
