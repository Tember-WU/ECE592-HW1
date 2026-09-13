// associativity_bench.cpp
// g++ -O0 -g -std=c++11 -m64 -Wall -Wextra -o associativity_bench associativity_bench.cpp

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <random>
#if defined(__x86_64__) || defined(_M_X64)
#include <x86intrin.h>   // x86 only, unused on AArch64
#endif
#include <sys/mman.h>
#include <unistd.h>
#include "timer_compat.h"

// ---------- Timer ----------
// tsc_start()/tsc_stop() now just forward to the portable backend in timer_compat.h so
// this file compiles unchanged on x86-64 (Sunbird/Charnwood/Ookay/Upgrade/Crux/Skylark/
// Artemisia) and on AArch64 (Thunderbird).
static inline uint64_t tsc_start() { return timer_start(); }
static inline uint64_t tsc_stop()  { return timer_stop(); }

// ---------- Config ----------
struct Config {
    size_t num_sets;          // 64 for L1, 1024 for L2
    size_t line_size;         // 64
    size_t max_k;             // max conflicting lines
    size_t samples;           // number of batches per K
    size_t warmup;
    size_t batch;             // number of dependent accesses per timed batch
    uint32_t seed;
    std::string outfile;
};

bool parse_args(int argc, char** argv, Config& cfg) {
    cfg.line_size = 64;
    cfg.batch = 128;   // default batch size
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--num_sets" && i+1 < argc) cfg.num_sets = std::stoul(argv[++i]);
        else if (arg == "--line_size" && i+1 < argc) cfg.line_size = std::stoul(argv[++i]);
        else if (arg == "--max_k" && i+1 < argc) cfg.max_k = std::stoul(argv[++i]);
        else if (arg == "--samples" && i+1 < argc) cfg.samples = std::stoul(argv[++i]);
        else if (arg == "--warmup" && i+1 < argc) cfg.warmup = std::stoul(argv[++i]);
        else if (arg == "--batch" && i+1 < argc) cfg.batch = std::stoul(argv[++i]);
        else if (arg == "--seed" && i+1 < argc) cfg.seed = std::stoul(argv[++i]);
        else if (arg == "--output" && i+1 < argc) cfg.outfile = argv[++i];
        else { std::cerr << "Unknown arg: " << arg << "\n"; return false; }
    }
    if (cfg.num_sets == 0 || cfg.max_k == 0 || cfg.samples == 0 || cfg.outfile.empty()) {
        std::cerr << "Required: --num_sets, --max_k, --samples, --output\n";
        return false;
    }
    return true;
}

// ---------- Allocation (huge pages for L2) ----------
#include <cerrno>

// Previously this function ignored `use_huge` entirely (always posix_memalign) while
// main() still conditionally called munmap() on the result for the L2 case -- munmap()
// on posix_memalign/malloc memory is undefined behavior. It also meant the L2 test never
// actually got huge-page backing despite claiming to, leaving 4KB-page TLB reach as an
// unaddressed confound with the true L2 capacity boundary (TA Slide 16/19: "use huge
// pages if THP is on").
//
// Fixed: always allocate via mmap (so cleanup is always munmap -- no mismatch), and for
// use_huge==true, round up to a 2MB boundary and madvise(MADV_HUGEPAGE) so Linux
// Transparent Huge Pages has a real chance to back the allocation with 2MB pages. This
// does not require a preconfigured hugetlbfs pool (MAP_HUGETLB would, and may not be
// available/permitted on shared lab machines), so it works across all 8 ECE hosts.
void* allocate_buffer(size_t size, bool use_huge, size_t& out_alloc_size) {
    const size_t HUGE_PAGE = 2 * 1024 * 1024;
    size_t alloc_size = use_huge
        ? ((size + HUGE_PAGE - 1) / HUGE_PAGE) * HUGE_PAGE
        : size;

    void* ptr = mmap(nullptr, alloc_size, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ptr == MAP_FAILED) {
        std::cerr << "FATAL: mmap allocation failed (errno " << errno << ": "
                   << strerror(errno) << ")\n";
        exit(1);
    }

    if (use_huge) {
        if (madvise(ptr, alloc_size, MADV_HUGEPAGE) != 0) {
            std::cerr << "WARNING: madvise(MADV_HUGEPAGE) failed (errno " << errno
                       << ": " << strerror(errno) << "). Continuing on regular 4KB "
                          "pages -- record this in your report, since this machine's L2 "
                          "result is then more exposed to a TLB-reach confound than "
                          "machines where THP was granted.\n";
        }
    }

    // First-touch every page so it is actually backed (and, for THP, eligible for
    // promotion to a 2MB page) before any timing begins. This also satisfies the
    // handout's first-touch-after-pinning locality requirement, since the process is
    // already pinned (via taskset) by the time main() reaches this call.
    volatile char* p = (char*)ptr;
    for (size_t i = 0; i < alloc_size; i += 4096) p[i] = 0;

    out_alloc_size = alloc_size;
    return ptr;
}

// ---------- Node and conflict cycle ----------
struct Node { uintptr_t next; };

void build_conflict_cycle(Node* base, size_t set_stride, size_t K, uint32_t seed) {
    if (K < 2) {
        if (K == 1) base->next = reinterpret_cast<uintptr_t>(base);
        return;
    }
    std::vector<size_t> order(K);
    for (size_t i = 0; i < K; ++i) order[i] = i;
    std::mt19937 rng(seed);
    std::shuffle(order.begin(), order.end(), rng);
    for (size_t i = 0; i < K; ++i) {
        size_t cur = order[i];
        size_t nxt = order[(i + 1) % K];
        Node* cur_node = reinterpret_cast<Node*>(reinterpret_cast<char*>(base) + cur * set_stride);
        Node* nxt_node = reinterpret_cast<Node*>(reinterpret_cast<char*>(base) + nxt * set_stride);
        cur_node->next = reinterpret_cast<uintptr_t>(nxt_node);
    }
}

// ---------- Measure for a given K ----------
struct Result {
    double eviction_prob;
    double median_latency;
};

Result measure_K(Node* base, size_t set_stride, size_t K,
                 size_t samples, size_t warmup, size_t batch,
                 uint64_t hit_threshold, uint64_t miss_threshold,
                 uint32_t seed) {
    build_conflict_cycle(base, set_stride, K, seed);
    Node* p = base;
    // warmup
    for (size_t w = 0; w < warmup; ++w)
        for (size_t i = 0; i < K; ++i) p = reinterpret_cast<Node*>(p->next);

    uint64_t threshold = (hit_threshold + miss_threshold) / 2;
    std::vector<uint64_t> latencies;
    latencies.reserve(samples);
    size_t evictions = 0;
    p = base;

    for (size_t s = 0; s < samples; ++s) {
        // chase K-1 conflicting lines
        for (size_t i = 0; i < K-1; ++i) p = reinterpret_cast<Node*>(p->next);
        // now p points to the last conflicting line; its next is the target (base)
        uint64_t t0 = tsc_start();
        // access the target batch times in a dependent chain
        Node* q = reinterpret_cast<Node*>(p->next); // first target access
        for (size_t i = 0; i < batch; ++i) {
            q = reinterpret_cast<Node*>(q->next);
        }
        uint64_t t1 = tsc_stop();
        uint64_t delta = t1 - t0;
        latencies.push_back(delta);
        // BUG FIX: hit_threshold/miss_threshold (and therefore `threshold`) are already
        // raw batch-total tick counts, the same units as `delta` -- both come from timing
        // one full batch of `batch` dependent accesses. The previous comparison
        // `delta > threshold * batch` multiplied by batch a second time, inflating the
        // threshold by ~100x and making it essentially unreachable, so
        // eviction_probability stayed near 0 regardless of true cache behavior. Compare
        // directly instead.
        if (delta > threshold) evictions++;
        p = base; // reset to start
    }

    std::sort(latencies.begin(), latencies.end());
    double med = (double)latencies[samples/2] / (double)batch; // per-access latency
    return {(double)evictions / (double)samples, med};
}

// ---------- Calibration (using batched latencies) ----------
void calibrate(Node* base, size_t set_stride, size_t max_k, size_t warmup, size_t batch,
               uint64_t& hit_threshold, uint64_t& miss_threshold, uint32_t seed) {
    const size_t CAL_SAMPLES = 100000;
    // Hit: K=1
    build_conflict_cycle(base, set_stride, 1, seed);
    Node* p = base;
    for (size_t w = 0; w < warmup; ++w) p = reinterpret_cast<Node*>(p->next);
    std::vector<uint64_t> hit(CAL_SAMPLES);
    for (size_t i = 0; i < CAL_SAMPLES; ++i) {
        uint64_t t0 = tsc_start();
        Node* q = p;
        for (size_t b = 0; b < batch; ++b) q = reinterpret_cast<Node*>(q->next);
        uint64_t t1 = tsc_stop();
        hit[i] = t1 - t0;
    }
    std::sort(hit.begin(), hit.end());
    hit_threshold = hit[static_cast<size_t>(0.95 * CAL_SAMPLES)]; // 95th percentile

    // Miss: K = max_k
    build_conflict_cycle(base, set_stride, max_k, seed + 1);
    p = base;
    for (size_t w = 0; w < warmup; ++w)
        for (size_t i = 0; i < max_k; ++i) p = reinterpret_cast<Node*>(p->next);
    std::vector<uint64_t> miss(CAL_SAMPLES);
    for (size_t i = 0; i < CAL_SAMPLES; ++i) {
        // chase max_k-1 conflicting lines, then time batch of target accesses
        for (size_t j = 0; j < max_k-1; ++j) p = reinterpret_cast<Node*>(p->next);
        uint64_t t0 = tsc_start();
        Node* q = reinterpret_cast<Node*>(p->next);
        for (size_t b = 0; b < batch; ++b) q = reinterpret_cast<Node*>(q->next);
        uint64_t t1 = tsc_stop();
        miss[i] = t1 - t0;
        p = base;
    }
    std::sort(miss.begin(), miss.end());
    miss_threshold = miss[static_cast<size_t>(0.05 * CAL_SAMPLES)]; // 5th percentile
}

// ---------- Main ----------
int main(int argc, char** argv) {
    Config cfg;
    if (!parse_args(argc, argv, cfg)) return 1;

    size_t set_stride = cfg.line_size * cfg.num_sets;
    size_t total_buffer = cfg.max_k * set_stride + cfg.line_size;
    // Always request huge-page backing, not just when num_sets looked "L2-sized".
    // Reasoning: the L1 conflict-set trick (candidate addresses spaced at multiples of
    // num_sets*line_size) is only guaranteed to land in the same real L1 set when the
    // machine's TRUE index+offset bit width fits inside whatever low-address-bit range
    // is guaranteed identical between virtual and physical addresses. A 4KB page only
    // guarantees the low 12 bits; if a machine's real L1 has more sets than assumed
    // (e.g. a 64KiB L1D with more index bits than a typical 32KiB design), a 4KB-page
    // stride is not enough. A 2MB huge page guarantees the low 21 bits, which comfortably
    // covers any plausible L1 design, so requesting huge pages here removes that
    // uncertainty at negligible cost for a small L1 buffer.
    bool use_huge = true;
    size_t alloc_size = 0;
    void* raw = allocate_buffer(total_buffer, use_huge, alloc_size);
    Node* base = reinterpret_cast<Node*>(raw);

    uint64_t hit_thresh, miss_thresh;
    calibrate(base, set_stride, cfg.max_k, cfg.warmup, cfg.batch,
              hit_thresh, miss_thresh, cfg.seed);
    std::cerr << "Hit threshold (95%): " << hit_thresh << " ticks (batch size " << cfg.batch << ")\n";
    std::cerr << "Miss threshold (5%): " << miss_thresh << " ticks\n";

    std::ofstream out(cfg.outfile);
    out << "K,eviction_probability,median_latency\n";

    for (size_t K = 1; K <= cfg.max_k; ++K) {
        Result res = measure_K(base, set_stride, K, cfg.samples, cfg.warmup, cfg.batch,
                               hit_thresh, miss_thresh, cfg.seed + K * 100);
        out << K << "," << res.eviction_prob << "," << res.median_latency << "\n";
        std::cerr << "K=" << K << " P=" << res.eviction_prob << " med=" << res.median_latency << "\n";
    }

    out.close();
    // allocate_buffer() always uses mmap() now (regardless of use_huge), so cleanup is
    // always munmap() -- no more posix_memalign/mmap mismatch.
    munmap(raw, alloc_size);
    return 0;
}