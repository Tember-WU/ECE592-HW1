#ifndef HIT_RATE_KERNEL_H
#define HIT_RATE_KERNEL_H

/* One timestamp interval per actual target load. All loop state stays in
 * registers even at -O0. No preparation or auxiliary loads occur inside the
 * loop. The necessary raw-output store is after the timestamp, but its cache
 * effects are part of this instrumented workload in BOTH executables.
 * reuse>1 visits the same node repeatedly before following its next pointer.
 * Fences serialize every visit, including repeated visits to the same node. */
__attribute__((noinline))
static void *collect(void *p, uint64_t *out, uint64_t n,
                     uint64_t reuse, int empty) {
#if defined(__x86_64__)
    __asm__ volatile(
        "mov %[reuse], %%r10\n\t"
        ".global sample_loop_begin\n"
        "sample_loop_begin:\n\t"
        "lfence\n\t"
        "rdtsc\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax\n\t"
        "mov %%rax, %%r8\n\t"
        "lfence\n\t"
        "test %[empty], %[empty]\n\t"
        "jnz 1f\n\t"
        "mov (%[p]), %%r9\n\t"
        "1: rdtscp\n\t"
        "shl $32, %%rdx\n\t"
        "or %%rdx, %%rax\n\t"
        "sub %%r8, %%rax\n\t"
        "lfence\n\t"
        "mov %%rax, (%[out])\n\t"
        "add $8, %[out]\n\t"
        "test %[empty], %[empty]\n\t"
        "jnz 2f\n\t"
        "dec %%r10\n\t"
        "jnz 2f\n\t"
        "mov %%r9, %[p]\n\t"
        "mov %[reuse], %%r10\n\t"
        "2: dec %[n]\n\t"
        "jnz sample_loop_begin\n\t"
        ".global sample_loop_end\n"
        "sample_loop_end:\n\t"
        : [p] "+&r"(p), [out] "+&r"(out), [n] "+&r"(n)
        : [reuse] "r"(reuse), [empty] "r"((uint64_t)empty)
        : "rax", "rdx", "rcx", "r8", "r9", "r10", "cc", "memory");
#elif defined(__aarch64__)
    uint64_t start, delta, remaining;
    void *next;
    __asm__ volatile(
        "mov %[left], %[reuse]\n\t"
        ".global sample_loop_begin\n"
        "sample_loop_begin:\n\t"
        "dsb ish\n\t"
        "isb\n\t"
        "mrs %[start], cntvct_el0\n\t"
        "isb\n\t"
        "cbnz %[empty], 1f\n\t"
        "ldr %[next], [%[p]]\n\t"
        "1: dsb ishld\n\t"
        "isb\n\t"
        "mrs %[delta], cntvct_el0\n\t"
        "isb\n\t"
        "sub %[delta], %[delta], %[start]\n\t"
        "str %[delta], [%[out]], #8\n\t"
        "cbnz %[empty], 2f\n\t"
        "subs %[left], %[left], #1\n\t"
        "b.ne 2f\n\t"
        "mov %[p], %[next]\n\t"
        "mov %[left], %[reuse]\n\t"
        "2: subs %[n], %[n], #1\n\t"
        "b.ne sample_loop_begin\n\t"
        ".global sample_loop_end\n"
        "sample_loop_end:\n\t"
        : [p] "+&r"(p), [out] "+&r"(out), [n] "+&r"(n),
          [start] "=&r"(start), [delta] "=&r"(delta),
          [left] "=&r"(remaining), [next] "=&r"(next)
        : [reuse] "r"(reuse), [empty] "r"((uint64_t)empty)
        : "cc", "memory");
#else
#error "Supported instruction paths: x86-64 and AArch64"
#endif
    return p;
}

static void *warm(void *p, uint64_t n) {
    for (uint64_t i = 0; i < n; ++i) {
#if defined(__x86_64__)
        __asm__ volatile("mov (%0), %0" : "+r"(p) :: "memory");
#elif defined(__aarch64__)
        __asm__ volatile("ldr %0, [%0]" : "+r"(p) :: "memory");
#endif
    }
    return p;
}
#endif
