/* Square-root processing: the triangular factor T of the covariance (T^H T = R) is updated
 * directly from the data. Squaring the data into a covariance squares its dynamic range; not
 * doing it halves the number of digits needed, which makes single precision sufficient for
 * interferers that are 80 dB above the noise (research/c_port/REPORT.md). */
#include <string.h>

#include "abfp_internal.h"

/* Rotates the row vector v (length n) into the upper triangular T, whose diagonal stays real
 * and non-negative. v is destroyed. */
static void absorb_row(abfp_complex* T, abfp_complex* v, size_t n, size_t first) {
    for (size_t i = first; i < n; i++) {
        const abfp_real t = T[i * n + i].re;
        const abfp_real r = abfp_hypot(t, abfp_hypot(v[i].re, v[i].im));
        if (!(r > ABFP_TINY)) {
            continue;
        }
        const abfp_real c = t / r;
        const abfp_complex s = abfp_scale(v[i], ABFP_R(1) / r);
        T[i * n + i] = abfp_c(r, 0);
        for (size_t j = i + 1; j < n; j++) {
            const abfp_complex tij = T[i * n + j];
            const abfp_complex vj = v[j];
            /* [T; v] <- [c conj(s); -s c] [T; v] */
            T[i * n + j] = abfp_add(abfp_scale(tij, c), abfp_cmul(s, vj));
            v[j] = abfp_sub(abfp_scale(vj, c), abfp_mul(s, tij));
        }
    }
}

int abfp_sqrt_update(abfp_complex* T, size_t n, const abf_cf32* x, size_t k, abfp_real beta) {
    const abfp_real keep = abfp_sqrt(beta);
    for (size_t i = 0; i < n * n; i++) {
        T[i] = abfp_scale(T[i], keep);
    }
    const abfp_real scale = abfp_sqrt((ABFP_R(1) - beta) / (abfp_real)k);
    for (size_t t = 0; t < k; t++) {
        abfp_complex v[ABFP_N];
        for (size_t i = 0; i < n; i++) { /* row x^H */
            v[i] = abfp_c(scale * (abfp_real)x[t * n + i].re, -scale * (abfp_real)x[t * n + i].im);
        }
        absorb_row(T, v, n, 0);
    }
    abfp_real sum = 0;
    for (size_t i = 0; i < n; i++) {
        sum += T[i * n + i].re;
    }
    return abfp_finite(sum);
}

/* Squared singular values of T (eigenvalues of R), ascending, by one-sided Jacobi: columns of a
 * copy of T are made orthogonal two by two. Small values keep their relative accuracy. */
abf_status abfp_sqrt_eigenvalues(const abfp_complex* T, size_t n, abfp_complex* work,
                                 abfp_real* values) {
    enum { MAX_SWEEPS = 30 };
    memcpy(work, T, n * n * sizeof *work);
    int converged = 0;
    for (int sweep = 0; sweep < MAX_SWEEPS && !converged; sweep++) {
        converged = 1;
        for (size_t p = 0; p + 1 < n; p++) {
            for (size_t q = p + 1; q < n; q++) {
                abfp_real a = 0;
                abfp_real b = 0;
                abfp_complex g = abfp_c(0, 0);
                for (size_t i = 0; i < n; i++) {
                    a += abfp_norm2(work[i * n + p]);
                    b += abfp_norm2(work[i * n + q]);
                    g = abfp_add(g, abfp_cmul(work[i * n + p], work[i * n + q]));
                }
                const abfp_real magnitude = abfp_hypot(g.re, g.im);
                if (!(magnitude > ABFP_R(4) * ABFP_EPS * abfp_sqrt(a) * abfp_sqrt(b)) ||
                    !(magnitude > ABFP_TINY)) {
                    continue;
                }
                converged = 0;
                const abfp_complex unit = abfp_c(g.re / magnitude, -g.im / magnitude);
                const abfp_real theta = (b - a) / (ABFP_R(2) * magnitude);
                abfp_real t = ABFP_R(1) / (abfp_fabs(theta) + abfp_hypot(theta, ABFP_R(1)));
                if (theta < ABFP_R(0)) {
                    t = -t;
                }
                const abfp_real c = ABFP_R(1) / abfp_hypot(t, ABFP_R(1));
                const abfp_real s = t * c;
                for (size_t i = 0; i < n; i++) {
                    const abfp_complex wp = work[i * n + p];
                    const abfp_complex wq = abfp_mul(unit, work[i * n + q]);
                    work[i * n + p] = abfp_c(c * wp.re - s * wq.re, c * wp.im - s * wq.im);
                    work[i * n + q] = abfp_c(s * wp.re + c * wq.re, s * wp.im + c * wq.im);
                }
            }
        }
    }
    for (size_t p = 0; p < n; p++) {
        abfp_real sum = 0;
        for (size_t i = 0; i < n; i++) {
            sum += abfp_norm2(work[i * n + p]);
        }
        values[p] = sum;
        if (!abfp_finite(sum)) {
            return ABF_ERR_NUMERIC;
        }
    }
    for (size_t i = 0; i + 1 < n; i++) { /* ascending */
        for (size_t j = i + 1; j < n; j++) {
            if (values[j] < values[i]) {
                const abfp_real swap = values[i];
                values[i] = values[j];
                values[j] = swap;
            }
        }
    }
    /* Not fully converged only means the last digits differ: accepted. */
    return ABF_OK;
}

/* w proportional to (T^H T + loading I)^-1 a, scaled to w^H a = 1. work receives the loaded
 * factor. Returns 0 if the system is singular. */
int abfp_sqrt_mvdr(const abfp_complex* T, size_t n, abfp_real loading, const abfp_complex* a,
                   abfp_complex* work, abfp_complex* w) {
    memcpy(work, T, n * n * sizeof *work);
    const abfp_real root = abfp_sqrt(loading);
    for (size_t i = 0; i < n; i++) { /* loading: n more rows, sqrt(loading) I */
        abfp_complex v[ABFP_N];
        memset(v, 0, sizeof v);
        v[i] = abfp_c(root, 0);
        absorb_row(work, v, n, i);
    }
    abfp_real energy = 0;
    for (size_t i = 0; i < n; i++) { /* T^H z = a, forward */
        abfp_complex sum = a[i];
        for (size_t p = 0; p < i; p++) {
            sum = abfp_sub(sum, abfp_cmul(work[p * n + i], w[p]));
        }
        if (!(work[i * n + i].re > ABFP_TINY)) {
            return 0;
        }
        w[i] = abfp_scale(sum, ABFP_R(1) / work[i * n + i].re);
        energy += abfp_norm2(w[i]); /* a^H R^-1 a = |z|^2 */
    }
    if (!(energy > ABFP_TINY) || !abfp_finite(energy)) {
        return 0;
    }
    for (size_t i = n; i-- > 0;) { /* T u = z, backward */
        abfp_complex sum = w[i];
        for (size_t p = i + 1; p < n; p++) {
            sum = abfp_sub(sum, abfp_mul(work[i * n + p], w[p]));
        }
        w[i] = abfp_scale(sum, ABFP_R(1) / work[i * n + i].re);
    }
    for (size_t i = 0; i < n; i++) {
        w[i] = abfp_scale(w[i], ABFP_R(1) / energy);
    }
    return 1;
}
