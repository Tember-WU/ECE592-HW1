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
#include <x86intrin.h>
#include <sys/mman.h>
#include <unistd.h>

// ---------- Timer ----------
static inline uint64_t tsc_start() {
    _mm_lfence();
    uint64_t t = __rdtsc();
    _mm_lfence();
    return t;
}

static inline uint64_t tsc_stop() {
    unsigned aux;
    _mm_lfence();
    uint64_t t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

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

// ---------- Allocation (huge pages for L2/LLC: physically-indexed levels
//            need physically-contiguous memory or a virtual stride cannot
//            be trusted to land in the same physical cache set) ----------
#include <stdlib.h>   // at the top

static size_t round_up_2mb(size_t size) {
    const size_t H = 2 * 1024 * 1024;
    return ((size + H - 1) / H) * H;
}

void* allocate_buffer(size_t size, bool use_huge) {
    if (!use_huge) {
        void* ptr = nullptr;
        int ret = posix_memalign(&ptr, 4096, size);
        if (ret != 0 || ptr == nullptr) {
            std::cerr << "FATAL: allocation failed (error " << ret << ")\n";
            exit(1);
        }
        volatile char* p = (char*)ptr;
        for (size_t i = 0; i < size; i += 4096) p[i] = 0;
        return ptr;
    }

    // use_huge == true: try explicit hugetlbfs first (guaranteed 2MB physical
    // contiguity), then fall back to THP via madvise (best-effort — verify!).
    size_t hsize = round_up_2mb(size);
    void* ptr = mmap(nullptr, hsize, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, -1, 0);
    bool got_hugetlb = (ptr != MAP_FAILED);
    if (!got_hugetlb) {
        std::cerr << "WARN: MAP_HUGETLB failed (no reserved huge pages?); "
                     "falling back to THP via madvise. VERIFY physical "
                     "contiguity before trusting L2/LLC conflict results "
                     "(check /proc/self/smaps for AnonHugePages).\n";
        ptr = mmap(nullptr, hsize, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (ptr == MAP_FAILED) {
            std::cerr << "FATAL: mmap failed\n";
            exit(1);
        }
        madvise(ptr, hsize, MADV_HUGEPAGE);
    }
    // Touch every 4K page up front so THP has a chance to collapse before
    // the timed region runs, and so hugetlbfs pages are actually faulted in.
    volatile char* p = (char*)ptr;
    for (size_t i = 0; i < hsize; i += 4096) p[i] = 0;
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
        // threshold is already a full-batch total (see calibrate()); delta
        // is also a full-batch total. Do NOT multiply by batch again.
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
    const size_t CAL_SAMPLES = 10000;
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
    bool use_huge = (cfg.num_sets >= 1024); // L2/LLC use huge pages
    if (use_huge) {
        std::cerr << "NOTE: physically-indexed level requested (num_sets="
                  << cfg.num_sets << "). Pin this process to a single core "
                     "within one L2/LLC domain (taskset) — on a multi-CCX "
                     "EPYC part, migrating across CCX/CCD during the run "
                     "invalidates the conflict-set assumption even with "
                     "correct huge pages.\n";
    }
    void* raw = allocate_buffer(total_buffer, use_huge);
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
    if (use_huge) munmap(raw, round_up_2mb(total_buffer));
    else free(raw);
    return 0;
}