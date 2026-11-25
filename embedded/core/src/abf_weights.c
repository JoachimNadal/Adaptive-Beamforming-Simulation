#include <float.h>
#include <math.h>
#include <string.h>

#include "abf_math.h"

abf_status abf_steering_ula(float theta, float d_over_lambda, size_t n, abf_cf32* a) {
    if (a == NULL || !abf_valid_n(n) || !isfinite(theta) || !(d_over_lambda > 0.0f)) {
        return ABF_ERR_ARG;
    }
    const float step = -6.28318530717958647692f * d_over_lambda * sinf(theta);
    for (size_t m = 0; m < n; m++) {
        const float phase = step * (float)m;
        a[m] = abf_make(cosf(phase), sinf(phase));
    }
    return ABF_OK;
}

abf_status abf_apply_weights(const abf_cf32* w, const abf_cf32* x, size_t n, size_t k,
                             abf_cf32* y) {
    if (w == NULL || x == NULL || y == NULL || !abf_valid_n(n)) {
        return ABF_ERR_ARG;
    }
    for (size_t i = 0; i < k; i++) {
        y[i] = abf_dot(w, x + i * n, n);
    }
    return ABF_OK;
}

abf_status abf_covariance_update(abf_cf32* r, const abf_cf32* x, size_t n, size_t k, float beta) {
    if (r == NULL || x == NULL || !abf_valid_n(n) || k == 0 || !(beta >= 0.0f && beta < 1.0f)) {
        return ABF_ERR_ARG;
    }
    abf_cf32 acc[ABF_MAX_ANTENNAS * ABF_MAX_ANTENNAS];
    memset(acc, 0, sizeof acc);
    for (size_t s = 0; s < k; s++) {
        const abf_cf32* v = x + s * n;
        for (size_t i = 0; i < n; i++) {
            for (size_t j = i; j < n; j++) {
                abf_cmac_conj(&acc[i * n + j], v[j], v[i]); /* v[i] conj(v[j]) */
            }
        }
    }
    /* A diagonal term is the energy of one antenna: it is finite if and only if all of its
     * samples are, and then so are the other terms. Checked before r is modified because a
     * recursive average never forgets a NaN. */
    for (size_t i = 0; i < n; i++) {
        if (!isfinite(acc[i * n + i].re)) {
            return ABF_ERR_NUMERIC;
        }
    }
    const float gain = (1.0f - beta) / (float)k;
    for (size_t i = 0; i < n; i++) {
        for (size_t j = i; j < n; j++) {
            abf_cf32 value = abf_make(gain * acc[i * n + j].re, gain * acc[i * n + j].im);
            if (beta > 0.0f) {
                value.re += beta * r[i * n + j].re;
                value.im += beta * r[i * n + j].im;
            }
            if (i == j) {
                value.im = 0.0f;
            }
            r[i * n + j] = value;
            r[j * n + i] = abf_make(value.re, -value.im);
        }
    }
    return ABF_OK;
}

abf_status abf_das_weights(const abf_cf32* a, size_t n, abf_cf32* w) {
    if (a == NULL || w == NULL || !abf_valid_n(n)) {
        return ABF_ERR_ARG;
    }
    const float energy = abf_energy(a, n);
    if (!(energy > FLT_MIN) || !isfinite(energy)) {
        return ABF_ERR_NUMERIC;
    }
    for (size_t i = 0; i < n; i++) {
        w[i] = abf_make(a[i].re / energy, a[i].im / energy);
    }
    return ABF_OK;
}

/* In-place Cholesky R = L L^H (lower triangle). A pivot that falls below n * epsilon times
 * its original value has no significant digit left in single precision. */
static abf_status cholesky(abf_cf32* l, size_t n) {
    for (size_t j = 0; j < n; j++) {
        const float original = l[j * n + j].re;
        float pivot = original;
        for (size_t p = 0; p < j; p++) {
            pivot -= abf_norm2(l[j * n + p]);
        }
        if (!(pivot > (float)n * FLT_EPSILON * original) || !isfinite(pivot)) {
            return ABF_ERR_NOT_POSDEF;
        }
        const float diagonal = sqrtf(pivot);
        l[j * n + j] = abf_make(diagonal, 0.0f);
        for (size_t i = j + 1; i < n; i++) {
            abf_cf32 sum = l[i * n + j];
            for (size_t p = 0; p < j; p++) {
                const abf_cf32 a = l[i * n + p];
                const abf_cf32 b = l[j * n + p]; /* sum -= a conj(b) */
                sum.re -= a.re * b.re + a.im * b.im;
                sum.im -= a.im * b.re - a.re * b.im;
            }
            l[i * n + j] = abf_make(sum.re / diagonal, sum.im / diagonal);
        }
    }
    return ABF_OK;
}

abf_status abf_mvdr_weights(const abf_cf32* r, const abf_cf32* a, size_t n, float relative_loading,
                            abf_cf32* w) {
    if (r == NULL || a == NULL || w == NULL || !abf_valid_n(n) || !(relative_loading >= 0.0f)) {
        return ABF_ERR_ARG;
    }
    float trace = 0.0f;
    for (size_t i = 0; i < n; i++) {
        trace += r[i * n + i].re;
    }
    if (!isfinite(trace)) {
        return ABF_ERR_NUMERIC;
    }
    if (!(trace > FLT_MIN)) {
        return ABF_ERR_NOT_POSDEF;
    }
    /* Normalising by the mean eigenvalue keeps every value near 1 whatever the ADC scale,
     * which avoids single-precision under/overflow. The weights do not depend on it. */
    const float scale = (float)n / trace;
    abf_cf32 l[ABF_MAX_ANTENNAS * ABF_MAX_ANTENNAS];
    for (size_t i = 0; i < n * n; i++) {
        l[i] = abf_make(r[i].re * scale, r[i].im * scale);
    }
    for (size_t i = 0; i < n; i++) {
        l[i * n + i] = abf_make(l[i * n + i].re + relative_loading, 0.0f);
    }
    const abf_status status = cholesky(l, n);
    if (status != ABF_OK) {
        return status;
    }
    /* forward substitution L z = a, then a^H R^-1 a = ||z||^2 */
    abf_cf32 z[ABF_MAX_ANTENNAS];
    for (size_t i = 0; i < n; i++) {
        abf_cf32 sum = a[i];
        for (size_t p = 0; p < i; p++) {
            const abf_cf32 t = abf_mul(l[i * n + p], z[p]);
            sum.re -= t.re;
            sum.im -= t.im;
        }
        z[i] = abf_make(sum.re / l[i * n + i].re, sum.im / l[i * n + i].re);
    }
    const float denominator = abf_energy(z, n);
    if (!(denominator > FLT_MIN) || !isfinite(denominator)) {
        return ABF_ERR_NUMERIC;
    }
    /* back substitution L^H u = z */
    for (size_t i = n; i-- > 0;) {
        abf_cf32 sum = z[i];
        for (size_t p = i + 1; p < n; p++) {
            abf_cf32 t = {0.0f, 0.0f};
            abf_cmac_conj(&t, l[p * n + i], z[p]);
            sum.re -= t.re;
            sum.im -= t.im;
        }
        z[i] = abf_make(sum.re / l[i * n + i].re, sum.im / l[i * n + i].re);
    }
    for (size_t i = 0; i < n; i++) {
        w[i] = abf_make(z[i].re / denominator, z[i].im / denominator);
    }
    return ABF_OK;
}

float abf_white_noise_gain(const abf_cf32* w, const abf_cf32* a, size_t n) {
    if (w == NULL || a == NULL || !abf_valid_n(n)) {
        return 0.0f;
    }
    const float energy = abf_energy(w, n);
    return energy > 0.0f ? abf_norm2(abf_dot(w, a, n)) / energy : 0.0f;
}

/* Shared LMS body: w += step * x * conj(e). */
static abf_status gradient_step(abf_cf32* w, const abf_cf32* x, abf_cf32 d, size_t n, float step,
                                abf_cf32* error) {
    const abf_cf32 y = abf_dot(w, x, n);
    const abf_cf32 e = abf_make(d.re - y.re, d.im - y.im);
    if (!isfinite(e.re) || !isfinite(e.im) || !isfinite(step)) {
        return ABF_ERR_NUMERIC; /* w untouched: one bad sample must not poison it */
    }
    for (size_t i = 0; i < n; i++) {
        w[i].re += step * (x[i].re * e.re + x[i].im * e.im);
        w[i].im += step * (x[i].im * e.re - x[i].re * e.im);
    }
    if (error != NULL) {
        *error = e;
    }
    return ABF_OK;
}

abf_status abf_lms_step(abf_cf32* w, const abf_cf32* x, abf_cf32 d, size_t n, float mu,
                        abf_cf32* error) {
    if (w == NULL || x == NULL || !abf_valid_n(n) || !(mu > 0.0f)) {
        return ABF_ERR_ARG;
    }
    return gradient_step(w, x, d, n, mu, error);
}

abf_status abf_nlms_step(abf_cf32* w, const abf_cf32* x, abf_cf32 d, size_t n, float mu, float eps,
                         abf_cf32* error) {
    if (w == NULL || x == NULL || !abf_valid_n(n) || !(mu > 0.0f) || !(eps > 0.0f)) {
        return ABF_ERR_ARG;
    }
    return gradient_step(w, x, d, n, mu / (eps + abf_energy(x, n)), error);
}

abf_status abf_rls_step(abf_cf32* w, abf_cf32* p, const abf_cf32* x, abf_cf32 d, size_t n,
                        float forgetting, abf_cf32* error) {
    if (w == NULL || p == NULL || x == NULL || !abf_valid_n(n) ||
        !(forgetting > 0.0f && forgetting <= 1.0f)) {
        return ABF_ERR_ARG;
    }
    abf_cf32 u[ABF_MAX_ANTENNAS];
    for (size_t i = 0; i < n; i++) {
        abf_cf32 sum = {0.0f, 0.0f};
        for (size_t j = 0; j < n; j++) {
            const abf_cf32 t = abf_mul(p[i * n + j], x[j]);
            sum.re += t.re;
            sum.im += t.im;
        }
        u[i] = sum;
    }
    const float denominator = forgetting + abf_dot(x, u, n).re;
    const abf_cf32 y = abf_dot(w, x, n);
    const abf_cf32 e = abf_make(d.re - y.re, d.im - y.im);
    if (!(denominator > 0.0f) || !isfinite(denominator) || !isfinite(e.re) || !isfinite(e.im)) {
        return ABF_ERR_NUMERIC;
    }
    for (size_t i = 0; i < n; i++) {
        const abf_cf32 g = abf_make(u[i].re / denominator, u[i].im / denominator);
        w[i].re += g.re * e.re + g.im * e.im; /* g conj(e) */
        w[i].im += g.im * e.re - g.re * e.im;
        for (size_t j = i; j < n; j++) {
            abf_cf32 v = p[i * n + j]; /* (P - g u^H) / forgetting */
            v.re = (v.re - (g.re * u[j].re + g.im * u[j].im)) / forgetting;
            v.im = (v.im - (g.im * u[j].re - g.re * u[j].im)) / forgetting;
            if (i == j) {
                v.im = 0.0f;
            }
            p[i * n + j] = v;
            p[j * n + i] = abf_make(v.re, -v.im);
        }
    }
    if (error != NULL) {
        *error = e;
    }
    return ABF_OK;
}
