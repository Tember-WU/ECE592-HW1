#define _GNU_SOURCE 1
#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <random>
#include <vector>
#include <linux/perf_event.h>
#include <sched.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static void die(const char* s) { perror(s); exit(1); }
static uint64_t number(const char* s) {
    char* e; errno=0; auto n=strtoull(s,&e,0);
    if(errno || *s=='-' || e==s || *e) { fprintf(stderr,"Invalid number: %s\n",s); exit(2); }
    return n;
}
static inline uint64_t tick() {
#if defined(__x86_64__)
    unsigned a,d;
    asm volatile("lfence\n\trdtsc\n\tlfence" : "=a"(a),"=d"(d) :: "memory");
    return (uint64_t(d)<<32)|a;
#elif defined(__aarch64__)
    uint64_t t;
    asm volatile("dsb ish\n\tisb\n\tmrs %0, cntvct_el0\n\tisb" : "=r"(t) :: "memory");
    return t;
#else
    timespec t; if(clock_gettime(CLOCK_MONOTONIC_RAW,&t)) die("clock_gettime");
    return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;
#endif
}
// A register-carried true dependency on both required ISAs, even at -O0.
// Each iteration performs exactly one 8-byte demand load; no array of independent loads.
__attribute__((noinline)) static uintptr_t chase(uintptr_t p, uint64_t n) {
#if defined(__x86_64__)
    asm volatile("1: mov (%0), %0\n\tdec %1\n\tjnz 1b" : "+r"(p), "+r"(n) :: "cc","memory");
#elif defined(__aarch64__)
    asm volatile("1: ldr %0, [%0]\n\tsubs %1, %1, #1\n\tb.ne 1b" : "+r"(p), "+r"(n) :: "cc","memory");
#else
    while(n--) p=*reinterpret_cast<volatile uintptr_t*>(p);
#endif
    return p;
}
int main(int argc,char** argv) {
    if(argc!=11) { fprintf(stderr,"Usage: bench CPU BYTES SPACING SAMPLES BATCH SEED TYPE CONFIG OUTPUT_PREFIX TIMING(0|1)\n"); return 2; }
    auto cpu=number(argv[1]), bytes=number(argv[2]), spacing=number(argv[3]);
    auto samples=number(argv[4]), batch=number(argv[5]), seed=number(argv[6]);
    auto type=number(argv[7]), config=number(argv[8]), timing=number(argv[10]);
    if(cpu>=CPU_SETSIZE || spacing<sizeof(uintptr_t) || spacing%alignof(uintptr_t) || bytes%spacing || bytes/spacing<2 || !samples || !batch || samples>100000000 || batch>1000000 || bytes>SIZE_MAX || samples>UINT64_MAX/batch || timing>1) {
        fprintf(stderr,"Invalid dimensions\n"); return 2;
    }
    cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(cpu,&mask);
    if(sched_setaffinity(0,sizeof(mask),&mask)) die("affinity");
    auto mem=(unsigned char*)mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(mem==MAP_FAILED) die("mmap");
    if(madvise(mem,bytes,MADV_NOHUGEPAGE)) die("MADV_NOHUGEPAGE");
    memset(mem,0,bytes); // first-touch after affinity; no global NUMA or THP changes
    uint64_t nodes=bytes/spacing;
    {
        std::vector<uint64_t> order(nodes);
        for(uint64_t i=0;i<nodes;i++) order[i]=i;
        // Explicit Fisher-Yates + rejection sampling, independent of std::shuffle implementation.
        std::mt19937_64 rng(seed);
        for(uint64_t i=nodes-1;i>0;i--) {
            uint64_t v, bound=i+1, threshold=uint64_t(-bound)%bound;
            do { v=rng(); } while(v<threshold);
            std::swap(order[i],order[v%bound]);
        }
        for(uint64_t i=0;i<nodes;i++) *reinterpret_cast<uintptr_t*>(mem+order[i]*spacing)=reinterpret_cast<uintptr_t>(mem+order[(i+1)%nodes]*spacing);
    }
    std::vector<uint64_t> times(timing?samples:0,0);
    uintptr_t p=reinterpret_cast<uintptr_t>(mem);
    p=chase(p,nodes*2); // two complete warm-up traversals, excluded from measurement
    int fd=-1;
    if(!timing) {
        perf_event_attr a={}; a.size=sizeof(a); a.type=type; a.config=config;
        a.disabled=1; a.pinned=1; a.exclude_kernel=1; a.exclude_hv=1; a.exclude_guest=1;
        a.read_format=PERF_FORMAT_TOTAL_TIME_ENABLED|PERF_FORMAT_TOTAL_TIME_RUNNING;
        fd=syscall(SYS_perf_event_open,&a,0,-1,-1,PERF_FLAG_FD_CLOEXEC);
        if(fd<0) die("perf_event_open");
    }
    rusage before,after; getrusage(RUSAGE_SELF,&before);
    uint64_t elapsed_start=tick();
    if(fd>=0 && ioctl(fd,PERF_EVENT_IOC_ENABLE,0)) die("enable");
    if(timing) {
        for(uint64_t i=0;i<samples;i++) { auto t=tick(); p=chase(p,batch); times[i]=tick()-t; }
    } else {
        // Counter-only pass avoids timing-buffer writes contaminating cache/DTLB events.
        // The same chain and exact same demand-load denominator are used in both passes.
        p=chase(p,samples*batch);
    }
    if(fd>=0 && ioctl(fd,PERF_EVENT_IOC_DISABLE,0)) die("disable");
    auto elapsed=tick()-elapsed_start;
    getrusage(RUSAGE_SELF,&after);
    uint64_t counts[3]={};
    if(fd>=0) {
        if(read(fd,counts,sizeof(counts))!=sizeof(counts)) die("counter read");
        if(!counts[1] || counts[1]!=counts[2]) { fprintf(stderr,"Unscheduled/multiplexed counter: enabled=%lu running=%lu\n",counts[1],counts[2]); return 3; }
        close(fd);
    }
    char path[4096];
    if(timing) {
        snprintf(path,sizeof(path),"%s.ticks.u64",argv[9]);
        FILE* f=fopen(path,"wb");
        if(!f || fwrite(times.data(),8,samples,f)!=samples || fclose(f)) die("timings output");
    }
#if defined(__x86_64__)
    const char* unit="TSC_ticks"; uint64_t freq=0;
#elif defined(__aarch64__)
    const char* unit="CNTVCT_ticks"; uint64_t freq; asm volatile("mrs %0, cntfrq_el0" : "=r"(freq));
#else
    const char* unit="ns"; uint64_t freq=1000000000;
#endif
    snprintf(path,sizeof(path),"%s.json",argv[9]); FILE* f=fopen(path,"w"); if(!f) die("json output");
    fprintf(f,"{\"bytes\":%lu,\"spacing\":%lu,\"samples\":%lu,\"batch\":%lu,\"seed\":%lu,\"chain_loads\":%lu,\"count\":%lu,\"enabled_ns\":%lu,\"running_ns\":%lu,\"cpu_end\":%d,\"timer_unit\":\"%s\",\"timer_hz\":%lu,\"elapsed_ticks\":%lu,\"minor_faults\":%ld,\"major_faults\":%ld,\"involuntary_switches\":%ld,\"checksum_offset\":%lu}\n",bytes,spacing,samples,batch,seed,samples*batch,counts[0],counts[1],counts[2],sched_getcpu(),unit,freq,elapsed,after.ru_minflt-before.ru_minflt,after.ru_majflt-before.ru_majflt,after.ru_nivcsw-before.ru_nivcsw,(uint64_t)(p-reinterpret_cast<uintptr_t>(mem)));
    if(fclose(f)) die("json close"); munmap(mem,bytes);
}
