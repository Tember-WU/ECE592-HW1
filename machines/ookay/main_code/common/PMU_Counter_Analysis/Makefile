CXX ?= g++
CXXFLAGS = -O0 -g -std=c++11 -Wall -Wextra
.PHONY: all clean test
all: build/bench build/bench.dis
build/bench: src/bench.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $< -o $@
build/bench.dis: build/bench
	objdump -d -C $< > $@
test: all
	python3 -m unittest discover -s tests -v
clean:
	rm -rf build
