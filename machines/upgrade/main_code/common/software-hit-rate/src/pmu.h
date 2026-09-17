#ifndef HIT_RATE_PMU_H
#define HIT_RATE_PMU_H
/* Validation executable only. The estimator is built without this header. */
#include <linux/perf_event.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>

static int fds[2];
static uint64_t ids[2];
static struct {
    uint64_t nr, enabled, running;
    struct { uint64_t count, id; } value[2];
} counts;

static void open_pmu(uint64_t miss_config, uint64_t loads_config) {
    uint64_t config[2] = {miss_config, loads_config};
    for (int i = 0; i < 2; ++i) {
        struct perf_event_attr a = {0};
        a.type = PERF_TYPE_RAW;
        a.size = sizeof(a);
        a.config = config[i];
        a.disabled = i == 0;
        a.pinned = i == 0;
        a.exclude_kernel = a.exclude_hv = a.exclude_guest = 1;
        a.read_format = PERF_FORMAT_GROUP | PERF_FORMAT_ID |
            PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
        fds[i] = (int)syscall(SYS_perf_event_open, &a, 0, -1,
                             i == 0 ? -1 : fds[0], PERF_FLAG_FD_CLOEXEC);
        if (fds[i] < 0) fail("perf_event_open");
        if (ioctl(fds[i], PERF_EVENT_IOC_ID, &ids[i])) fail("PMU id");
    }
}
static void start_pmu(void) {
    if (ioctl(fds[0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP)) fail("PMU reset");
    if (ioctl(fds[0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP)) fail("PMU enable");
}
static void stop_pmu(void) {
    if (ioctl(fds[0], PERF_EVENT_IOC_DISABLE, PERF_IOC_FLAG_GROUP)) fail("PMU disable");
    if (read(fds[0], &counts, sizeof(counts)) != sizeof(counts) ||
        counts.nr != 2 || !counts.running || counts.running != counts.enabled) {
        fprintf(stderr, "Invalid or multiplexed PMU group\n"); exit(1);
    }
}
static uint64_t count_for(int index) {
    for (int i = 0; i < 2; ++i)
        if (counts.value[i].id == ids[index]) return counts.value[i].count;
    fprintf(stderr, "Missing PMU event id\n"); exit(1);
}
#endif
