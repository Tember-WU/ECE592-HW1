#include <cpuid.h>
#include <stdio.h>

int main(void) {
    unsigned a, b, c, d;
    if (__get_cpuid_max(0, 0) < 4) return 1;
    puts("subleaf,eax,ebx,ecx,edx,type,level,line_bytes,partitions,ways,sets,size_bytes,inclusive_lower_levels,complex_indexing");
    for (unsigned i = 0; i < 32; ++i) {
        __cpuid_count(4, i, a, b, c, d);
        if (!(a & 31)) return 0;
        unsigned line = (b & 4095) + 1, partitions = ((b >> 12) & 1023) + 1;
        unsigned ways = (b >> 22) + 1;
        unsigned long long sets = (unsigned long long)c + 1;
        printf("%u,0x%08x,0x%08x,0x%08x,0x%08x,%u,%u,%u,%u,%u,%llu,%llu,%u,%u\n",
               i, a, b, c, d, a & 31, (a >> 5) & 7, line, partitions,
               ways, sets, line * partitions * ways * sets, (d >> 1) & 1, (d >> 2) & 1);
    }
    return 1;
}
