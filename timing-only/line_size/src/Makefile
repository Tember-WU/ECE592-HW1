# Skylark, Artemisia (x86_64) and the AArch64 machine (Thunderbird / Ampere Altra).
#
# Usage: make all   (or just 'make')
#        make clean

CXX = g++
UNAME_M := $(shell uname -m)

COMMON_FLAGS = -O0 -g -std=c++11 -Wall -Wextra -fno-omit-frame-pointer

# -m64 is an x86-only flag; aarch64-linux-gnu-g++ does not understand it and will error.
ifeq ($(UNAME_M),x86_64)
    CXXFLAGS = $(COMMON_FLAGS) -m64
else
    CXXFLAGS = $(COMMON_FLAGS)
endif

TARGETS = line_size_bench

all: $(TARGETS)

# associativity_bench: associativity_bench.cpp timer_compat.h
#	$(CXX) $(CXXFLAGS) -o $@ associativity_bench.cpp

line_size_bench: line_size_bench.cpp timer_compat.h
	$(CXX) $(CXXFLAGS) -o $@ line_size_bench.cpp

clean:
	rm -f $(TARGETS)

.PHONY: all clean