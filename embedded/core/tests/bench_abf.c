/* Throughput of the kernels on the machine it runs on (one core). */
#include <stdio.h>
#include <time.h>

#include "abf.h"

enum { BLOCK = 1024, MAX_N = ABF_MAX_ANTENNAS };
static abf_cf32 x[BLOCK * MAX_N], y[BLOCK], r[MAX_N * MAX_N], p[MAX_N * MAX_N];
static abf_cf32 a[MAX_N], w[MAX_N];

/* CPU time: coarse but standard C, hence the long runs. */
static double seconds(void) {
    return (double)clock() / CLOCKS_PER_SEC;
}

int main(void) {
    for (size_t i = 0; i < BLOCK * MAX_N; i++) {
        x[i].re = (float)((i * 7919u) % 1000u) / 500.0f - 1.0f;
        x[i].im = (float)((i * 6101u) % 1000u) / 500.0f - 1.0f;
    }
    printf("antennas  apply MS/s  covariance MS/s  MVDR us  RLS us/sample\n");
    for (size_t n = 4; n <= MAX_N; n *= 2) {
        double rate[4];
        for (int kernel = 0; kernel < 4; kernel++) {
            long runs = 0;
            (void)abf_steering_ula(0.2f, 0.5f, n, a);
            (void)abf_das_weights(a, n, w);
            (void)abf_covariance_update(r, x, n, BLOCK, 0.0f);
            for (size_t i = 0; i < n * n; i++) {
                p[i].re = (i % (n + 1) == 0) ? 1.0f : 0.0f;
                p[i].im = 0.0f;
            }
            const double start = seconds();
            double elapsed = 0.0;
            do {
                for (int repeat = 0; repeat < 20; repeat++) {
                    const abf_cf32 d = {1.0f, 0.0f};
                    if (kernel == 0) {
                        (void)abf_apply_weights(w, x, n, BLOCK, y);
                    } else if (kernel == 1) {
                        (void)abf_covariance_update(r, x, n, BLOCK, 0.5f);
                    } else if (kernel == 2) {
                        (void)abf_mvdr_weights(r, a, n, 1e-2f, w);
                    } else {
                        (void)abf_rls_step(w, p, x + (size_t)(runs % BLOCK) * n, d, n, 0.99f, NULL);
                    }
                    runs++;
                }
                elapsed = seconds() - start;
            } while (elapsed < 0.5);
            rate[kernel] = elapsed / (double)runs;
        }
        printf("%8u  %10.1f  %15.1f  %7.3f  %13.3f\n", (unsigned)n, (double)BLOCK / rate[0] / 1e6,
               (double)BLOCK / rate[1] / 1e6, rate[2] * 1e6, rate[3] * 1e6);
    }
    return 0;
}
