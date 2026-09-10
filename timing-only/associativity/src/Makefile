# Makefile for associativity_bench
# Usage: make all  (or just 'make')
#        make clean

CXX = g++
CXXFLAGS = -O0 -g -std=c++11 -m64 -Wall -Wextra -fno-omit-frame-pointer
TARGET = associativity_bench
SOURCES = associativity_bench.cpp

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f $(TARGET)

.PHONY: all clean