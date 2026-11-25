/* Self-contained unit tests, runnable on the target without Python. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "abf.h"

static int failures = 0;

#define CHECK(condition)                                                \
    do {                                                                \
        if (!(condition)) {                                             \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition); \
            failures++;                                                 \
        }                                                               \
    } while (0)

static int near(float a, float b, float tolerance) {
    return fabsf(a - b) <= tolerance;
}

/* xorshift: deterministic on every platform */
static uint32_t rng_state = 2463534242u;
static float uniform(void) {
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return (float)(rng_state >> 8) / 8388608.0f - 1.0f; /* [-1, 1) */
}
static abf_cf32 random_cf32(float amplitude) {
    abf_cf32 z;
    z.re = amplitude * uniform();
    z.im = amplitude * uniform();
    return z;
}

static abf_cf32 response(const abf_cf32* w, const abf_cf32* a, size_t n) {
    abf_cf32 y;
    CHECK(abf_apply_weights(w, a, n, 1, &y) == ABF_OK);
    return y;
}

static float power(abf_cf32 z) {
    return z.re * z.re + z.im * z.im;
}

static void test_steering(void) {
    abf_cf32 a[4];
    CHECK(abf_steering_ula(0.52359877559f, 0.5f, 4, a) == ABF_OK); /* 30 degrees */
    const float expected[4][2] = {{1, 0}, {0, -1}, {-1, 0}, {0, 1}};
    for (int m = 0; m < 4; m++) {
        CHECK(near(a[m].re, expected[m][0], 1e-6f) && near(a[m].im, expected[m][1], 1e-6f));
    }
    CHECK(abf_steering_ula(0.0f, 0.5f, 0, a) == ABF_ERR_ARG);
    CHECK(abf_steering_ula(0.0f, 0.5f, ABF_MAX_ANTENNAS + 1, a) == ABF_ERR_ARG);
    CHECK(abf_steering_ula(NAN, 0.5f, 4, a) == ABF_ERR_ARG);
    CHECK(abf_steering_ula(0.0f, 0.0f, 4, a) == ABF_ERR_ARG);
    CHECK(abf_steering_ula(0.0f, 0.5f, 4, NULL) == ABF_ERR_ARG);
}

/* One strong interferer in noise: MVDR must keep the target and reject the interferer,
 * whatever the absolute level (the ADC scale is arbitrary). */
static void test_mvdr(float level) {
    enum { N = 8, K = 512 };
    static abf_cf32 x[N * K];
    abf_cf32 target[N], jammer[N], r[N * N], w[N];
    CHECK(abf_steering_ula(0.0f, 0.5f, N, target) == ABF_OK);
    CHECK(abf_steering_ula(-0.6f, 0.5f, N, jammer) == ABF_OK);
    for (size_t k = 0; k < K; k++) {
        const abf_cf32 s = random_cf32(30.0f * level);
        for (size_t m = 0; m < N; m++) {
            const abf_cf32 noise = random_cf32(level);
            x[k * N + m].re = jammer[m].re * s.re - jammer[m].im * s.im + noise.re;
            x[k * N + m].im = jammer[m].re * s.im + jammer[m].im * s.re + noise.im;
        }
    }
    CHECK(abf_covariance_update(r, x, N, K, 0.0f) == ABF_OK);
    CHECK(abf_mvdr_weights(r, target, N, 1e-3f, w) == ABF_OK);
    const abf_cf32 gain = response(w, target, N);
    CHECK(near(gain.re, 1.0f, 1e-4f) && near(gain.im, 0.0f, 1e-4f));
    CHECK(power(response(w, jammer, N)) < 1e-5f);
    CHECK(abf_white_noise_gain(w, target, N) > 0.5f * (float)N);
}

static void test_mvdr_errors(void) {
    abf_cf32 r[16], a[4], w[4];
    memset(r, 0, sizeof r);
    CHECK(abf_steering_ula(0.1f, 0.5f, 4, a) == ABF_OK);
    for (int i = 0; i < 4; i++) {
        w[i].re = 42.0f;
        w[i].im = 0.0f;
    }
    CHECK(abf_mvdr_weights(r, a, 4, 1e-2f, w) == ABF_ERR_NOT_POSDEF); /* silence */
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) { /* rank one */
            r[i * 4 + j].re = a[i].re * a[j].re + a[i].im * a[j].im;
            r[i * 4 + j].im = a[i].im * a[j].re - a[i].re * a[j].im;
        }
    }
    CHECK(abf_mvdr_weights(r, a, 4, 0.0f, w) == ABF_ERR_NOT_POSDEF);
    CHECK(w[0].re == 42.0f);                              /* outputs untouched on error */
    CHECK(abf_mvdr_weights(r, a, 4, 1e-2f, w) == ABF_OK); /* loading rescues it */
    r[0].re = NAN;
    CHECK(abf_mvdr_weights(r, a, 4, 1e-2f, w) == ABF_ERR_NUMERIC);
    CHECK(abf_mvdr_weights(NULL, a, 4, 1e-2f, w) == ABF_ERR_ARG);
    CHECK(abf_mvdr_weights(r, a, 4, -1.0f, w) == ABF_ERR_ARG);
}

static void test_covariance(void) {
    const abf_cf32 x[4] = {{1, 0}, {0, 1}, {2, 0}, {0, -2}}; /* 2 antennas, 2 snapshots */
    abf_cf32 r[4];
    memset(r, 0xFF, sizeof r); /* NaN: beta = 0 must ignore it */
    CHECK(abf_covariance_update(r, x, 2, 2, 0.0f) == ABF_OK);
    /* sum of [1, j][1, j]^H and [2, -2j][2, -2j]^H over 2 */
    CHECK(near(r[0].re, 2.5f, 1e-6f) && near(r[3].re, 2.5f, 1e-6f));
    CHECK(near(r[1].im, 1.5f, 1e-6f) && near(r[2].im, -1.5f, 1e-6f));
    const abf_cf32 before = r[0];
    CHECK(abf_covariance_update(r, x, 2, 2, 0.75f) == ABF_OK);
    CHECK(near(r[0].re, before.re, 1e-6f));
    CHECK(abf_covariance_update(r, x, 2, 0, 0.5f) == ABF_ERR_ARG);
    CHECK(abf_covariance_update(r, x, 2, 2, 1.0f) == ABF_ERR_ARG);
}

static void test_das(void) {
    abf_cf32 a[4], w[4];
    CHECK(abf_steering_ula(0.3f, 0.5f, 4, a) == ABF_OK);
    CHECK(abf_das_weights(a, 4, w) == ABF_OK);
    CHECK(near(response(w, a, 4).re, 1.0f, 1e-6f));
    CHECK(near(abf_white_noise_gain(w, a, 4), 4.0f, 1e-4f));
    memset(a, 0, sizeof a);
    CHECK(abf_das_weights(a, 4, w) == ABF_ERR_NUMERIC);
}

/* Adaptive filters must learn a known combiner from its output. */
static void test_adaptive(void) {
    enum { N = 4 };
    const abf_cf32 truth[N] = {{0.5f, 0.1f}, {-0.2f, 0.3f}, {0.0f, -0.4f}, {0.25f, 0.0f}};
    abf_cf32 lms[N], nlms[N], rls[N], p[N * N];
    memset(lms, 0, sizeof lms);
    memset(nlms, 0, sizeof nlms);
    memset(rls, 0, sizeof rls);
    memset(p, 0, sizeof p);
    for (int i = 0; i < N; i++) {
        p[i * N + i].re = 100.0f;
    }
    for (int k = 0; k < 4000; k++) {
        abf_cf32 x[N], d;
        for (int i = 0; i < N; i++) {
            x[i] = random_cf32(1.0f);
        }
        d = response(truth, x, N);
        CHECK(abf_lms_step(lms, x, d, N, 0.05f, NULL) == ABF_OK);
        CHECK(abf_nlms_step(nlms, x, d, N, 0.5f, 1e-6f, NULL) == ABF_OK);
        CHECK(abf_rls_step(rls, p, x, d, N, 0.95f, NULL) == ABF_OK);
    }
    for (int i = 0; i < N; i++) {
        CHECK(near(lms[i].re, truth[i].re, 1e-3f) && near(lms[i].im, truth[i].im, 1e-3f));
        CHECK(near(nlms[i].re, truth[i].re, 1e-3f) && near(nlms[i].im, truth[i].im, 1e-3f));
        CHECK(near(rls[i].re, truth[i].re, 1e-3f) && near(rls[i].im, truth[i].im, 1e-3f));
        CHECK(p[i * N + i].re > 0.0f && p[i * N + i].im == 0.0f);
    }
    abf_cf32 bad[N], d = {0.0f, 0.0f}, saved = lms[0];
    for (int i = 0; i < N; i++) {
        bad[i] = random_cf32(1.0f);
    }
    bad[1].re = NAN; /* one corrupt sample must not poison the state */
    CHECK(abf_lms_step(lms, bad, d, N, 0.05f, NULL) == ABF_ERR_NUMERIC);
    CHECK(abf_nlms_step(nlms, bad, d, N, 0.5f, 1e-6f, NULL) == ABF_ERR_NUMERIC);
    CHECK(abf_rls_step(rls, p, bad, d, N, 0.95f, NULL) == ABF_ERR_NUMERIC);
    CHECK(lms[0].re == saved.re && isfinite(p[0].re));
    CHECK(abf_rls_step(rls, p, bad, d, N, 1.5f, NULL) == ABF_ERR_ARG);
    CHECK(abf_lms_step(lms, bad, d, N, 0.0f, NULL) == ABF_ERR_ARG);
}

static void test_frames(void) {
    const uint8_t digits[] = "123456789";
    CHECK(abf_crc32(digits, 9) == 0xCBF43926u); /* standard check value */
    uint8_t buffer[256];
    abf_frame frame;
    abf_cf32 out[4];
    for (size_t i = 0; i < sizeof buffer; i++) {
        buffer[i] = (uint8_t)(uniform() * 127.0f);
    }
    for (size_t size = 0; size <= sizeof buffer; size++) {
        CHECK(abf_frame_parse(buffer, size, &frame) == ABF_ERR_FRAME);
    }
    CHECK(abf_frame_parse(NULL, 64, &frame) == ABF_ERR_ARG);
    memset(&frame, 0, sizeof frame);
    CHECK(abf_frame_samples(&frame, out, 4) == ABF_ERR_ARG);
}

int main(void) {
    test_steering();
    test_mvdr(1.0f);
    test_mvdr(1e-12f);
    test_mvdr(1e8f);
    test_mvdr_errors();
    test_covariance();
    test_das();
    test_adaptive();
    test_frames();
    printf(failures == 0 ? "all C tests passed\n" : "%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
