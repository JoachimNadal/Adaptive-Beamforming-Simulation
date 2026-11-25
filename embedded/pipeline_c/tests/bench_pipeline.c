/* Time per block of the whole pipeline on the machine it runs on, one core. */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "abf_pipeline.h"

enum { MAX_K = 1024 };
static abf_cf32 x[ABFP_N * MAX_K], copy[ABFP_N * MAX_K], y[MAX_K];
static abfp_state state;

static uint32_t rng_state = 1u;
static float noise(void) {
    rng_state = rng_state * 1664525u + 1013904223u;
    return (float)((double)(rng_state >> 8) / 8388608.0 - 1.0);
}

static double seconds(void) {
    return (double)clock() / CLOCKS_PER_SEC;
}

int main(void) {
    printf("state %u bytes, real is %u bytes\n", (unsigned)abfp_state_size(),
           (unsigned)sizeof(abfp_real));
    printf("mode  antennas  block  us/block  MS/s\n");
    for (int mode = ABFP_PHASE1; mode <= ABFP_NOISE_LOADED_SQRT; mode++) {
        for (int n = 4; n <= ABFP_N; n *= 2) {
            for (size_t k = 64; k <= MAX_K; k *= 4) {
                abfp_config c;
                memset(&c, 0, sizeof c);
                c.num_antennas = n;
                c.mode = mode;
                c.d_over_lambda = 0.5f;
                c.covariance_beta = 0.5f;
                c.relative_loading = 1e-2f;
                c.noise_factor = 10.0f;
                c.max_interferers = 2;
                c.guard_rad = 0.1f;
                c.min_interferer_inr = 2.0f;
                c.derivative_constraint = 1;
                c.min_wng_ratio = 0.1f;
                abf_cf32 a[ABFP_N], ones[ABFP_N];
                (void)abf_steering_ula(-0.6f, 0.5f, (size_t)n, a);
                for (int i = 0; i < n; i++) {
                    ones[i].re = 1.0f;
                    ones[i].im = 0.0f;
                }
                for (size_t t = 0; t < k; t++) {
                    const float sr = 30.0f * noise(), si = 30.0f * noise();
                    for (int m = 0; m < n; m++) {
                        x[t * (size_t)n + (size_t)m].re = sr * a[m].re - si * a[m].im + noise();
                        x[t * (size_t)n + (size_t)m].im = sr * a[m].im + si * a[m].re + noise();
                    }
                }
                (void)abfp_init(&state, &c);
                (void)abfp_set_calibration(&state, ones);
                abfp_result r;
                uint32_t sequence = 0;
                long runs = 0;
                const double start = seconds();
                double elapsed = 0.0;
                do {
                    for (int i = 0; i < 10; i++) {
                        /* processing works in place: restore the input, as a DMA would */
                        memcpy(copy, x, k * (size_t)n * sizeof *x);
                        (void)abfp_process(&state, copy, k, sequence++, 0, y, &r);
                        runs++;
                    }
                    elapsed = seconds() - start;
                } while (elapsed < 0.3);
                const double per_block = elapsed / (double)runs;
                printf("%4d  %8d  %5u  %8.2f  %5.1f%s\n", mode, n, (unsigned)k, per_block * 1e6,
                       (double)k / per_block / 1e6, r.status ? "  (status set)" : "");
            }
        }
    }
    return 0;
}
