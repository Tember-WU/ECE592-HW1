#include <cpuid.h>
#include <stdio.h>

/* Read-only CPUID leaf 4 system inventory; no timing or cache workload. */
int main(void) {
    unsigned a, b, c, d;
    for (unsigned subleaf = 0; ; ++subleaf) {
        __cpuid_count(4, subleaf, a, b, c, d);
        if (!(a & 31)) break;
        unsigned line = (b & 4095) + 1;
        unsigned partitions = ((b >> 12) & 1023) + 1;
        unsigned ways = ((b >> 22) & 1023) + 1;
        unsigned sets = c + 1;
        printf("subleaf=%u eax=%08x ebx=%08x ecx=%08x edx=%08x "
               "type=%u level=%u bytes=%llu line=%u partitions=%u ways=%u sets=%u "
               "inclusive_lower_levels=%u complex_indexing=%u max_addressable_sharers=%u\n",
               subleaf, a, b, c, d, a & 31, (a >> 5) & 7,
               (unsigned long long)line * partitions * ways * sets,
               line, partitions, ways, sets, (d >> 1) & 1, (d >> 2) & 1,
               ((a >> 14) & 4095) + 1);
    }
    return 0;
}
