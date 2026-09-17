#define _GNU_SOURCE
#include <errno.h>
#include <linux/perf_event.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Read-only access diagnostic: one system-wide CMN HNF cache-miss event.
 * It is never enabled. Explicitly avoid per-user filtering unsupported by CMN.
 * Dynamic PMU type and raw encoding come from the archived local sysfs inventory.
 */
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    struct perf_event_attr attr = {0};
    attr.type = (unsigned)strtoul(argv[1], NULL, 0);
    attr.size = sizeof(attr);
    attr.config = strtoull(argv[2], NULL, 0);
    attr.disabled = 1;
    int fd = (int)syscall(SYS_perf_event_open, &attr, -1, 0, -1, PERF_FLAG_FD_CLOEXEC);
    int error = fd < 0 ? errno : 0;
    printf("{\"opened\":%s,\"errno\":%d,\"message\":\"%s\"}\n",
           fd >= 0 ? "true" : "false", error, strerror(error));
    if (fd >= 0) close(fd);
    return 0;
}
