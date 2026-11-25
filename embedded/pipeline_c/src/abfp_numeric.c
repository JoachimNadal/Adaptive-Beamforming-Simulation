/* Eigenvalues, source counting and root-MUSIC. */
#include <string.h>

#include "abfp_math.h"

#define PI 3.14159265358979323846

/* ---- Hermitian eigenproblem ---------------------------------------------------------- */

/* One Jacobi rotation annihilating a[p][q].
 *
 * With a[p][q] = |g| e^(j phi), column q is first multiplied by e^(-j phi), which makes the
 * 2 x 2 block real, then the classical real rotation is applied. */
static void rotate(abfp_complex* a, abfp_complex* v, size_t n, size_t p, size_t q) {
    const abfp_complex g = a[p * n + q];
    const abfp_real magnitude = abfp_hypot(g.re, g.im);
    const abfp_complex unit = abfp_c(g.re / magnitude, -g.im / magnitude); /* e^(-j phi) */
    const abfp_real theta = (a[q * n + q].re - a[p * n + p].re) / (ABFP_R(2) * magnitude);
    abfp_real t = ABFP_R(1) / (abfp_fabs(theta) + abfp_hypot(theta, ABFP_R(1)));
    if (theta < ABFP_R(0)) {
        t = -t;
    }
    const abfp_real c = ABFP_R(1) / abfp_hypot(t, ABFP_R(1));
    const abfp_real s = t * c;
    const abfp_real app = a[p * n + p].re - t * magnitude;
    const abfp_real aqq = a[q * n + q].re + t * magnitude;

    for (size_t k = 0; k < n; k++) { /* columns of a and v */
        const abfp_complex akp = a[k * n + p];
        const abfp_complex akq = abfp_mul(unit, a[k * n + q]);
        a[k * n + p] = abfp_c(c * akp.re - s * akq.re, c * akp.im - s * akq.im);
        a[k * n + q] = abfp_c(s * akp.re + c * akq.re, s * akp.im + c * akq.im);
        const abfp_complex vkp = v[k * n + p];
        const abfp_complex vkq = abfp_mul(unit, v[k * n + q]);
        v[k * n + p] = abfp_c(c * vkp.re - s * vkq.re, c * vkp.im - s * vkq.im);
        v[k * n + q] = abfp_c(s * vkp.re + c * vkq.re, s * vkp.im + c * vkq.im);
    }
    for (size_t k = 0; k < n; k++) { /* rows follow by symmetry */
        a[p * n + k] = abfp_c(a[k * n + p].re, -a[k * n + p].im);
        a[q * n + k] = abfp_c(a[k * n + q].re, -a[k * n + q].im);
    }
    a[p * n + p] = abfp_c(app, 0);
    a[q * n + q] = abfp_c(aqq, 0);
    a[p * n + q] = abfp_c(0, 0);
    a[q * n + p] = abfp_c(0, 0);
}

abf_status abfp_eigh(abfp_complex* a, size_t n, abfp_real* values, abfp_complex* vectors) {
    enum { MAX_SWEEPS = 30 };
    if (a == NULL || values == NULL || vectors == NULL || n == 0 || n > ABFP_N) {
        return ABF_ERR_ARG;
    }
    abfp_real total = 0;
    for (size_t i = 0; i < n * n; i++) {
        vectors[i] = abfp_c(0, 0);
        total += abfp_norm2(a[i]);
    }
    if (!abfp_finite(total)) {
        return ABF_ERR_NUMERIC;
    }
    for (size_t i = 0; i < n; i++) {
        vectors[i * n + i] = abfp_c(1, 0);
    }
    int converged = 0;
    for (int sweep = 0; sweep < MAX_SWEEPS && !converged; sweep++) {
        converged = 1;
        for (size_t p = 0; p + 1 < n; p++) {
            for (size_t q = p + 1; q < n; q++) {
                /* relative test: keeps small eigenvalues accurate next to large ones */
                const abfp_real off = abfp_norm2(a[p * n + q]);
                const abfp_real scale = abfp_fabs(a[p * n + p].re) * abfp_fabs(a[q * n + q].re);
                if (off > ABFP_EPS * ABFP_EPS * scale && off > ABFP_TINY) {
                    rotate(a, vectors, n, p, q);
                    converged = 0;
                }
            }
        }
    }
    /* A relative test can stall on round-off; accept if what is left is negligible. */
    if (!converged) {
        abfp_real off = 0;
        for (size_t i = 0; i < n; i++) {
            for (size_t j = 0; j < n; j++) {
                off += (i == j) ? ABFP_R(0) : abfp_norm2(a[i * n + j]);
            }
        }
        const abfp_real limit = ABFP_R(100) * ABFP_EPS;
        if (!(off <= limit * limit * total)) {
            return ABF_ERR_NUMERIC;
        }
    }
    for (size_t i = 0; i < n; i++) {
        values[i] = a[i * n + i].re;
    }
    for (size_t i = 0; i + 1 < n; i++) { /* ascending order */
        size_t smallest = i;
        for (size_t j = i + 1; j < n; j++) {
            if (values[j] < values[smallest]) {
                smallest = j;
            }
        }
        if (smallest != i) {
            const abfp_real value = values[i];
            values[i] = values[smallest];
            values[smallest] = value;
            for (size_t k = 0; k < n; k++) {
                const abfp_complex swap = vectors[k * n + i];
                vectors[k * n + i] = vectors[k * n + smallest];
                vectors[k * n + smallest] = swap;
            }
        }
    }
    return ABF_OK;
}

int abfp_mdl(const abfp_real* values, size_t n, abfp_real snapshots) {
    if (values == NULL || n == 0 || n > ABFP_N || !(snapshots > ABFP_R(1))) {
        return 0;
    }
    const abfp_real largest = values[n - 1] > ABFP_TINY ? values[n - 1] : ABFP_TINY;
    /* Guards the logarithm only: callers clamp to what their computation resolves. */
    const abfp_real floor_value = ABFP_EPS * ABFP_EPS * largest;
    abfp_real best_score = 0;
    int best = 0;
    abfp_real sum = 0;
    abfp_real sum_log = 0;
    /* order n - 1 down to 0: the noise set grows by one eigenvalue at a time */
    for (size_t count = 1; count <= n; count++) {
        const abfp_real v = values[count - 1] > floor_value ? values[count - 1] : floor_value;
        sum += v;
        sum_log += abfp_log(v);
        const abfp_real m = (abfp_real)count;
        const abfp_real sphericity = abfp_log(sum / m) - sum_log / m;
        const abfp_real order = (abfp_real)(n - count);
        const abfp_real score =
            snapshots * m * sphericity +
            ABFP_R(0.5) * order * (ABFP_R(2) * (abfp_real)n - order) * abfp_log(snapshots);
        if (count == 1 || score <= best_score) { /* ties go to the smaller order */
            best_score = score;
            best = (int)(n - count);
        }
    }
    return best;
}

/* ---- polynomial roots ---------------------------------------------------------------- */

int abfp_polynomial_roots(const double* c_re, const double* c_im, int degree, double* z_re,
                          double* z_im) {
    enum { MAX_ITERATIONS = 200 };
    if (c_re == NULL || c_im == NULL || z_re == NULL || z_im == NULL || degree < 1 ||
        degree > 2 * ABFP_N - 2) {
        return 0;
    }
    for (int k = 0; k < degree; k++) { /* two circles around the unit circle, no symmetry */
        const double radius = (k % 2 == 0) ? 0.85 : 1.2;
        const double angle = 2.0 * PI * (double)k / (double)degree + 0.35;
        z_re[k] = radius * cos(angle);
        z_im[k] = radius * sin(angle);
    }
    for (int iteration = 0; iteration < MAX_ITERATIONS; iteration++) {
        double largest = 0.0;
        for (int k = 0; k < degree; k++) {
            const double x = z_re[k];
            const double y = z_im[k];
            double pr = c_re[0];
            double pi = c_im[0];
            double dr = 0.0;
            double di = 0.0;
            for (int i = 1; i <= degree; i++) { /* Horner, with derivative */
                const double ndr = dr * x - di * y + pr;
                di = dr * y + di * x + pi;
                dr = ndr;
                const double npr = pr * x - pi * y + c_re[i];
                pi = pr * y + pi * x + c_im[i];
                pr = npr;
            }
            const double dd = dr * dr + di * di;
            if (pr * pr + pi * pi == 0.0 || dd == 0.0) {
                continue;
            }
            const double wr = (pr * dr + pi * di) / dd; /* Newton step p / p' */
            const double wi = (pi * dr - pr * di) / dd;
            double sr = 0.0;
            double si = 0.0;
            for (int j = 0; j < degree; j++) {
                if (j != k) {
                    const double ex = x - z_re[j];
                    const double ey = y - z_im[j];
                    const double e2 = ex * ex + ey * ey;
                    if (e2 > 0.0) {
                        sr += ex / e2;
                        si -= ey / e2;
                    }
                }
            }
            const double qr = 1.0 - (wr * sr - wi * si);
            const double qi = -(wr * si + wi * sr);
            const double q2 = qr * qr + qi * qi;
            if (q2 == 0.0) {
                continue;
            }
            const double stepr = (wr * qr + wi * qi) / q2;
            const double stepi = (wi * qr - wr * qi) / q2;
            z_re[k] = x - stepr;
            z_im[k] = y - stepi;
            const double step = fabs(stepr) + fabs(stepi);
            largest = step > largest ? step : largest;
        }
        if (largest < 1e-13) {
            break;
        }
    }
    return degree;
}

int abfp_root_music(const abfp_complex* vectors, size_t n, size_t sources, float d_over_lambda,
                    float* angles) {
    enum { MAX_DEGREE = 2 * ABFP_N - 2 };
    if (vectors == NULL || angles == NULL || n < 2 || n > ABFP_N || sources == 0 || sources >= n ||
        !(d_over_lambda > 0.0f)) {
        return 0;
    }
    /* Coefficient of z^l is the sum of the l-th diagonal of U_n U_n^H. It is Hermitian: only
     * l >= 0 is computed. Highest power first. */
    double c_re[MAX_DEGREE + 1];
    double c_im[MAX_DEGREE + 1];
    const int degree = (int)(2 * (n - 1));
    for (size_t lag = 0; lag < n; lag++) {
        double re = 0.0;
        double im = 0.0;
        for (size_t i = 0; i + lag < n; i++) {
            for (size_t e = 0; e < n - sources; e++) { /* U[i] conj(U[i + lag]) */
                const abfp_complex u = vectors[i * n + e];
                const abfp_complex w = vectors[(i + lag) * n + e];
                re += (double)u.re * (double)w.re + (double)u.im * (double)w.im;
                im += (double)u.im * (double)w.re - (double)u.re * (double)w.im;
            }
        }
        c_re[n - 1 - lag] = re;
        c_im[n - 1 - lag] = im;
        c_re[n - 1 + lag] = re;
        c_im[n - 1 + lag] = -im;
    }
    double z_re[MAX_DEGREE];
    double z_im[MAX_DEGREE];
    if (abfp_polynomial_roots(c_re, c_im, degree, z_re, z_im) != degree) {
        return 0;
    }
    double magnitude[MAX_DEGREE];
    for (int i = 0; i < degree; i++) {
        magnitude[i] = hypot(z_re[i], z_im[i]);
    }
    for (int i = 0; i < degree; i++) { /* sort by magnitude */
        int smallest = i;
        for (int j = i + 1; j < degree; j++) {
            if (magnitude[j] < magnitude[smallest]) {
                smallest = j;
            }
        }
        const double m = magnitude[i];
        const double re = z_re[i];
        const double im = z_im[i];
        magnitude[i] = magnitude[smallest];
        z_re[i] = z_re[smallest];
        z_im[i] = z_im[smallest];
        magnitude[smallest] = m;
        z_re[smallest] = re;
        z_im[smallest] = im;
    }
    /* roots come in conjugate-reciprocal pairs: the inner half, nearest the circle last */
    for (size_t i = 0; i < sources; i++) {
        const size_t index = n - 2 - i;
        double sine = -atan2(z_im[index], z_re[index]) / (2.0 * PI * (double)d_over_lambda);
        sine = sine > 1.0 ? 1.0 : (sine < -1.0 ? -1.0 : sine);
        angles[i] = (float)asin(sine);
    }
    for (size_t i = 0; i + 1 < sources; i++) {
        for (size_t j = i + 1; j < sources; j++) {
            if (angles[j] < angles[i]) {
                const float swap = angles[i];
                angles[i] = angles[j];
                angles[j] = swap;
            }
        }
    }
    return (int)sources;
}
