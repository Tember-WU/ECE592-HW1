#include <cpuid.h>
#include <stdio.h>

int main(void) {
    unsigned a, b, c, d;
    puts("[");
    for (unsigned i = 0; __get_cpuid_count(4, i, &a, &b, &c, &d) && (a & 31); ++i) {
        printf("%s{\"leaf\":4,\"subleaf\":%u,\"eax\":%u,\"ebx\":%u,"
               "\"ecx\":%u,\"edx\":%u,\"type\":%u,\"level\":%u,"
               "\"inclusive_of_lower_levels\":%u,\"line_bytes\":%u,"
               "\"ways\":%u,\"sets\":%u}",
               i ? ",\n" : "", i, a, b, c, d, a & 31, (a >> 5) & 7,
               (d >> 1) & 1, (b & 4095) + 1, ((b >> 22) & 1023) + 1, c + 1);
    }
    puts("\n]");
    return 0;
}
