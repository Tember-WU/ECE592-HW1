// line_size_bench.cpp
// Compile: g++ -O0 -g -std=c++11 -m64 -Wall -Wextra -o line_size_bench line_size_bench.cpp
// Usage: ./line_size_bench --stride 64 --alignment 0 --footprint 262144 --batch 1024 --samples 1000000 --warmup 1000 --seed 701 --mode random_lines --output data.csv

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <random>
#include <chrono>
#if defined(__x86_64__) || defined(_M_X64)
#include <x86intrin.h>   // _rdtsc, _rdtscp, _mm_lfence -- x86 only, unused on AArch64
#endif
#include "timer_compat.h"

// =============== Timer ===============
// Forwards to the portable backend so this file compiles on both x86-64 and AArch64
// (Thunderbird) without touching x86 intrinsics directly.
static inline uint64_t tsc_start() { return timer_start(); }
static inline uint64_t tsc_stop()  { return timer_stop(); }

// =============== Parameter parsing ===============
struct Config {
    size_t stride;          // bytes between consecutive nodes
    size_t alignment;       // offset from base (0,16,32,48)
    size_t footprint;       // total working set bytes
    size_t batch;           // number of dependent accesses per timed batch
    size_t samples;         // number of timed batches to collect
    size_t warmup;          // number of warmup batches (excluded)
    uint32_t seed;          // for reproducible randomization
    std::string mode;       // "random_lines", "sequential_lines", "fully_random"
    std::string outfile;    // output CSV file
    size_t group_window;    // grouping window in bytes for random_lines/sequential_lines
                             // traversal ordering (NOT a line-size assumption -- see build_chain)
};

bool parse_args(int argc, char** argv, Config& cfg) {
    cfg.group_window = 0; // 0 = not set; validated below
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--stride" && i+1 < argc) cfg.stride = std::stoul(argv[++i]);
        else if (arg == "--alignment" && i+1 < argc) cfg.alignment = std::stoul(argv[++i]);
        else if (arg == "--footprint" && i+1 < argc) cfg.footprint = std::stoul(argv[++i]);
        else if (arg == "--batch" && i+1 < argc) cfg.batch = std::stoul(argv[++i]);
        else if (arg == "--samples" && i+1 < argc) cfg.samples = std::stoul(argv[++i]);
        else if (arg == "--warmup" && i+1 < argc) cfg.warmup = std::stoul(argv[++i]);
        else if (arg == "--seed" && i+1 < argc) cfg.seed = std::stoul(argv[++i]);
        else if (arg == "--mode" && i+1 < argc) cfg.mode = argv[++i];
        else if (arg == "--group_window" && i+1 < argc) cfg.group_window = std::stoul(argv[++i]);
        else if (arg == "--output" && i+1 < argc) cfg.outfile = argv[++i];
        else { std::cerr << "Unknown or incomplete argument: " << arg << "\n"; return false; }
    }
    if (cfg.stride == 0 || cfg.footprint == 0 || cfg.batch == 0 || cfg.samples == 0 || cfg.outfile.empty()) {
        std::cerr << "Required: --stride, --footprint, --batch, --samples, --output\n";
        return false;
    }
    if (cfg.mode.empty()) cfg.mode = "random_lines";
    // group_window must be explicitly sized to (at least) the largest stride in your sweep
    // (e.g. 512 if you sweep up to 512B) -- see build_chain() for why this must not be a
    // guessed cache-line size. Refuse to silently default to something that could bias results.
    if ((cfg.mode == "random_lines" || cfg.mode == "sequential_lines") &&
        (cfg.group_window == 0 || cfg.group_window < cfg.stride)) {
        std::cerr << "For --mode random_lines/sequential_lines, --group_window is required and "
                     "must be >= --stride (size it to your largest swept stride, not a guessed "
                     "line size).\n";
        return false;
    }
    return true;
}

// =============== Build the pointer chain ===============
// We treat each node as a uintptr_t cell located at base + i * stride.
// The chain is built as a circular linked list.
void build_chain(uintptr_t* base, size_t num_nodes, size_t stride, uint32_t seed, const std::string& mode,
                  size_t group_window) {
    // Create a vector of node indices 0 .. num_nodes-1
    std::vector<size_t> indices(num_nodes);
    for (size_t i = 0; i < num_nodes; ++i) indices[i] = i;

    std::mt19937 rng(seed);

    if (mode == "fully_random") {
        // Shuffle all nodes, then link in that order (no spatial grouping)
        std::shuffle(indices.begin(), indices.end(), rng);
        for (size_t i = 0; i < num_nodes; ++i) {
            size_t cur = indices[i];
            size_t nxt = indices[(i + 1) % num_nodes];
            // Store the address of node nxt into node cur
            uintptr_t* cur_ptr = reinterpret_cast<uintptr_t*>(reinterpret_cast<char*>(base) + cur * stride);
            uintptr_t* nxt_ptr = reinterpret_cast<uintptr_t*>(reinterpret_cast<char*>(base) + nxt * stride);
            *cur_ptr = reinterpret_cast<uintptr_t>(nxt_ptr);
        }
        return;
    }

    // For random_lines or sequential_lines, we group nodes into fixed-size "grouping
    // windows" purely to control traversal order (sequential inside a window, randomized
    // window order) and defeat stream prefetchers.
    //
    // IMPORTANT: this window size must NOT be the candidate cache-line size we are trying
    // to discover -- hardcoding it (e.g. to 64) would guarantee the grouping collapses to
    // one node per window for every stride >= that constant, which mechanically flattens
    // the latency curve at that stride regardless of the true hardware line size. Instead
    // we size the window to the largest stride ever tested (passed in via group_window),
    // so every candidate stride in the sweep still gets >=2 nodes per window and the
    // resulting plateau reflects real cache behavior, not code structure.
    size_t nodes_per_line = group_window / stride;
    if (nodes_per_line == 0) nodes_per_line = 1; // if stride > group_window, each node is its own group

    size_t num_lines = (num_nodes + nodes_per_line - 1) / nodes_per_line;

    // Create a vector of line indices 0 .. num_lines-1
    std::vector<size_t> line_order(num_lines);
    for (size_t i = 0; i < num_lines; ++i) line_order[i] = i;
    if (mode == "random_lines") {
        std::shuffle(line_order.begin(), line_order.end(), rng);
    } // else sequential_lines keeps order

    // Build the chain line by line in the shuffled order
    for (size_t li = 0; li < num_lines; ++li) {
        size_t line_idx = line_order[li];
        size_t start_node = line_idx * nodes_per_line;
        size_t end_node = std::min(start_node + nodes_per_line, num_nodes);

        // Link nodes within the line sequentially (in increasing address order)
        for (size_t i = start_node; i < end_node; ++i) {
            size_t cur = i;
            size_t nxt = (i + 1 < end_node) ? (i + 1) : (line_order[(li + 1) % num_lines] * nodes_per_line);
            // nxt is the first node of the next line in the shuffled order
            uintptr_t* cur_ptr = reinterpret_cast<uintptr_t*>(reinterpret_cast<char*>(base) + cur * stride);
            uintptr_t* nxt_ptr = reinterpret_cast<uintptr_t*>(reinterpret_cast<char*>(base) + nxt * stride);
            *cur_ptr = reinterpret_cast<uintptr_t>(nxt_ptr);
        }
    }
}

// =============== Main measurement ===============
int main(int argc, char** argv) {
    Config cfg;
    if (!parse_args(argc, argv, cfg)) return 1;

    // Allocate aligned buffer
    const size_t alignment = 64;  // we want cache-line alignment
    void* raw = aligned_alloc(alignment, cfg.footprint + cfg.alignment + alignment); // extra for offset
    if (!raw) { std::cerr << "Allocation failed\n"; return 1; }
    char* base = static_cast<char*>(raw) + cfg.alignment;
    // Ensure base is aligned to 64 bytes (already, since raw is 64-aligned and offset is multiple of 8)
    // We'll just use base.

    size_t num_nodes = cfg.footprint / cfg.stride;
    if (num_nodes < 2) { std::cerr << "Too few nodes\n"; return 1; }

    // Build the pointer chain
    build_chain(reinterpret_cast<uintptr_t*>(base), num_nodes, cfg.stride, cfg.seed, cfg.mode,
                cfg.group_window);

    // Find the first node (base)
    uintptr_t* p = reinterpret_cast<uintptr_t*>(base);

    // Warmup
    for (size_t w = 0; w < cfg.warmup; ++w) {
        for (size_t i = 0; i < cfg.batch; ++i) {
            p = reinterpret_cast<uintptr_t*>(*p);
        }
    }
    // volatile sink to prevent optimization
    volatile uintptr_t* sink = p;
    (void)sink;

    // Open output file
    std::ofstream out(cfg.outfile);
    if (!out) { std::cerr << "Cannot open " << cfg.outfile << "\n"; return 1; }

    // Reset p to start
    p = reinterpret_cast<uintptr_t*>(base);

    // Collect samples
    for (size_t s = 0; s < cfg.samples; ++s) {
        uint64_t t0 = tsc_start();
        // Dependent chain
        for (size_t i = 0; i < cfg.batch; ++i) {
            p = reinterpret_cast<uintptr_t*>(*p);
        }
        uint64_t t1 = tsc_stop();
        uint64_t delta = t1 - t0;
        out << delta << '\n';
    }
    out.close();

    // Prevent compiler from discarding p
    volatile uintptr_t* final_p = p;
    (void)final_p;

    free(raw);
    return 0;
}