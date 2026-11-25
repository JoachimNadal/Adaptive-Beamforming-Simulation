/* Self-contained tests, runnable on the target without Python. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "abf_pipeline.h"

static int failures = 0;

#define CHECK(condition)                                                \
    do {                                                                \
        if (!(condition)) {                                             \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition); \
            failures++;                                                 \
        }                                                               \
    } while (0)

#ifdef ABFP_DOUBLE
#define TOLERANCE 1e-10
#else
#define TOLERANCE 2e-5
#endif

static uint32_t rng_state = 2463534242u;
static double uniform(void) {
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return ((double)(rng_state >> 8) + 0.5) / 16777216.0;
}
static double gaussian(void) {
    return sqrt(-2.0 * log(uniform())) * cos(6.283185307179586 * uniform());
}

enum { N = 8, K = 256 };
static abf_cf32 block[N * K], output[K];
static abfp_state state;

static abfp_config default_config(int mode) {
    abfp_config c;
    memset(&c, 0, sizeof c);
    c.num_antennas = N;
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
    return c;
}

/* Unit noise, target at broadside, interferers of given amplitude at two angles. */
static void fill(double target, double interferer) {
    for (int t = 0; t < K; t++) {
        const double s[6] = {gaussian(), gaussian(), gaussian(),
                             gaussian(), gaussian(), gaussian()};
        for (int m = 0; m < N; m++) {
            const double p1 = -3.141592653589793 * m * sin(-0.45);
            const double p2 = -3.141592653589793 * m * sin(0.7);
            double re = target * s[0] + gaussian();
            double im = target * s[1] + gaussian();
            re += interferer * (s[2] * cos(p1) - s[3] * sin(p1) + s[4] * cos(p2) - s[5] * sin(p2));
            im += interferer * (s[2] * sin(p1) + s[3] * cos(p1) + s[4] * sin(p2) + s[5] * cos(p2));
            block[t * N + m].re = (float)(re * 0.7071);
            block[t * N + m].im = (float)(im * 0.7071);
        }
    }
}

static float response(const abfp_state* s, float theta) {
    abf_cf32 a[N], y;
    CHECK(abf_steering_ula(theta, 0.5f, N, a) == ABF_OK);
    CHECK(abf_apply_weights(s->weights, a, N, 1, &y) == ABF_OK);
    return y.re * y.re + y.im * y.im;
}

static void test_eigh(size_t n) {
    static abfp_complex a[ABFP_N * ABFP_N], copy[ABFP_N * ABFP_N], v[ABFP_N * ABFP_N];
    abfp_real values[ABFP_N];
    for (size_t i = 0; i < n; i++) {
        for (size_t j = i; j < n; j++) {
            a[i * n + j].re = (abfp_real)gaussian();
            a[i * n + j].im = (i == j) ? (abfp_real)0 : (abfp_real)gaussian();
            a[j * n + i].re = a[i * n + j].re;
            a[j * n + i].im = -a[i * n + j].im;
        }
    }
    memcpy(copy, a, sizeof copy);
    CHECK(abfp_eigh(a, n, values, v) == ABF_OK);
    for (size_t e = 0; e < n; e++) {
        CHECK(e == 0 || values[e] >= values[e - 1]);
        for (size_t i = 0; i < n; i++) { /* A v = lambda v */
            double re = 0.0, im = 0.0;
            for (size_t j = 0; j < n; j++) {
                const abfp_complex x = copy[i * n + j], y = v[j * n + e];
                re += (double)(x.re * y.re - x.im * y.im);
                im += (double)(x.re * y.im + x.im * y.re);
            }
            CHECK(fabs(re - (double)(values[e] * v[i * n + e].re)) < TOLERANCE * 10);
            CHECK(fabs(im - (double)(values[e] * v[i * n + e].im)) < TOLERANCE * 10);
        }
        for (size_t f = 0; f <= e; f++) { /* orthonormal */
            double re = 0.0, im = 0.0;
            for (size_t j = 0; j < n; j++) {
                const abfp_complex x = v[j * n + e], y = v[j * n + f];
                re += (double)(x.re * y.re + x.im * y.im);
                im += (double)(x.re * y.im - x.im * y.re);
            }
            CHECK(fabs(re - (e == f ? 1.0 : 0.0)) < TOLERANCE && fabs(im) < TOLERANCE);
        }
    }
}

static void test_eigh_special(void) {
    abfp_complex a[9], v[9];
    abfp_real values[3];
    memset(a, 0, sizeof a); /* zero matrix */
    CHECK(abfp_eigh(a, 3, values, v) == ABF_OK && values[2] == (abfp_real)0);
    memset(a, 0, sizeof a); /* diagonal, unsorted */
    a[0].re = 3;
    a[4].re = 1;
    a[8].re = 2;
    CHECK(abfp_eigh(a, 3, values, v) == ABF_OK);
    CHECK(values[0] == (abfp_real)1 && values[1] == (abfp_real)2 && values[2] == (abfp_real)3);
    a[0].re = (abfp_real)NAN;
    CHECK(abfp_eigh(a, 3, values, v) == ABF_ERR_NUMERIC);
    CHECK(abfp_eigh(a, 0, values, v) == ABF_ERR_ARG);
}

static void test_roots(void) {
    /* (z - 0.5)(z + 2)(z - j) = z^3 + (1.5 - j) z^2 + (-1 - 1.5j) z + j */
    const double re[4] = {1.0, 1.5, -1.0, 0.0}, im[4] = {0.0, -1.0, -1.5, 1.0};
    double zr[3], zi[3];
    CHECK(abfp_polynomial_roots(re, im, 3, zr, zi) == 3);
    int found = 0;
    for (int k = 0; k < 3; k++) {
        found |= (fabs(zr[k] - 0.5) < 1e-9 && fabs(zi[k]) < 1e-9) ? 1 : 0;
        found |= (fabs(zr[k] + 2.0) < 1e-9 && fabs(zi[k]) < 1e-9) ? 2 : 0;
        found |= (fabs(zr[k]) < 1e-9 && fabs(zi[k] - 1.0) < 1e-9) ? 4 : 0;
    }
    CHECK(found == 7);
    CHECK(abfp_polynomial_roots(re, im, 0, zr, zi) == 0);
}

static void test_mdl(void) {
    const abfp_real two[6] = {(abfp_real)0.95, (abfp_real)0.98, 1, (abfp_real)1.04, 20, 300};
    const abfp_real none[4] = {(abfp_real)0.95, 1, (abfp_real)1.02, (abfp_real)1.05};
    CHECK(abfp_mdl(two, 6, 500) == 2);
    CHECK(abfp_mdl(none, 4, 500) == 0);
}

static void test_process(int mode) {
    abfp_config c = default_config(mode);
    abfp_result r;
    abf_cf32 ones[N];
    for (int i = 0; i < N; i++) {
        ones[i].re = 1.0f;
        ones[i].im = 0.0f;
    }
    CHECK(abfp_init(&state, &c) == ABF_OK);
    CHECK(abfp_set_calibration(&state, ones) == ABF_OK);
    for (uint32_t b = 0; b < 6; b++) {
        fill(1.0, 30.0);
        CHECK(abfp_process(&state, block, K, b, 0, output, &r) == ABF_OK);
    }
    CHECK(r.status == 0);
    CHECK(r.method == (mode == ABFP_PHASE1 ? ABFP_METHOD_LCMV : ABFP_METHOD_MVDR));
    CHECK(r.num_sources == 3);
    CHECK(fabsf(response(&state, 0.0f) - 1.0f) < 1e-3f);
    CHECK(response(&state, -0.45f) < 1e-4f && response(&state, 0.7f) < 1e-4f);
    if (mode == ABFP_PHASE1) {
        CHECK(r.num_doas == 3 && r.num_nulls == 2);
        CHECK(fabsf(r.doas_rad[0] + 0.45f) < 5e-3f && fabsf(r.doas_rad[2] - 0.7f) < 5e-3f);
    }
    const abf_cf32 before = state.weights[2];

    fill(1.0, 30.0); /* clipped block: output produced, weights held */
    CHECK(abfp_process(&state, block, K, 6, ABF_FLAG_ADC_OVERFLOW, output, &r) == ABF_OK);
    CHECK((r.status & ABFP_ADC_OVERFLOW) && (r.status & ABFP_WEIGHTS_HELD));
    CHECK(state.weights[2].re == before.re && state.weights[2].im == before.im);

    fill(1.0, 30.0); /* one corrupt sample: muted, and no effect afterwards */
    block[17].im = NAN;
    CHECK(abfp_process(&state, block, K, 7, 0, output, &r) == ABF_OK);
    CHECK((r.status & ABFP_INVALID_DATA) && output[0].re == 0.0f);
    block[17].im = INFINITY;
    CHECK(abfp_process(&state, block, K, 8, 0, output, &r) == ABF_OK);
    CHECK(r.status & ABFP_INVALID_DATA);
    fill(1.0, 30.0);
    CHECK(abfp_process(&state, block, K, 9, 0, output, &r) == ABF_OK);
    CHECK(r.status == 0 && response(&state, -0.45f) < 1e-4f);

    memset(block, 0, sizeof block); /* silence */
    abfp_state quiet;
    CHECK(abfp_init(&quiet, &c) == ABF_OK);
    CHECK(abfp_process(&quiet, block, K, 0, 0, output, &r) == ABF_OK);
    CHECK((r.status & ABFP_WEIGHTS_HELD) && (r.status & ABFP_UNCALIBRATED));

    fill(1.0, 30.0); /* sequence gap, then clock loss */
    CHECK(abfp_process(&state, block, K, 12, 0, output, &r) == ABF_OK);
    CHECK(r.status & ABFP_SEQUENCE_GAP);
    CHECK(abfp_process(&state, block, K, 13, ABF_FLAG_CLOCK_UNLOCKED, output, &r) == ABF_OK);
    CHECK((r.status & ABFP_CLOCK_UNLOCKED) && (r.status & ABFP_UNCALIBRATED));
}

/* 80 dB interferers: the square-root mode must still count and reject, in any precision. */
static void test_high_dynamic_range(void) {
    abfp_config c = default_config(ABFP_NOISE_LOADED_SQRT);
    abfp_result r;
    CHECK(abfp_init(&state, &c) == ABF_OK);
    for (uint32_t b = 0; b < 6; b++) {
        fill(1.0, 1e4);
        CHECK(abfp_process(&state, block, K, b, 0, output, &r) == ABF_OK);
    }
    CHECK(r.num_sources == 3 && r.method == ABFP_METHOD_MVDR);
    CHECK(fabsf(response(&state, 0.0f) - 1.0f) < 1e-3f);
    CHECK(response(&state, -0.45f) < 1e-9f && response(&state, 0.7f) < 1e-9f);
    CHECK(fabsf(r.noise_power - 1.0f) < 0.15f);
}

/* The covariance mode must report that it cannot resolve the noise, not fail silently. */
static void test_precision_is_reported(void) {
    abfp_config c = default_config(ABFP_NOISE_LOADED);
    abfp_result r;
    CHECK(abfp_init(&state, &c) == ABF_OK);
    fill(1.0, 30.0);
    CHECK(abfp_process(&state, block, K, 0, 0, output, &r) == ABF_OK);
    CHECK(!(r.status & ABFP_PRECISION_LIMITED));
    CHECK(abfp_init(&state, &c) == ABF_OK);
    fill(1.0, 1e4);
    CHECK(abfp_process(&state, block, K, 0, 0, output, &r) == ABF_OK);
    CHECK(((r.status & ABFP_PRECISION_LIMITED) != 0) == (sizeof(abfp_real) == sizeof(float)));
}

static void test_calibration(void) {
    abfp_config c = default_config(ABFP_PHASE1);
    abf_cf32 truth[N];
    CHECK(abfp_init(&state, &c) == ABF_OK);
    for (int m = 0; m < N; m++) {
        truth[m].re = (float)((1.0 + 0.1 * m) * cos(0.7 * m));
        truth[m].im = (float)((1.0 + 0.1 * m) * sin(0.7 * m));
    }
    for (int t = 0; t < K; t++) { /* one 30 dB source at 0.2 rad through the bad channels */
        const double sr = 30.0 * gaussian(), si = 30.0 * gaussian();
        for (int m = 0; m < N; m++) {
            const double p = -3.141592653589793 * m * sin(0.2);
            const double re = sr * cos(p) - si * sin(p), im = sr * sin(p) + si * cos(p);
            block[t * N + m].re =
                (float)(re * (double)truth[m].re - im * (double)truth[m].im + gaussian());
            block[t * N + m].im =
                (float)(re * (double)truth[m].im + im * (double)truth[m].re + gaussian());
        }
    }
    CHECK(abfp_calibrate(&state, block, K, 0.2f) == ABF_OK);
    for (int m = 0; m < N; m++) { /* inverse times truth is one */
        const abf_cf32 g = state.calibration_inverse[m];
        CHECK(fabsf(g.re * truth[m].re - g.im * truth[m].im - 1.0f) < 0.01f);
        CHECK(fabsf(g.re * truth[m].im + g.im * truth[m].re) < 0.01f);
    }
    memset(truth, 0, sizeof truth);
    CHECK(abfp_set_calibration(&state, truth) == ABF_ERR_NUMERIC);
}

static void test_arguments(void) {
    abfp_config c = default_config(ABFP_PHASE1);
    abfp_result r;
    CHECK(abfp_init(NULL, &c) == ABF_ERR_ARG);
    c.num_antennas = 17;
    CHECK(abfp_init(&state, &c) == ABF_ERR_ARG);
    c = default_config(7);
    CHECK(abfp_init(&state, &c) == ABF_ERR_ARG);
    c = default_config(ABFP_PHASE1);
    c.d_over_lambda = 0.6f;
    CHECK(abfp_init(&state, &c) == ABF_ERR_ARG);
    c = default_config(ABFP_PHASE1);
    c.relative_loading = NAN;
    CHECK(abfp_init(&state, &c) == ABF_ERR_ARG);
    c = default_config(ABFP_PHASE1);
    CHECK(abfp_init(&state, &c) == ABF_OK);
    CHECK(abfp_process(&state, block, 0, 0, 0, output, &r) == ABF_ERR_ARG);
    CHECK(abfp_process(&state, NULL, K, 0, 0, output, &r) == ABF_ERR_ARG);
    CHECK(abfp_calibrate(&state, block, K, 3.0f) == ABF_ERR_ARG);
}

int main(void) {
    for (size_t n = 1; n <= ABFP_N; n++) {
        test_eigh(n);
    }
    test_eigh_special();
    test_roots();
    test_mdl();
    test_process(ABFP_PHASE1);
    test_process(ABFP_NOISE_LOADED);
    test_process(ABFP_NOISE_LOADED_SQRT);
    test_high_dynamic_range();
    test_precision_is_reported();
    test_calibration();
    test_arguments();
    printf(failures == 0 ? "all pipeline tests passed (state %u bytes)\n" : "%u failure(s)\n",
           failures == 0 ? (unsigned)abfp_state_size() : (unsigned)failures);
    return failures == 0 ? 0 : 1;
}
