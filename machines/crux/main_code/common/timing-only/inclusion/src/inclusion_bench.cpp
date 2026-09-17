// inclusion_bench.cpp
// Experiment 5: Inclusion / exclusion behavior (TA slides 17-18)
//
// Implements three sub-modes, run in order per machine:
//
//   1. calibrate     -> build reference single-access latency distributions
//                        for L2-resident, LLC-resident, and DRAM-resident
//                        lines. Used to set the two classification thresholds.
//
//   2. find_conflict  -> empirically search for a (stride, K) pair that
//                        forms a real LLC conflict set on THIS machine
//                        (LLC is physically indexed and often sliced/hashed,
//                        so we cannot just compute the index bits the way
//                        associativity_bench.cpp does for the VIPT L1D).
//                        This reuses the eviction-probability sweep idea
//                        from Experiment 3, but the "hit" class we watch
//                        for eviction out of is LLC-resident, not L1-resident.
//
//   3. test           -> the actual inclusion/exclusion trial from slide 18:
//                        make target T resident in L1/L2, pressure ONLY the
//                        LLC with a conflict ring that (as far as we can
//                        verify) does not also map to T's L2 set, reload T,
//                        classify the reload against the calibrated
//                        thresholds, repeat over many targets/sets/trials.
//
// Build: g++ -O0 -g -std=c++11 -m64 -Wall -Wextra -fno-omit-frame-pointer \
//            -o inclusion_bench inclusion_bench.cpp
//
// IMPORTANT CAVEATS (read before trusting the output):
//  - We assume L1D/L2 set-index bits live within the page offset (VIPT-style,
//    consistent with what associativity_bench.cpp already assumed and what
//    slide 16 states). If a machine's L2 is not indexed this way the
//    "does not touch T's L2 set" filter in `test` mode is only a best-effort
//    heuristic, not a proof. Say so in the report.
//  - LLC slicing/hashing on many Intel chips means a single linear stride
//    will NOT produce a clean conflict set. `find_conflict` searches
//    empirically and reports its own eviction probability at the K you
//    give it; treat anything below ~0.8 as "did not find a usable set" and
//    try other strides/alignments before trusting `test` output.
//  - Single-access (non-batched) timing is inherently noisier than the
//    batched timing used in Experiments 1-4 (slide 11). We rely on the
//    fact that DRAM vs LLC vs L2/L1 gaps are large (tens to hundreds of
//    ticks) relative to that noise, but you must still look at the full
//    distribution (the CSV keeps every sample), not just a mean.

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <random>
#include <string>
#include <unistd.h>

// ---------------- Timer ----------------
// x86-64 (Sunbird, Charnwood, Ookay, Upgrade, Crux, Skylark, Artemisia):
// fenced RDTSC/RDTSCP, TA slide 5.
// AArch64 (Thunderbird, Ampere Altra): the Generic Timer via CNTVCT_EL0,
// bracketed with DSB SY + ISB, TA slide 6. Ticks are NOT the same unit or
// rate across architectures -- that's fine here because every threshold
// this program computes (calibrate's medians/boundaries) is derived and
// consumed on the SAME machine in the SAME run; nothing compares raw tick
// counts across machines.
#if defined(__x86_64__) || defined(__i386__)
#include <x86intrin.h>

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

#elif defined(__aarch64__)

static inline uint64_t arm_cnt() {
    uint64_t t;
    __asm__ __volatile__(
        "dsb sy\n\t"
        "isb\n\t"
        "mrs %0, cntvct_el0\n\t"
        "isb\n\t"
        : "=r"(t) :: "memory");
    return t;
}
// Same call used for both start and stop: DSB SY drains outstanding memory
// accesses before the read (covers the "wait for prior loads" role RDTSCP
// plays on x86), ISB before and after fences the pipeline around the MRS.
static inline uint64_t tsc_start() { return arm_cnt(); }
static inline uint64_t tsc_stop()  { return arm_cnt(); }

#else
#error "Unsupported architecture: add a tsc_start/tsc_stop pair for it."
#endif

struct Node { uintptr_t next; };

// ---------------- Allocation ----------------
void* allocate_buffer(size_t size) {
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

// Build a randomized cycle over `count` nodes spaced `stride` bytes apart,
// starting at `base`. Same construction as associativity_bench.cpp.
void build_cycle(Node* base, size_t stride, size_t count, uint32_t seed) {
    if (count == 0) return;
    if (count == 1) { base->next = reinterpret_cast<uintptr_t>(base); return; }
    std::vector<size_t> order(count);
    for (size_t i = 0; i < count; ++i) order[i] = i;
    std::mt19937 rng(seed);
    std::shuffle(order.begin(), order.end(), rng);
    for (size_t i = 0; i < count; ++i) {
        size_t cur = order[i];
        size_t nxt = order[(i + 1) % count];
        Node* cur_node = reinterpret_cast<Node*>(reinterpret_cast<char*>(base) + cur * stride);
        Node* nxt_node = reinterpret_cast<Node*>(reinterpret_cast<char*>(base) + nxt * stride);
        cur_node->next = reinterpret_cast<uintptr_t>(nxt_node);
    }
}

// Chase a built cycle `laps` times through all `count` nodes (read-only,
// dependent chain). Returns the pointer position afterward.
Node* chase(Node* p, size_t steps) {
    for (size_t i = 0; i < steps; ++i) p = reinterpret_cast<Node*>(p->next);
    return p;
}

// ---------------- Config ----------------
struct Config {
    std::string mode;      // sweep_capacity | calibrate | find_conflict | test
    std::string outfile;
    uint32_t seed = 701;
    size_t warmup = 1000;

    // sweep_capacity
    size_t min_bytes = 16 * 1024;
    size_t max_bytes = 128 * 1024 * 1024;
    size_t sc_batch = 512;
    size_t sc_samples = 2000;

    // calibrate
    size_t l2_bytes = 0;
    size_t llc_bytes = 0;
    size_t dram_bytes = 0;
    size_t line_size = 64;
    size_t cal_samples = 200000;

    // find_conflict
    size_t candidate_stride = 0;   // bytes between conflicting lines
    size_t k = 0;                  // number of conflicting lines to test
    size_t fc_samples = 20000;
    uint64_t llc_hit_thresh = 0;   // ticks; from calibrate step
    uint64_t dram_thresh = 0;      // ticks; from calibrate step

    // test
    size_t llc_stride = 0;         // stride found by find_conflict
    size_t pressure_k = 0;         // conflict-ring size (> LLC ways)
    size_t l2_sets = 0;            // from Experiment 3 result for this machine
    size_t num_targets = 20;       // distinct T addresses / LLC "sets" to sample
    size_t num_trials = 2000;      // repeats per target
    size_t target_gap = 4 * 1024 * 1024; // bytes between independent target regions
    uint64_t l2_dram_boundary = 0; // ticks: classify reload < this as L2-ish
    uint64_t llc_dram_boundary = 0;// ticks: classify reload < this as LLC-ish (else DRAM-ish)
};

bool parse_args(int argc, char** argv, Config& c) {
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() { return std::string(argv[++i]); };
        if (a == "--mode") c.mode = next();
        else if (a == "--output") c.outfile = next();
        else if (a == "--seed") c.seed = std::stoul(next());
        else if (a == "--warmup") c.warmup = std::stoul(next());
        else if (a == "--min_bytes") c.min_bytes = std::stoul(next());
        else if (a == "--max_bytes") c.max_bytes = std::stoul(next());
        else if (a == "--sc_batch") c.sc_batch = std::stoul(next());
        else if (a == "--sc_samples") c.sc_samples = std::stoul(next());
        else if (a == "--l2_bytes") c.l2_bytes = std::stoul(next());
        else if (a == "--llc_bytes") c.llc_bytes = std::stoul(next());
        else if (a == "--dram_bytes") c.dram_bytes = std::stoul(next());
        else if (a == "--line_size") c.line_size = std::stoul(next());
        else if (a == "--cal_samples") c.cal_samples = std::stoul(next());
        else if (a == "--candidate_stride") c.candidate_stride = std::stoul(next());
        else if (a == "--k") c.k = std::stoul(next());
        else if (a == "--fc_samples") c.fc_samples = std::stoul(next());
        else if (a == "--llc_hit_thresh") c.llc_hit_thresh = std::stoull(next());
        else if (a == "--dram_thresh") c.dram_thresh = std::stoull(next());
        else if (a == "--llc_stride") c.llc_stride = std::stoul(next());
        else if (a == "--pressure_k") c.pressure_k = std::stoul(next());
        else if (a == "--l2_sets") c.l2_sets = std::stoul(next());
        else if (a == "--num_targets") c.num_targets = std::stoul(next());
        else if (a == "--num_trials") c.num_trials = std::stoul(next());
        else if (a == "--target_gap") c.target_gap = std::stoul(next());
        else if (a == "--l2_dram_boundary") c.l2_dram_boundary = std::stoull(next());
        else if (a == "--llc_dram_boundary") c.llc_dram_boundary = std::stoull(next());
        else { std::cerr << "Unknown arg: " << a << "\n"; return false; }
    }
    if (c.mode.empty() || c.outfile.empty()) {
        std::cerr << "Required: --mode {calibrate|find_conflict|test} --output FILE\n";
        return false;
    }
    return true;
}

// ---------------- sweep_capacity ----------------
// A self-contained, mini Experiment-1-style capacity sweep (slide 14),
// so this tool does NOT depend on your team's earlier Experiment 1/3
// numbers being on hand or correct. For each footprint size (powers of two
// from min_bytes to max_bytes), build a randomized cycle covering that many
// bytes, warm it, then time a large BATCH of dependent accesses (same
// batching method as associativity_bench.cpp / line_size_bench.cpp, see
// slide 11) and report the median per-access latency. Run this once per
// machine; the Python driver finds the two biggest steps in the resulting
// curve (L1/L2 boundary is irrelevant here, we only need the L2->LLC step
// and the LLC->DRAM step) and uses those footprints directly as
// `llc_bytes`-adjacent and `dram_bytes` inputs to `calibrate`, no manual
// cache-size input required.
// Warm a `count`-node cycle by chasing it, but bound the TOTAL number of
// dependent accesses regardless of how large `count` or `requested_laps`
// are. Without this bound, warmup cost is requested_laps * count, which
// silently explodes for large footprints (e.g. 1000 laps over a 128 MiB /
// 2,097,152-node footprint is ~2 billion dependent loads for ONE data
// point). We always do at least one full lap (so every line is touched at
// least once) and never more than `warmup_cap` total accesses.
static const size_t WARMUP_CAP_DEFAULT = 20 * 1000 * 1000; // ~20M dependent loads, a few seconds worst case
Node* bounded_warmup(Node* p, size_t count, size_t requested_laps, size_t warmup_cap = WARMUP_CAP_DEFAULT) {
    size_t total = requested_laps * count;
    if (total < count) total = count;           // at least one full lap
    if (total > warmup_cap) total = std::max(count, warmup_cap);
    return chase(p, total);
}

void run_sweep_capacity(const Config& c) {
    std::ofstream out(c.outfile);
    out << "footprint_bytes,median_ticks_per_access\n";

    for (size_t footprint = c.min_bytes; footprint <= c.max_bytes; footprint *= 2) {
        size_t count = footprint / c.line_size;
        if (count < 2) count = 2;
        void* raw = allocate_buffer(count * c.line_size + c.line_size);
        Node* base = reinterpret_cast<Node*>(raw);
        build_cycle(base, c.line_size, count, c.seed);

        Node* p = base;
        p = bounded_warmup(p, count, c.warmup);

        std::vector<uint64_t> lat;
        lat.reserve(c.sc_samples);
        for (size_t s = 0; s < c.sc_samples; ++s) {
            uint64_t t0 = tsc_start();
            p = chase(p, c.sc_batch);
            uint64_t t1 = tsc_stop();
            lat.push_back(t1 - t0);
        }
        std::sort(lat.begin(), lat.end());
        double med = (double)lat[lat.size() / 2] / (double)c.sc_batch;
        out << footprint << "," << med << "\n";
        std::cerr << "footprint=" << footprint << " median_ticks_per_access=" << med << "\n";
        free(raw);
    }
    out.close();
}

// ---------------- calibrate ----------------
// Produces one CSV with columns: class,ticks
// class in {L2, LLC, DRAM}. Each is a SINGLE-ACCESS (not batched) reload
// latency after making that resident region hot, matching the single-access
// measurement `test` uses in the actual trial (slide 18's "reload T" step).
void run_calibrate(const Config& c) {
    std::ofstream out(c.outfile);
    out << "class,ticks\n";

    struct ClassSpec { const char* name; size_t bytes; };
    std::vector<ClassSpec> classes = {
        {"L2",   c.l2_bytes},
        {"LLC",  c.llc_bytes},
        {"DRAM", c.dram_bytes},
    };

    for (auto& cs : classes) {
        size_t count = cs.bytes / c.line_size;
        if (count < 2) count = 2;
        void* raw = allocate_buffer(count * c.line_size + c.line_size);
        Node* base = reinterpret_cast<Node*>(raw);
        build_cycle(base, c.line_size, count, c.seed);

        // Warm the whole region into the target level by chasing it repeatedly.
        Node* p = base;
        p = bounded_warmup(p, count, c.warmup);

        // Single-access timing: bracket exactly ONE dependent load per sample,
        // matching the reload step in `test`.
        for (size_t s = 0; s < c.cal_samples; ++s) {
            uint64_t t0 = tsc_start();
            p = reinterpret_cast<Node*>(p->next);
            uint64_t t1 = tsc_stop();
            out << cs.name << "," << (t1 - t0) << "\n";
        }
        free(raw);
        std::cerr << "calibrated class " << cs.name << " (" << cs.bytes << " bytes, "
                  << count << " lines)\n";
    }
    out.close();
}

// ---------------- find_conflict ----------------
// Same eviction-probability idea as associativity_bench.cpp, but aimed at
// the LLC: build a K-line conflict ring at the given candidate_stride, warm
// the FIRST line so it is LLC-resident, chase the other K-1 ring lines, then
// reload line 0 and see whether it now looks like a DRAM access (evicted
// from the LLC) rather than an LLC hit. Sweep K and/or stride externally
// (from the Python driver) until eviction_probability climbs to ~1.0 for
// K > (assumed LLC ways) and stays ~0 for K <= ways -- that is your evidence
// the stride actually conflates LLC sets on this machine.
void run_find_conflict(const Config& c) {
    if (c.candidate_stride == 0 || c.k == 0 || c.llc_hit_thresh == 0 || c.dram_thresh == 0) {
        std::cerr << "find_conflict requires --candidate_stride --k --llc_hit_thresh --dram_thresh\n";
        exit(1);
    }
    size_t total = c.k * c.candidate_stride + c.line_size;
    void* raw = allocate_buffer(total);
    Node* base = reinterpret_cast<Node*>(raw);
    build_cycle(base, c.candidate_stride, c.k, c.seed);

    uint64_t mid = (c.llc_hit_thresh + c.dram_thresh) / 2;

    std::ofstream out(c.outfile);
    out << "trial,reload_ticks,classified_evicted\n";
    size_t evictions = 0;
    Node* p = base;

    for (size_t s = 0; s < c.fc_samples; ++s) {
        // Re-warm line 0 into LLC (a handful of direct hits on node 0 itself).
        p = base;
        for (size_t w = 0; w < 8; ++w) p = reinterpret_cast<Node*>(base->next), p = base;

        // Chase the remaining K-1 ring lines (pressure), ending back at node 0's
        // predecessor so ->next is node 0.
        p = base;
        for (size_t i = 0; i < c.k - 1; ++i) p = reinterpret_cast<Node*>(p->next);

        uint64_t t0 = tsc_start();
        Node* q = reinterpret_cast<Node*>(p->next); // reload of node 0 (or whichever line the cycle put here)
        (void)q;
        uint64_t t1 = tsc_stop();
        uint64_t delta = t1 - t0;
        bool evicted = delta > mid;
        if (evicted) evictions++;
        out << s << "," << delta << "," << (evicted ? 1 : 0) << "\n";
    }
    out.close();
    free(raw);
    double prob = (double)evictions / (double)c.fc_samples;
    std::cerr << "stride=" << c.candidate_stride << " K=" << c.k
              << " eviction_probability=" << prob << "\n";
}

// ---------------- test ----------------
// The actual inclusion/exclusion trial (slide 18):
//   1. calibrate (done separately, thresholds passed in)
//   2. place T: make it resident in L1/L2 (chase it directly, repeatedly)
//   3. pressure ONLY the LLC: chase a conflict ring (found by find_conflict)
//      that shares T's LLC set/slice behavior but is filtered, on a best
//      effort basis, to avoid T's L2 set (see the l2_sets filter below)
//   4. reload T, single access, classify against the two thresholds
//   5. repeat over many independent targets ("sets") and many trials each
void run_test(const Config& c) {
    if (c.llc_stride == 0 || c.pressure_k == 0 || c.l2_dram_boundary == 0 || c.llc_dram_boundary == 0) {
        std::cerr << "test requires --llc_stride --pressure_k --l2_dram_boundary --llc_dram_boundary\n";
        exit(1);
    }

    std::ofstream out(c.outfile);
    out << "target_id,trial,reload_ticks,classification,l2_set_index_of_target,l2_set_index_min_pressure_line\n";

    size_t region_bytes = c.pressure_k * c.llc_stride + c.line_size;

    for (size_t tgt = 0; tgt < c.num_targets; ++tgt) {
        void* raw = allocate_buffer(region_bytes);
        Node* base = reinterpret_cast<Node*>(raw);
        // Target T is node 0 of this region. Pressure ring = nodes 0..K-1
        // spaced llc_stride apart, i.e. node 0 IS part of the ring (matches
        // find_conflict's convention: reloading node 0 after chasing K-1
        // others tells you whether T got evicted).
        uint32_t seed = c.seed + (uint32_t)(tgt * 97 + 13);
        build_cycle(base, c.llc_stride, c.pressure_k, seed);

        // Best-effort L2-set bookkeeping (VIPT assumption, see file header
        // caveats): if the low bits (mod l2_sets*line_size window) of a
        // pressure line's address equal T's, that line ALSO maps to T's L2
        // set and would confound the "L2 untouched" claim. We just record
        // this so the Python side can flag/filter trials, rather than
        // silently pretending every trial is clean.
        long target_l2_set = -1, min_pressure_l2_set = -1;
        if (c.l2_sets > 0) {
            uintptr_t t_addr = reinterpret_cast<uintptr_t>(base);
            target_l2_set = (long)((t_addr / c.line_size) % c.l2_sets);
            long best = -1; bool found_same = false;
            for (size_t i = 1; i < c.pressure_k; ++i) {
                uintptr_t addr = t_addr + i * c.llc_stride;
                long s2 = (long)((addr / c.line_size) % c.l2_sets);
                if (best == -1) best = s2;
                if (s2 == target_l2_set) found_same = true;
            }
            min_pressure_l2_set = best;
            if (found_same) {
                std::cerr << "WARNING target " << tgt
                          << ": at least one pressure line shares T's L2 set "
                             "index under the VIPT assumption -- this trial's "
                             "'LLC-only pressure' claim is compromised.\n";
            }
        }

        for (size_t trial = 0; trial < c.num_trials; ++trial) {
            // 2. Place T: pull it into L1/L2 with direct repeated hits.
            Node* p = base;
            for (size_t w = 0; w < c.warmup; ++w) p = reinterpret_cast<Node*>(base->next), p = base;

            // 3. Pressure the (candidate) LLC set only: chase K-1 other ring
            // lines, dependent chain, read-only.
            p = base;
            for (size_t i = 0; i < c.pressure_k - 1; ++i) p = reinterpret_cast<Node*>(p->next);

            // 4. Reload T: single dependent access, fenced.
            uint64_t t0 = tsc_start();
            Node* q = reinterpret_cast<Node*>(p->next);
            (void)q;
            uint64_t t1 = tsc_stop();
            uint64_t delta = t1 - t0;

            const char* cls;
            if (delta < c.l2_dram_boundary) cls = "L2_hit";
            else if (delta < c.llc_dram_boundary) cls = "LLC_hit";
            else cls = "DRAM";

            out << tgt << "," << trial << "," << delta << "," << cls << ","
                << target_l2_set << "," << min_pressure_l2_set << "\n";
        }
        free(raw);
        std::cerr << "target " << tgt << " done\n";
    }
    out.close();
}

int main(int argc, char** argv) {
    Config c;
    if (!parse_args(argc, argv, c)) return 1;
    if (c.mode == "sweep_capacity") run_sweep_capacity(c);
    else if (c.mode == "calibrate") run_calibrate(c);
    else if (c.mode == "find_conflict") run_find_conflict(c);
    else if (c.mode == "test") run_test(c);
    else { std::cerr << "Unknown mode: " << c.mode << "\n"; return 1; }
    return 0;
}