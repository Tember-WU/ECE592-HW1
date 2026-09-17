#pragma once
#include "pmu.hpp"

static void save_ticks(const char *path, const uint64_t *values, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f || fwrite(values, sizeof(*values), n, f) != n) fail("raw output");
    if (fclose(f)) fail("raw close");
}

static void log_usage(const struct rusage& before, const struct rusage& after) {
    fprintf(stderr, "cpu_end=%d minor_faults=%ld major_faults=%ld voluntary_switches=%ld involuntary_switches=%ld\n",
            sched_getcpu(), after.ru_minflt - before.ru_minflt, after.ru_majflt - before.ru_majflt,
            after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw);
}

/* Report the mapping containing the workload. A malloc mapping may also
 * contain other allocations; its size is not the working-set size. */
static void log_mapping(const void *base, const char *phase) {
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f) fail("smaps");
    char line[512];
    unsigned long lo = 0, hi = 0, selected_lo = 0;
    bool selected = false;
    fprintf(stderr, "mapping_%s base=%p cpu=%d\n", phase, base, sched_getcpu());
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "%lx-%lx", &lo, &hi) == 2) {
            selected = (uintptr_t)base >= lo && (uintptr_t)base < hi;
            if (selected) selected_lo = lo;
        }
        if (selected && (!strncmp(line, "AnonHugePages:", 14) ||
                         !strncmp(line, "KernelPageSize:", 15) || !strncmp(line, "Size:", 5)))
            fprintf(stderr, "%s", line);
    }
    fclose(f);
    f = fopen("/proc/self/numa_maps", "r");
    if (!f) fail("numa_maps");
    while (fgets(line, sizeof(line), f))
        if (sscanf(line, "%lx", &lo) == 1 && lo == selected_lo)
            fprintf(stderr, "numa_mapping: %s", line);
    fclose(f);
}
