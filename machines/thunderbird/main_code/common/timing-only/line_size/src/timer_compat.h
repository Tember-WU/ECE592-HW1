// timer_compat.h
// Portable Phase-I timer backend. Include this instead of touching x86intrin.h or
// inline asm directly in the benchmarks, so the same .cpp compiles on both the x86-64
// lab machines (Sunbird, Charnwood, Ookay, Upgrade, Crux, Skylark, Artemisia) and the
// AArch64 machine (Thunderbird / Ampere Altra).
//
// x86-64: RDTSC/RDTSCP bracketed with LFENCE (TA slide 5).
// AArch64: CNTVCT_EL0 bracketed with DSB SY + ISB (TA slides 6/8). The generic timer is
//          coarse, so results here are still only meaningful when batched (--batch),
//          exactly like the existing benches already do.
//
// Units note (handout + TA slide 5): both backends return raw ticks, NOT cycles or ns.
// Label Phase-I output as "ticks/access" regardless of architecture. Only convert to
// ns/cycles in Phase II once you have a PMU cycle event (x86) or CNTFRQ_EL0 (Arm) to
// justify the conversion.

#pragma once
#include <cstdint>

#if defined(__x86_64__) || defined(_M_X64)

#include <x86intrin.h>

static inline uint64_t timer_start() {
    _mm_lfence();
    uint64_t t = __rdtsc();
    _mm_lfence();
    return t;
}

static inline uint64_t timer_stop() {
    unsigned aux;
    _mm_lfence();
    uint64_t t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

#elif defined(__aarch64__)

static inline uint64_t timer_start() {
    uint64_t t;
    __asm__ __volatile__(
        "dsb sy\n\t"
        "isb\n\t"
        "mrs %0, cntvct_el0\n\t"
        "isb\n\t"
        : "=r"(t) :: "memory");
    return t;
}

static inline uint64_t timer_stop() {
    // Same barrier skeleton at both ends: DSB SY drains outstanding memory accesses
    // (the AArch64 analogue of RDTSCP "waiting for prior loads"), ISB flushes the
    // pipeline so nothing hoists across the read.
    uint64_t t;
    __asm__ __volatile__(
        "dsb sy\n\t"
        "isb\n\t"
        "mrs %0, cntvct_el0\n\t"
        "isb\n\t"
        : "=r"(t) :: "memory");
    return t;
}

// Nominal counter frequency (typically tens of MHz on Arm -- NOT the core clock).
// Record this once per run/log so you can later report ns/access without pretending
// the generic timer tick is a CPU cycle.
static inline uint64_t timer_nominal_freq_hz() {
    uint64_t f;
    __asm__ __volatile__("mrs %0, cntfrq_el0" : "=r"(f));
    return f;
}

#else
#error "timer_compat.h: no timer backend for this architecture -- add one before building here."
#endif