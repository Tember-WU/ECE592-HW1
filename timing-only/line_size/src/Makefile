CXX = g++

CXXFLAGS = -O0 -g -std=c++11 -m64 -Wall -Wextra

TARGET = line_size_bench

SOURCES = line_size_bench.cpp

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCES)

clean:
	rm -f $(TARGET)