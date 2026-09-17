#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <unistd.h>

static void fail(const char *s) { perror(s); exit(1); }
#include "kernel.h"
#ifdef WITH_PMU
#include "pmu.h"
#endif

static uint64_t number(const char *s) {
    char *end;
    errno = 0;
    uint64_t n = strtoull(s, &end, 0);
    if (errno || !*s || *end || *s == '-') {
        fprintf(stderr, "Invalid unsigned integer: %s\n", s); exit(1);
    }
    return n;
}
static uint64_t rng(uint64_t *s) {
    uint64_t x = *s;
    x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
    *s = x;
    return x * UINT64_C(2685821657736338717);
}
static void mapping_log(void *p) {
    FILE *f = fopen("/proc/self/numa_maps", "r");
    if (!f) return;
    char line[4096]; unsigned long lo;
    while (fgets(line, sizeof(line), f))
        if (sscanf(line, "%lx", &lo) == 1 && lo == (uintptr_t)p)
            fprintf(stderr, "mapping: %s", line);
    fclose(f);
}

int main(int argc, char **argv) {
#ifdef WITH_PMU
    const int required = 13;
#else
    const int required = 11;
#endif
    if (argc != required) {
        fprintf(stderr, "Usage: %s bytes spacing samples seed cpu reuse threshold "
                "random|sequential|empty raw.u64 metadata.json"
#ifdef WITH_PMU
                " raw_miss_config raw_loads_config"
#endif
                "\n", argv[0]);
        return 2;
    }
    uint64_t bytes = number(argv[1]), spacing = number(argv[2]);
    uint64_t n = number(argv[3]), seed = number(argv[4]);
    uint64_t cpu = number(argv[5]), reuse = number(argv[6]);
    uint64_t threshold = number(argv[7]);
    int empty = !strcmp(argv[8], "empty");
    if (bytes < 4096 || bytes > UINT64_C(2147483648) || spacing < sizeof(void *) ||
        spacing % sizeof(void *) || bytes % spacing || bytes / spacing < 2 ||
        !n || n > UINT64_C(100000000) || !seed || cpu >= CPU_SETSIZE ||
        !reuse || reuse > 1024 ||
        (strcmp(argv[8], "random") && strcmp(argv[8], "sequential") && !empty)) {
        fprintf(stderr, "Invalid workload configuration\n"); return 2;
    }
    cpu_set_t set;
    CPU_ZERO(&set); CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set)) fail("affinity");
    if (sched_getcpu() != (int)cpu) fail("placement");
    size_t map_bytes = (bytes + 4095) & ~(size_t)4095;
    void *base = mmap(NULL, map_bytes, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (base == MAP_FAILED) fail("mmap chain");
    /* Base pages make runs independent of THP allocation success. */
    if (madvise(base, map_bytes, MADV_NOHUGEPAGE)) fail("base pages");
    memset(base, 0, map_bytes);
    uint64_t nodes = bytes / spacing;
    size_t *order = malloc(nodes * sizeof(*order));
    if (!order) fail("order allocation");
    for (size_t i = 0; i < nodes; ++i) order[i] = i;
    uint64_t state = seed;
    if (!strcmp(argv[8], "random"))
        for (size_t i = nodes - 1; i > 0; --i) {
            size_t j = rng(&state) % (i + 1), t = order[i];
            order[i] = order[j]; order[j] = t;
        }
    for (size_t i = 0; i < nodes; ++i)
        *(void **)((char *)base + order[i] * spacing) =
            (char *)base + order[(i + 1) % nodes] * spacing;
    free(order);
    uint64_t *raw = mmap(NULL, n * 8, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (raw == MAP_FAILED) fail("mmap output");
    if (madvise(raw, n * 8, MADV_NOHUGEPAGE)) fail("output base pages");
    memset(raw, 0, n * 8);
    void *cursor = warm(base, nodes * 4 > 1000000 ? nodes * 4 : 1000000);
    mapping_log(base); mapping_log(raw);
    /* Prime timer/output loop separately; excluded from saved sample count. */
    uint64_t scratch[2048];
    cursor = collect(cursor, scratch, 2048, reuse, empty);
#ifdef WITH_PMU
    open_pmu(number(argv[11]), number(argv[12]));
#endif
    struct rusage before, after;
    getrusage(RUSAGE_SELF, &before);
    int start_cpu = sched_getcpu();
#ifdef WITH_PMU
    start_pmu();
#endif
    cursor = collect(cursor, raw, n, reuse, empty);
#ifdef WITH_PMU
    stop_pmu();
#endif
    int end_cpu = sched_getcpu();
    getrusage(RUSAGE_SELF, &after);
    __asm__ volatile("" : : "r"(cursor) : "memory");
    uint64_t hits = 0;
    for (uint64_t i = 0; i < n; ++i) hits += raw[i] <= threshold;
    FILE *f = fopen(argv[9], "wb");
    if (!f) fail("raw output");
    if (fwrite(raw, 8, n, f) != n || fclose(f)) fail("raw write");
    f = fopen(argv[10], "w");
    if (!f) fail("metadata output");
    fprintf(f, "{\"samples\":%" PRIu64 ",\"target_loads\":%" PRIu64
            ",\"classified_hits\":%" PRIu64 ",\"threshold_ticks\":%" PRIu64
            ",\"cpu_before\":%d,\"cpu_after\":%d,"
            "\"minor_faults\":%ld,\"major_faults\":%ld,"
            "\"voluntary_switches\":%ld,\"involuntary_switches\":%ld,",
            n, empty ? 0 : n, hits, threshold, start_cpu, end_cpu,
            after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt,
            after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw);
#if defined(__x86_64__)
    fprintf(f, "\"timer_unit\":\"TSC ticks/access including fences\",\"timer_hz\":null");
#else
    uint64_t hz;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(hz));
    fprintf(f, "\"timer_unit\":\"CNTVCT ticks/access including barriers\",\"timer_hz\":%" PRIu64, hz);
#endif
#ifdef WITH_PMU
    fprintf(f, ",\"pmu\":{\"l1_misses\":%" PRIu64 ",\"retired_loads\":%" PRIu64
            ",\"time_enabled_ns\":%" PRIu64 ",\"time_running_ns\":%" PRIu64 "}",
            count_for(0), count_for(1), counts.enabled, counts.running);
    close(fds[0]); close(fds[1]);
#else
    fprintf(f, ",\"pmu\":null");
#endif
    fprintf(f, "}\n");
    if (fclose(f)) fail("metadata close");
    munmap(raw, n * 8); munmap(base, map_bytes);
    return start_cpu == (int)cpu && end_cpu == (int)cpu ? 0 : 3;
}
