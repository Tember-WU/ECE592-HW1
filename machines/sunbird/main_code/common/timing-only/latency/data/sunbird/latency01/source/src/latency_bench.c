#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>
#include "timing.h"

#ifndef MADV_COLLAPSE
#define MADV_COLLAPSE 25
#endif
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Raw arrays require little-endian uint64 values"
#endif

static void fail(const char *what) { perror(what); exit(1); }
static void require(int ok, const char *what) {
    if (!ok) { fprintf(stderr, "%s\n", what); exit(1); }
}
static uint64_t number(const char *s) {
    char *end;
    errno = 0;
    uint64_t n = strtoull(s, &end, 10);
    require(!errno && *s && !*end && *s != '-', "Invalid unsigned integer");
    return n;
}
static uint64_t rng(uint64_t *state) {
    uint64_t x = *state;
    x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
    *state = x;
    return x * UINT64_C(2685821657736338717);
}

/* Four separate dependency streams: throughput diagnostic, never hit latency.
 * They partition the same circular permutation used by the dependent test. */
__attribute__((noinline))
static uint64_t time_independent(void **cursors, uint64_t groups) {
    void *a = cursors[0], *b = cursors[1], *c = cursors[2], *d = cursors[3];
    uint64_t ticks;
#if defined(__x86_64__)
    __asm__ volatile(
        "lfence\n\trdtsc\n\tshl $32, %%rdx\n\tor %%rdx, %%rax\n\t"
        "mov %%rax, %%r8\n\tlfence\n\t"
        "1:\n\t.rept 4\n\t"
        "mov (%[a]), %[a]\n\tmov (%[b]), %[b]\n\t"
        "mov (%[c]), %[c]\n\tmov (%[d]), %[d]\n\t.endr\n\t"
        "dec %[g]\n\tjnz 1b\n\t"
        "rdtscp\n\tshl $32, %%rdx\n\tor %%rdx, %%rax\n\t"
        "sub %%r8, %%rax\n\tlfence\n\t"
        : "=&a"(ticks), [a] "+&r"(a), [b] "+&r"(b), [c] "+&r"(c),
          [d] "+&r"(d), [g] "+&r"(groups)
        : : "rcx", "rdx", "r8", "cc", "memory");
#elif defined(__aarch64__)
    uint64_t start;
    __asm__ volatile(
        "dsb ish\n\tisb\n\tmrs %[start], cntvct_el0\n\tisb\n\t"
        "1:\n\t.rept 4\n\t"
        "ldr %[a], [%[a]]\n\tldr %[b], [%[b]]\n\t"
        "ldr %[c], [%[c]]\n\tldr %[d], [%[d]]\n\t.endr\n\t"
        "subs %[g], %[g], #1\n\tb.ne 1b\n\t"
        "dsb ishld\n\tisb\n\tmrs %[ticks], cntvct_el0\n\tisb\n\t"
        "sub %[ticks], %[ticks], %[start]\n\t"
        : [ticks] "=&r"(ticks), [start] "=&r"(start), [a] "+&r"(a),
          [b] "+&r"(b), [c] "+&r"(c), [d] "+&r"(d), [g] "+&r"(groups)
        : : "cc", "memory");
#endif
    cursors[0] = a; cursors[1] = b; cursors[2] = c; cursors[3] = d;
    return ticks;
}

static void timer_info(void) {
#if defined(__x86_64__)
    puts("{\"timer_unit\":\"TSC ticks\",\"timer_frequency_hz\":null,"
         "\"timer\":\"LFENCE/RDTSC/LFENCE ... RDTSCP/LFENCE\"}");
#elif defined(__aarch64__)
    uint64_t hz, start, end;
    struct timespec a, b, delay = {0, 200000000};
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(hz));
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &a)) fail("clock_gettime");
    __asm__ volatile("isb; mrs %0, cntvct_el0; isb" : "=r"(start) : : "memory");
    while (nanosleep(&delay, &delay)) if (errno != EINTR) fail("nanosleep");
    __asm__ volatile("isb; mrs %0, cntvct_el0; isb" : "=r"(end) : : "memory");
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &b)) fail("clock_gettime");
    double seconds = b.tv_sec - a.tv_sec + (b.tv_nsec - a.tv_nsec) * 1e-9;
    require(hz && end > start && seconds > 0, "Invalid generic timer");
    printf("{\"timer_unit\":\"CNTVCT ticks\",\"timer_frequency_hz\":%" PRIu64
           ",\"observed_frequency_hz\":%.3f,\"timer\":"
           "\"DSB ISH/ISB/CNTVCT/ISB ... DSB ISHLD/ISB/CNTVCT/ISB\"}\n",
           hz, (end - start) / seconds);
#endif
}

/* Only mapping/page/NUMA evidence: never cache geometry. */
static size_t mapping_info(void *base, int report) {
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f) fail("smaps");
    char line[512]; unsigned long lo, hi;
    int selected = 0; size_t huge_kib = 0;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2)
            selected = (uintptr_t)base >= lo && (uintptr_t)base < hi;
        if (selected) {
            sscanf(line, "AnonHugePages: %zu", &huge_kib);
            if (report && (!strncmp(line, "AnonHugePages:", 14) ||
                           !strncmp(line, "KernelPageSize:", 15))) fputs(line, stderr);
        }
    }
    fclose(f);
    if (report) {
        f = fopen("/proc/self/numa_maps", "r");
        if (!f) fail("numa_maps");
        while (fgets(line, sizeof(line), f))
            if (sscanf(line, "%lx", &lo) == 1 && lo == (uintptr_t)base)
                fprintf(stderr, "numa_mapping: %s", line);
        fclose(f);
    }
    return huge_kib * 1024;
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--timer-info")) { timer_info(); return 0; }
    if (argc != 10) {
        fprintf(stderr, "Usage: %s bytes spacing chase|sequential|paired|independent|empty "
                "samples batch seed cpu huge|base output.u64\n", argv[0]);
        return 1;
    }
    size_t bytes = number(argv[1]), spacing = number(argv[2]), samples = number(argv[4]);
    uint64_t batch = number(argv[5]), seed = number(argv[6]), cpu_number = number(argv[7]);
    const char *mode = argv[3];
    int paired = !strcmp(mode, "paired"), independent = !strcmp(mode, "independent");
    int empty = !strcmp(mode, "empty"), sequential = !strcmp(mode, "sequential");
    int huge = !strcmp(argv[8], "huge"), columns = paired ? 2 : 1;
    require(bytes && spacing >= sizeof(void *) && !(spacing % sizeof(void *)) &&
            !(bytes % spacing) && bytes / spacing >= 16 && samples && seed &&
            batch && !(batch % 16) && cpu_number < CPU_SETSIZE &&
            (paired || independent || empty || sequential || !strcmp(mode, "chase")) &&
            (huge || !strcmp(argv[8], "base")), "Invalid benchmark parameters");
    size_t n = bytes / spacing;
    require(!paired || batch <= n / 4, "Paired mode needs at least four batches per cycle");
    require(!independent || !(n % 4), "Independent mode needs four equal cycle segments");
    require(samples <= SIZE_MAX / (sizeof(uint64_t) * columns) &&
            batch <= UINT64_MAX / samples, "Sample/batch size overflow");
    int cpu = (int)cpu_number;
    cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set)) fail("sched_setaffinity");
    require(sched_getcpu() == cpu, "CPU affinity failed");

    size_t alignment = (size_t)sysconf(_SC_PAGESIZE);
    if (huge) {
        FILE *f = fopen("/sys/kernel/mm/transparent_hugepage/hpage_pmd_size", "r");
        if (!f) fail("hpage_pmd_size");
        require(fscanf(f, "%zu", &alignment) == 1, "Invalid THP size"); fclose(f);
    }
    require(alignment && !(alignment & (alignment - 1)) && bytes < SIZE_MAX - 2 * alignment,
            "Invalid alignment/allocation size");
    size_t mapped = (bytes + alignment - 1) / alignment * alignment;
    char *original = mmap(NULL, mapped + alignment, PROT_READ | PROT_WRITE,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (original == MAP_FAILED) fail("mmap");
    char *base = (char *)(((uintptr_t)original + alignment - 1) & ~(alignment - 1));
    size_t prefix = base - original, suffix = alignment - prefix;
    if (prefix && munmap(original, prefix)) fail("munmap prefix");
    if (suffix && munmap(base + mapped, suffix)) fail("munmap suffix");
    if (madvise(base, mapped, huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE)) fail("madvise");
    memset(base, 0, mapped);
    if (huge && mapping_info(base, 0) != mapped && madvise(base, mapped, MADV_COLLAPSE))
        fail("MADV_COLLAPSE: full THP backing unavailable");

    size_t *order = malloc(n * sizeof(*order));
    uint64_t *raw = malloc(samples * columns * sizeof(*raw));
    if (!order || !raw) fail("malloc");
    memset(raw, 0, samples * columns * sizeof(*raw));
    for (size_t i = 0; i < n; ++i) order[i] = i;
    uint64_t state = seed;
    if (!sequential)
        for (size_t i = n - 1; i > 0; --i) {
            size_t j = rng(&state) % (i + 1), tmp = order[i];
            order[i] = order[j]; order[j] = tmp;
        }
    for (size_t i = 0; i < n; ++i)
        *(void **)(base + order[i] * spacing) = base + order[(i + 1) % n] * spacing;
    void *cursor = base + order[0] * spacing, *streams[4], *expected[4];
    for (size_t i = 0; i < 4; ++i) {
        streams[i] = base + order[i * (n / 4)] * spacing;
        size_t advance = empty ? 0 : samples * (independent ? batch / 4 : batch);
        expected[i] = base + order[(i * (n / 4) + advance % n) % n] * spacing;
    }
    free(order);
    uint64_t warm = n * 4;
    if (warm < 1048576) warm = 1048576;
    warm = (warm + 15) / 16 * 16;
    void *warm_cursor = cursor;
    time_batch(&warm_cursor, warm / 16);
    fprintf(stderr, "mapping_before:\n");
    require(mapping_info(base, 1) == (huge ? mapped : 0), "Unexpected page backing before timing");
    struct rusage before, after;
    getrusage(RUSAGE_SELF, &before);
    for (size_t i = 0; i < samples; ++i) {
        if (independent) raw[i] = time_independent(streams, batch / 16);
        else {
            void *again = cursor;
            raw[i * columns] = time_batch(&cursor, empty ? 0 : batch / 16);
            if (paired) {
                /* First pass follows a full-cycle reuse distance; then read the
                 * SAME batch again immediately. Continue at the first pass end.
                 * This is working-set pressure, not guaranteed set-selective eviction. */
                raw[i * columns + 1] = time_batch(&again, batch / 16);
                require(again == cursor, "Paired cursor mismatch");
            }
        }
    }
    getrusage(RUSAGE_SELF, &after);
    for (size_t i = 0; i < (independent ? 4U : 1U); ++i)
        require((independent ? streams[i] : cursor) == expected[i], "Final dependency cursor mismatch");
    fprintf(stderr, "mapping_after:\n");
    require(mapping_info(base, 1) == (huge ? mapped : 0), "Page backing changed during timing");
    FILE *f = fopen(argv[9], "wb");
    if (!f) fail("output");
    if (fwrite(raw, sizeof(*raw), samples * columns, f) != samples * columns) fail("fwrite");
    if (fclose(f)) fail("fclose");
    fprintf(stderr, "bytes=%zu spacing=%zu mode=%s samples=%zu batch=%" PRIu64
            " columns=%d seed=%" PRIu64 " cpu_start=%d cpu_end=%d warm_loads=%" PRIu64
            " mapped_bytes=%zu dependency_result_verified=1\n",
            bytes, spacing, mode, samples, batch, columns, seed, cpu, sched_getcpu(), warm, mapped);
    fprintf(stderr, "measurement_minor_faults=%ld major_faults=%ld voluntary_switches=%ld involuntary_switches=%ld\n",
            after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt,
            after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw);
    free(raw);
    if (munmap(base, mapped)) fail("munmap");
    return 0;
}
