#ifndef LATENCY_TIMING_H
#define LATENCY_TIMING_H
#include <stdint.h>
/* Kept equivalent to the capacity timer: the load loop is inside one asm block. */
#if defined(__x86_64__)
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

#elif defined(__aarch64__)
__attribute__((noinline))
static uint64_t time_batch(void **cursor, uint64_t groups) {
    void *p = *cursor;
    uint64_t ticks, start;
    __asm__ volatile(
        "dsb ish\n\t"
        "isb\n\t"
        "mrs %[start], cntvct_el0\n\t"
        "isb\n\t"
        "cbz %[groups], 2f\n\t"
        "1:\n\t"
        ".rept 16\n\t"
        "ldr %[p], [%[p]]\n\t"
        ".endr\n\t"
        "subs %[groups], %[groups], #1\n\t"
        "b.ne 1b\n\t"
        "2:\n\t"
        "dsb ishld\n\t"
        "isb\n\t"
        "mrs %[ticks], cntvct_el0\n\t"
        "isb\n\t"
        "sub %[ticks], %[ticks], %[start]\n\t"
        : [ticks] "=&r"(ticks), [start] "=&r"(start),
          [p] "+&r"(p), [groups] "+&r"(groups)
        : : "cc", "memory");
    *cursor = p;
    return ticks;
}

#else
#error "Supported architectures: x86-64 and AArch64"
#endif
#endif
