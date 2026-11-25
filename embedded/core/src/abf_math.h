/* Internal complex helpers. */
#ifndef ABF_MATH_H
#define ABF_MATH_H

#include "abf.h"

static inline abf_cf32 abf_make(float re, float im) {
    abf_cf32 z;
    z.re = re;
    z.im = im;
    return z;
}

/* accumulator += conj(a) * b */
static inline void abf_cmac_conj(abf_cf32* acc, abf_cf32 a, abf_cf32 b) {
    acc->re += a.re * b.re + a.im * b.im;
    acc->im += a.re * b.im - a.im * b.re;
}

static inline abf_cf32 abf_mul(abf_cf32 a, abf_cf32 b) {
    return abf_make(a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re);
}

static inline float abf_norm2(abf_cf32 a) {
    return a.re * a.re + a.im * a.im;
}

static inline int abf_valid_n(size_t n) {
    return n >= 1 && n <= ABF_MAX_ANTENNAS;
}

/* sum conj(a[i]) b[i] */
static inline abf_cf32 abf_dot(const abf_cf32* a, const abf_cf32* b, size_t n) {
    abf_cf32 acc = {0.0f, 0.0f};
    for (size_t i = 0; i < n; i++) {
        abf_cmac_conj(&acc, a[i], b[i]);
    }
    return acc;
}

static inline float abf_energy(const abf_cf32* a, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        acc += abf_norm2(a[i]);
    }
    return acc;
}

#endif
