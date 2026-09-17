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

#ifndef MADV_COLLAPSE
#define MADV_COLLAPSE 25 /* Linux UAPI; older glibc headers may omit it. */
#endif

#if !defined(__x86_64__)
#error "This small benchmark implements the x86-64 path used on artemisia."
#endif

/* The entire timed interval is assembly so -O0 adds no stack loads/stores
 * to the dependent chain. Each group contains 16 dependent loads, NOT 16
 * independent streams. Passing zero groups measures the empty timer. */
__attribute__((noinline))
static uint64_t time_batch(void **cursor, uint64_t groups) {
    void *p = *cursor;
    uint64_t ticks;
    __asm__ volatile(
        "lfence\n\t"
        "rdtsc\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax\n\t"
        "mov %%rax, %%r8\n\t"
        "lfence\n\t"
        "test %[groups], %[groups]\n\t"
        "jz 2f\n\t"
        "1:\n\t"
        ".rept 16\n\t"
        "mov (%[p]), %[p]\n\t"
        ".endr\n\t"
        "dec %[groups]\n\t"
        "jnz 1b\n\t"
        "2:\n\t"
        "rdtscp\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax\n\t"
        "sub %%r8, %%rax\n\t"
        "lfence\n\t"
        : "=&a"(ticks), [p] "+&r"(p), [groups] "+&r"(groups)
        : : "rcx", "rdx", "r8", "cc", "memory");
    *cursor = p;
    return ticks;
}

static void fail(const char *what) { perror(what); exit(1); }

static uint64_t rng(uint64_t *state) {
    uint64_t x = *state;
    x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
    *state = x;
    return x * UINT64_C(2685821657736338717);
}

static uint64_t number(const char *s) {
    char *end;
    errno = 0;
    uint64_t n = strtoull(s, &end, 10);
    if (errno || !*s || *end || *s == '-') {
        fprintf(stderr, "Invalid integer: %s\n", s); exit(1);
    }
    return n;
}

/* Only inspect mapping/page placement; never inspect cache geometry. */
static size_t mapping_info(void *base) {
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f) fail("smaps");
    char line[512];
    unsigned long lo, hi;
    int selected = 0;
    size_t huge_kib = 0;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2)
            selected = (uintptr_t)base >= lo && (uintptr_t)base < hi;
        if (selected && (!strncmp(line, "AnonHugePages:", 14) ||
                         !strncmp(line, "KernelPageSize:", 15)))
            fprintf(stderr, "%s", line);
        if (selected) sscanf(line, "AnonHugePages: %zu", &huge_kib);
    }
    fclose(f);
    f = fopen("/proc/self/numa_maps", "r");
    if (!f) fail("numa_maps");
    while (fgets(line, sizeof(line), f))
        if (sscanf(line, "%lx", &lo) == 1 && lo == (uintptr_t)base)
            fprintf(stderr, "numa_mapping: %s", line);
    fclose(f);
    return huge_kib * 1024;
}

int main(int argc, char **argv) {
    if (argc != 10) {
        fprintf(stderr, "Usage: %s bytes spacing random|sequential|empty "
                "samples batch seed cpu huge|base output.u64\n", argv[0]);
        return 1;
    }
    size_t bytes = number(argv[1]), spacing = number(argv[2]);
    const char *mode = argv[3];
    size_t samples = number(argv[4]);
    uint64_t batch = number(argv[5]), seed = number(argv[6]);
    int cpu = (int)number(argv[7]);
    int huge = !strcmp(argv[8], "huge");
    int empty = !strcmp(mode, "empty");
    if (!bytes || spacing < sizeof(void *) || spacing % sizeof(void *) ||
        bytes % spacing || bytes / spacing < 2 || !samples || !seed ||
        !batch || batch % 16 || cpu < 0 || cpu >= CPU_SETSIZE ||
        (strcmp(mode, "random") && strcmp(mode, "sequential") && !empty) ||
        (!huge && strcmp(argv[8], "base"))) {
        fprintf(stderr, "Invalid benchmark parameters\n"); return 1;
    }
    cpu_set_t set;
    CPU_ZERO(&set); CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set)) fail("sched_setaffinity");
    if (sched_getcpu() != cpu) { fprintf(stderr, "Affinity failed\n"); return 1; }

    const size_t alignment = 2 * 1024 * 1024;
    size_t mapped = (bytes + alignment - 1) / alignment * alignment;
    char *original = mmap(NULL, mapped + alignment, PROT_READ | PROT_WRITE,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (original == MAP_FAILED) fail("mmap");
    char *base = (char *)(((uintptr_t)original + alignment - 1) & ~(alignment - 1));
    size_t prefix = (size_t)(base - original), suffix = alignment - prefix;
    if (prefix && munmap(original, prefix)) fail("munmap prefix");
    if (suffix && munmap(base + mapped, suffix)) fail("munmap suffix");
    if (madvise(base, mapped, huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE)) fail("madvise");
    memset(base, 0, mapped); /* first touch AFTER CPU binding */
    /* MADV_HUGEPAGE is only a hint. Require actual THP backing to avoid
     * misclassifying a TLB transition as an LLC capacity boundary. */
    if (huge && madvise(base, mapped, MADV_COLLAPSE)) fail("MADV_COLLAPSE");

    size_t n = bytes / spacing;
    size_t *order = malloc(n * sizeof(*order));
    uint64_t *raw = malloc(samples * sizeof(*raw));
    if (!order || !raw) fail("malloc");
    memset(raw, 0, samples * sizeof(*raw)); /* no output-buffer page faults */
    for (size_t i = 0; i < n; ++i) order[i] = i;
    uint64_t state = seed;
    if (!strcmp(mode, "random"))
        for (size_t i = n - 1; i > 0; --i) {
            size_t j = rng(&state) % (i + 1);
            size_t tmp = order[i]; order[i] = order[j]; order[j] = tmp;
        }
    for (size_t i = 0; i < n; ++i)
        *(void **)(base + order[i] * spacing) = base + order[(i + 1) % n] * spacing;
    void *cursor = base + order[0] * spacing;
    free(order);
    /* Warm every node at least four times and execute >= 1M loads. */
    uint64_t warm = n * 4;
    if (warm < 1048576) warm = 1048576;
    warm = (warm + 15) / 16 * 16;
    time_batch(&cursor, warm / 16);
    fprintf(stderr, "mapping_before:\n");
    if (mapping_info(base) != (huge ? mapped : 0)) {
        fprintf(stderr, "Unexpected page backing before measurement\n"); return 1;
    }
    struct rusage before, after;
    getrusage(RUSAGE_SELF, &before);
    for (size_t i = 0; i < samples; ++i)
        raw[i] = time_batch(&cursor, empty ? 0 : batch / 16);
    getrusage(RUSAGE_SELF, &after);
    fprintf(stderr, "mapping_after:\n");
    if (mapping_info(base) != (huge ? mapped : 0)) {
        fprintf(stderr, "Page backing changed during measurement\n"); return 1;
    }

    FILE *f = fopen(argv[9], "wb");
    if (!f) fail("output");
    if (fwrite(raw, sizeof(*raw), samples, f) != samples) fail("fwrite");
    if (fclose(f)) fail("fclose");
    fprintf(stderr, "bytes=%zu spacing=%zu mode=%s samples=%zu batch=%" PRIu64
            " seed=%" PRIu64 " cpu_start=%d cpu_end=%d warm_loads=%" PRIu64
            " base=%p mapped_bytes=%zu\n", bytes, spacing, mode, samples, batch,
            seed, cpu, sched_getcpu(), warm, (void *)base, mapped);
    fprintf(stderr, "measurement_minor_faults=%ld major_faults=%ld "
            "voluntary_switches=%ld involuntary_switches=%ld\n",
            after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt,
            after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw);
    free(raw);
    if (munmap(base, mapped)) fail("munmap");
    return 0;
}
