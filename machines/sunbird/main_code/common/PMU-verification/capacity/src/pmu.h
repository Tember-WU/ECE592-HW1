#ifndef CAPACITY_PMU_H
#define CAPACITY_PMU_H
#include <linux/perf_event.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>

/* Up to four per-thread raw events. Identical workloads may be repeated with
 * smaller pinned groups; an unschedulable group must fail, never scale. */
enum { EVENT_COUNT = 4 };
static int pmu_event_count;
static int pmu_fds[EVENT_COUNT];
static uint64_t pmu_ids[EVENT_COUNT], pmu_configs[EVENT_COUNT];
static struct {
    uint64_t nr, time_enabled, time_running;
    struct { uint64_t value, id; } events[EVENT_COUNT];
} pmu_counts;

static void pmu_open(const char *spec) {
    pmu_event_count = 1;
    for (const char *s = spec; *s; ++s) if (*s == ',') ++pmu_event_count;
    if (pmu_event_count > EVENT_COUNT) {
        fprintf(stderr, "Expected one to four raw event configs\n"); exit(1);
    }
    const char *p = spec;
    for (int i = 0; i < pmu_event_count; ++i) {
        char *end;
        errno = 0;
        pmu_configs[i] = strtoull(p, &end, 0);
        if (errno || end == p || *p == '-' ||
            (i < pmu_event_count - 1 ? *end != ',' : *end != '\0')) {
            fprintf(stderr, "Invalid comma-separated raw event configs\n");
            exit(1);
        }
        p = *end ? end + 1 : end;
        struct perf_event_attr attr = {0};
        attr.type = PERF_TYPE_RAW;
        attr.size = sizeof(attr);
        attr.config = pmu_configs[i];
        attr.disabled = i == 0;
        attr.pinned = i == 0;
        attr.exclude_kernel = 1;
        attr.exclude_hv = 1;
        attr.exclude_guest = 1;
        attr.read_format = PERF_FORMAT_GROUP | PERF_FORMAT_ID |
                           PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
        pmu_fds[i] = (int)syscall(SYS_perf_event_open, &attr, 0, -1,
                                  i == 0 ? -1 : pmu_fds[0], PERF_FLAG_FD_CLOEXEC);
        if (pmu_fds[i] < 0) fail("perf_event_open");
        if (ioctl(pmu_fds[i], PERF_EVENT_IOC_ID, &pmu_ids[i])) fail("PERF_EVENT_IOC_ID");
    }
}

static void pmu_start(void) {
    if (ioctl(pmu_fds[0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP)) fail("PMU reset");
    if (ioctl(pmu_fds[0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP)) fail("PMU enable");
    __asm__ volatile("" ::: "memory");
}

static void pmu_stop(void) {
    __asm__ volatile("" ::: "memory");
    if (ioctl(pmu_fds[0], PERF_EVENT_IOC_DISABLE, PERF_IOC_FLAG_GROUP)) fail("PMU disable");
    ssize_t got = read(pmu_fds[0], &pmu_counts, sizeof(pmu_counts));
    if (got != (ssize_t)((3 + 2 * pmu_event_count) * sizeof(uint64_t)) ||
        pmu_counts.nr != (uint64_t)pmu_event_count ||
        !pmu_counts.time_enabled || !pmu_counts.time_running ||
        pmu_counts.time_running != pmu_counts.time_enabled) {
        fprintf(stderr, "PMU group unscheduled, multiplexed, or invalid: bytes=%zd enabled=%" PRIu64
                        " running=%" PRIu64 "\n", got, pmu_counts.time_enabled, pmu_counts.time_running);
        exit(1);
    }
}

static void pmu_save(const char *path, uint64_t loads) {
    FILE *f = fopen(path, "w");
    if (!f) fail("PMU output");
    fprintf(f, "{\"time_enabled_ns\":%" PRIu64 ",\"time_running_ns\":%" PRIu64
               ",\"chain_loads\":%" PRIu64 ",\"events\":[", pmu_counts.time_enabled,
               pmu_counts.time_running, loads);
    for (int i = 0; i < pmu_event_count; ++i) {
        int found = -1;
        for (int j = 0; j < pmu_event_count; ++j)
            if (pmu_counts.events[j].id == pmu_ids[i]) found = j;
        if (found < 0) { fprintf(stderr, "PMU event ID missing\n"); exit(1); }
        fprintf(f, "%s{\"config\":%" PRIu64 ",\"count\":%" PRIu64 "}",
                i ? "," : "", pmu_configs[i], pmu_counts.events[found].value);
        if (close(pmu_fds[i])) fail("PMU close");
    }
    fprintf(f, "]}\n");
    if (fclose(f)) fail("PMU fclose");
}
#endif
