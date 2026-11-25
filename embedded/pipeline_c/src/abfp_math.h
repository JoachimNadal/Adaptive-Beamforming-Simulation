/* Internal helpers for abfp_complex. */
#ifndef ABFP_MATH_H
#define ABFP_MATH_H

#include <float.h>
#include <math.h>

#include "abf_pipeline.h"

#ifdef ABFP_DOUBLE
#define ABFP_EPS   DBL_EPSILON
#define ABFP_TINY  DBL_MIN
#define abfp_sqrt  sqrt
#define abfp_fabs  fabs
#define abfp_log   log
#define abfp_hypot hypot
#else
#define ABFP_EPS   FLT_EPSILON
#define ABFP_TINY  FLT_MIN
#define abfp_sqrt  sqrtf
#define abfp_fabs  fabsf
#define abfp_log   logf
#define abfp_hypot hypotf
#endif

#define ABFP_R(x) ((abfp_real)(x))

static inline int abfp_finite(abfp_real x) {
    return x - x == ABFP_R(0);
}

static inline abfp_complex abfp_c(abfp_real re, abfp_real im) {
    abfp_complex z;
    z.re = re;
    z.im = im;
    return z;
}

static inline abfp_complex abfp_mul(abfp_complex a, abfp_complex b) {
    return abfp_c(a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re);
}

/* conj(a) b */
static inline abfp_complex abfp_cmul(abfp_complex a, abfp_complex b) {
    return abfp_c(a.re * b.re + a.im * b.im, a.re * b.im - a.im * b.re);
}

static inline abfp_complex abfp_add(abfp_complex a, abfp_complex b) {
    return abfp_c(a.re + b.re, a.im + b.im);
}

static inline abfp_complex abfp_sub(abfp_complex a, abfp_complex b) {
    return abfp_c(a.re - b.re, a.im - b.im);
}

static inline abfp_complex abfp_scale(abfp_complex a, abfp_real s) {
    return abfp_c(a.re * s, a.im * s);
}

static inline abfp_real abfp_norm2(abfp_complex a) {
    return a.re * a.re + a.im * a.im;
}

#endif
