/* Block pipeline. Follows embedded/common/pipeline.py step by step in Phase 1 mode. */
#include <string.h>

#include "abfp_internal.h"

#define TWO_PI 6.28318530717958647692

size_t abfp_state_size(void) {
    return sizeof(abfp_state);
}

static void steering(const abfp_state* s, double theta, abfp_complex* a, size_t stride) {
    const size_t n = (size_t)s->config.num_antennas;
    const double step = -TWO_PI * (double)s->config.d_over_lambda * sin(theta);
    for (size_t m = 0; m < n; m++) {
        a[m * stride] = abfp_c((abfp_real)cos(step * (double)m), (abfp_real)sin(step * (double)m));
    }
}

static void reset_covariance(abfp_state* s) {
    memset(s->r_sum, 0, sizeof s->r_sum);
    s->weight_sum = 0;
    s->weight_squared = 0;
}

static void set_das(abfp_state* s) {
    const size_t n = (size_t)s->config.num_antennas;
    for (size_t i = 0; i < n; i++) {
        s->weights[i].re = (float)(s->a_target[i].re / (abfp_real)n);
        s->weights[i].im = (float)(s->a_target[i].im / (abfp_real)n);
    }
}

abf_status abfp_init(abfp_state* s, const abfp_config* c) {
    if (s == NULL || c == NULL || c->num_antennas < 2 || c->num_antennas > ABFP_N ||
        c->mode < ABFP_PHASE1 || c->mode > ABFP_NOISE_LOADED_SQRT ||
        !(c->d_over_lambda > 0.0f && c->d_over_lambda <= 0.5005f) ||
        !(c->target_rad >= -1.5708f && c->target_rad <= 1.5708f) ||
        !(c->covariance_beta >= 0.0f && c->covariance_beta < 1.0f) ||
        !(c->relative_loading > 0.0f && c->relative_loading <= 1.0f) ||
        !(c->noise_factor >= 0.0f && c->noise_factor <= 1e6f) || c->max_interferers < 0 ||
        c->max_interferers >= c->num_antennas || !(c->guard_rad > 0.0f) ||
        !(c->min_interferer_inr >= 0.0f) ||
        !(c->min_wng_ratio >= 0.0f && c->min_wng_ratio < 1.0f)) {
        return ABF_ERR_ARG;
    }
    memset(s, 0, sizeof *s);
    s->config = *c;
    steering(s, (double)c->target_rad, s->a_target, 1);
    set_das(s);
    return ABF_OK;
}

abf_status abfp_set_calibration(abfp_state* s, const abf_cf32* gains) {
    if (s == NULL || gains == NULL) {
        return ABF_ERR_ARG;
    }
    const size_t n = (size_t)s->config.num_antennas;
    for (size_t i = 0; i < n; i++) {
        const float energy = gains[i].re * gains[i].re + gains[i].im * gains[i].im;
        if (!(energy > 1e-18f) || !(energy - energy == 0.0f)) {
            return ABF_ERR_NUMERIC; /* dead or undefined channel: nothing changed yet */
        }
    }
    for (size_t i = 0; i < n; i++) {
        const float energy = gains[i].re * gains[i].re + gains[i].im * gains[i].im;
        s->calibration_inverse[i].re = gains[i].re / energy;
        s->calibration_inverse[i].im = -gains[i].im / energy;
    }
    s->calibrated = 1;
    reset_covariance(s);
    return ABF_OK;
}

/* ---- covariance ---------------------------------------------------------------------- */

/* r <- (1 / k) sum x x^H. Returns 0 if any sample is not finite. */
static int block_covariance(abfp_complex* r, const abf_cf32* x, size_t n, size_t k) {
    memset(r, 0, n * n * sizeof *r);
    for (size_t t = 0; t < k; t++) {
        const abf_cf32* v = x + t * n;
        for (size_t i = 0; i < n; i++) {
            const abfp_real xr = (abfp_real)v[i].re;
            const abfp_real xi = (abfp_real)v[i].im;
            abfp_complex* row = r + i * n;
            for (size_t j = i; j < n; j++) { /* v[i] conj(v[j]) */
                const abfp_real yr = (abfp_real)v[j].re;
                const abfp_real yi = (abfp_real)v[j].im;
                row[j].re += xr * yr + xi * yi;
                row[j].im += xi * yr - xr * yi;
            }
        }
    }
    const abfp_real scale = ABFP_R(1) / (abfp_real)k;
    for (size_t i = 0; i < n; i++) {
        if (!abfp_finite(r[i * n + i].re)) {
            return 0;
        }
        r[i * n + i] = abfp_c(r[i * n + i].re * scale, 0);
        for (size_t j = i + 1; j < n; j++) {
            r[i * n + j] = abfp_scale(r[i * n + j], scale);
            r[j * n + i] = abfp_c(r[i * n + j].re, -r[i * n + j].im);
        }
    }
    return 1;
}

/* ---- linear algebra ------------------------------------------------------------------ */

/* In-place Cholesky, lower triangle. */
static int cholesky(abfp_complex* l, size_t n) {
    for (size_t j = 0; j < n; j++) {
        const abfp_real original = l[j * n + j].re;
        abfp_real pivot = original;
        for (size_t p = 0; p < j; p++) {
            pivot -= abfp_norm2(l[j * n + p]);
        }
        if (!(pivot > (abfp_real)n * ABFP_EPS * original) || !abfp_finite(pivot)) {
            return 0;
        }
        const abfp_real diagonal = abfp_sqrt(pivot);
        l[j * n + j] = abfp_c(diagonal, 0);
        for (size_t i = j + 1; i < n; i++) {
            abfp_complex sum = l[i * n + j];
            for (size_t p = 0; p < j; p++) { /* l[i][p] conj(l[j][p]) */
                sum = abfp_sub(sum, abfp_cmul(l[j * n + p], l[i * n + p]));
            }
            l[i * n + j] = abfp_scale(sum, ABFP_R(1) / diagonal);
        }
    }
    return 1;
}

/* Solves L L^H x = b in place for one right-hand side stored with a stride. */
static void cholesky_solve(const abfp_complex* l, size_t n, abfp_complex* b, size_t stride) {
    for (size_t i = 0; i < n; i++) {
        abfp_complex sum = b[i * stride];
        for (size_t p = 0; p < i; p++) {
            sum = abfp_sub(sum, abfp_mul(l[i * n + p], b[p * stride]));
        }
        b[i * stride] = abfp_scale(sum, ABFP_R(1) / l[i * n + i].re);
    }
    for (size_t i = n; i-- > 0;) {
        abfp_complex sum = b[i * stride];
        for (size_t p = i + 1; p < n; p++) {
            sum = abfp_sub(sum, abfp_cmul(l[p * n + i], b[p * stride]));
        }
        b[i * stride] = abfp_scale(sum, ABFP_R(1) / l[i * n + i].re);
    }
}

static abfp_real trace(const abfp_complex* r, size_t n) {
    abfp_real t = 0;
    for (size_t i = 0; i < n; i++) {
        t += r[i * n + i].re;
    }
    return t;
}

/* White noise gain of candidate weights toward the target; 0 if they are not finite. */
static abfp_real gain_of(const abfp_state* s, const abfp_complex* w) {
    const size_t n = (size_t)s->config.num_antennas;
    abfp_complex response = abfp_c(0, 0);
    abfp_real energy = 0;
    for (size_t i = 0; i < n; i++) {
        response = abfp_add(response, abfp_cmul(w[i], s->a_target[i]));
        energy += abfp_norm2(w[i]);
    }
    if (!(energy > ABFP_R(0)) || !abfp_finite(energy)) {
        return 0;
    }
    return abfp_norm2(response) / energy;
}

/* Keeps candidate weights if their white noise gain is acceptable. */
static int accept(abfp_state* s, const abfp_complex* w) {
    const size_t n = (size_t)s->config.num_antennas;
    if (!(gain_of(s, w) >= (abfp_real)s->config.min_wng_ratio * (abfp_real)n)) {
        return 0;
    }
    for (size_t i = 0; i < n; i++) {
        s->weights[i].re = (float)w[i].re;
        s->weights[i].im = (float)w[i].im;
    }
    return 1;
}

/* Copies R + loading I, scaled to unit mean eigenvalue, into work and factorises it. */
static int factor_loaded(abfp_state* s, abfp_real loading) {
    const size_t n = (size_t)s->config.num_antennas;
    const abfp_real scale = (abfp_real)n / trace(s->r, n);
    for (size_t i = 0; i < n * n; i++) {
        s->work[i] = abfp_scale(s->r[i], scale);
    }
    for (size_t i = 0; i < n; i++) {
        s->work[i * n + i].re += loading * scale;
    }
    return cholesky(s->work, n);
}

/* MVDR weights from the factor in work. */
static int solve_mvdr(abfp_state* s) {
    const size_t n = (size_t)s->config.num_antennas;
    abfp_complex w[ABFP_N];
    memcpy(w, s->a_target, sizeof w);
    cholesky_solve(s->work, n, w, 1);
    abfp_real denominator = 0;
    for (size_t i = 0; i < n; i++) {
        denominator += abfp_cmul(s->a_target[i], w[i]).re;
    }
    if (!(denominator > ABFP_TINY) || !abfp_finite(denominator)) {
        return 0;
    }
    for (size_t i = 0; i < n; i++) {
        w[i] = abfp_scale(w[i], ABFP_R(1) / denominator);
    }
    return accept(s, w);
}

/* LCMV weights from the factor in work: target, optional derivative, explicit nulls. */
static int solve_lcmv(abfp_state* s, const abfp_result* result, int derivative) {
    const size_t n = (size_t)s->config.num_antennas;
    abfp_complex* C = s->constraints; /* row-major n x columns, row stride n */
    size_t columns = 0;
    for (size_t i = 0; i < n; i++) {
        C[i * n] = s->a_target[i];
    }
    columns = 1;
    if (derivative) {
        /* d a_m / d theta is proportional to -j m a_m. Removing its component along a leaves
         * -j (m - (n - 1) / 2) a_m: the constraint referenced to the array centre. */
        abfp_real energy = 0;
        for (size_t i = 0; i < n; i++) {
            const abfp_real offset = (abfp_real)i - ABFP_R(0.5) * (abfp_real)(n - 1);
            const abfp_complex a = s->a_target[i];
            C[i * n + 1] = abfp_c(offset * a.im, -offset * a.re);
            energy += offset * offset;
        }
        const abfp_real scale = abfp_sqrt((abfp_real)n / energy);
        for (size_t i = 0; i < n; i++) {
            C[i * n + 1] = abfp_scale(C[i * n + 1], scale);
        }
        columns = 2;
    }
    for (int32_t k = 0; k < result->num_nulls; k++) {
        steering(s, (double)result->nulls_rad[k], C + columns, n);
        columns++;
    }
    for (size_t i = 0; i < n; i++) {
        for (size_t c = 0; c < columns; c++) {
            s->solved[i * n + c] = C[i * n + c];
        }
    }
    for (size_t c = 0; c < columns; c++) {
        cholesky_solve(s->work, n, s->solved + c, n);
    }
    /* G = C^H R^-1 C, stored in vectors (no longer needed) */
    abfp_complex* G = s->vectors;
    for (size_t p = 0; p < columns; p++) {
        for (size_t q = 0; q < columns; q++) {
            abfp_complex sum = abfp_c(0, 0);
            for (size_t i = 0; i < n; i++) {
                sum = abfp_add(sum, abfp_cmul(C[i * n + p], s->solved[i * n + q]));
            }
            G[p * columns + q] = sum;
        }
    }
    for (size_t p = 0; p < columns; p++) { /* exact Hermitian symmetry */
        G[p * columns + p].im = 0;
        for (size_t q = p + 1; q < columns; q++) {
            const abfp_complex a = G[p * columns + q];
            const abfp_complex b = G[q * columns + p];
            const abfp_complex m = abfp_c(ABFP_R(0.5) * (a.re + b.re), ABFP_R(0.5) * (a.im - b.im));
            G[p * columns + q] = m;
            G[q * columns + p] = abfp_c(m.re, -m.im);
        }
    }
    if (!cholesky(G, columns)) {
        return 0;
    }
    abfp_complex f[ABFP_N];
    memset(f, 0, sizeof f);
    f[0] = abfp_c(1, 0);
    cholesky_solve(G, columns, f, 1);
    abfp_complex w[ABFP_N];
    for (size_t i = 0; i < n; i++) {
        abfp_complex sum = abfp_c(0, 0);
        for (size_t c = 0; c < columns; c++) {
            sum = abfp_add(sum, abfp_mul(s->solved[i * n + c], f[c]));
        }
        w[i] = sum;
    }
    return accept(s, w);
}

/* ---- interferers --------------------------------------------------------------------- */

/* Least-squares source powers: diag(A+ (R - noise I) A+^H). Returns 0 if A is degenerate. */
static int source_powers(abfp_state* s, const abfp_result* result, abfp_real noise,
                         abfp_real* powers) {
    const size_t n = (size_t)s->config.num_antennas;
    const size_t count = (size_t)result->num_doas;
    abfp_complex* A = s->constraints;
    abfp_complex gram[ABFP_N * ABFP_N];
    for (size_t k = 0; k < count; k++) {
        steering(s, (double)result->doas_rad[k], A + k, n);
    }
    for (size_t p = 0; p < count; p++) {
        for (size_t q = 0; q < count; q++) {
            abfp_complex sum = abfp_c(0, 0);
            for (size_t i = 0; i < n; i++) {
                sum = abfp_add(sum, abfp_cmul(A[i * n + p], A[i * n + q]));
            }
            gram[p * count + q] = sum;
        }
    }
    if (!cholesky(gram, count)) {
        return 0;
    }
    for (size_t k = 0; k < count; k++) {
        /* row k of the pseudo-inverse is (A G^-1 e_k)^H */
        abfp_complex e[ABFP_N];
        memset(e, 0, sizeof e);
        e[k] = abfp_c(1, 0);
        cholesky_solve(gram, count, e, 1);
        abfp_complex b[ABFP_N];
        for (size_t i = 0; i < n; i++) {
            b[i] = abfp_c(0, 0);
            for (size_t c = 0; c < count; c++) {
                b[i] = abfp_add(b[i], abfp_mul(A[i * n + c], e[c]));
            }
        }
        abfp_real power = 0;
        abfp_real energy = 0;
        for (size_t i = 0; i < n; i++) {
            abfp_complex rb = abfp_c(0, 0);
            for (size_t j = 0; j < n; j++) {
                rb = abfp_add(rb, abfp_mul(s->r[i * n + j], b[j]));
            }
            power += abfp_cmul(b[i], rb).re;
            energy += abfp_norm2(b[i]);
        }
        powers[k] = power - noise * energy;
    }
    return 1;
}

static void select_interferers(abfp_state* s, abfp_real noise, abfp_result* result) {
    abfp_real powers[ABFP_N];
    if (!source_powers(s, result, noise, powers)) {
        return;
    }
    int candidates[ABFP_N];
    int count = 0;
    for (int k = 0; k < result->num_doas; k++) {
        const float distance = fabsf(result->doas_rad[k] - s->config.target_rad);
        if (powers[k] > noise * (abfp_real)s->config.min_interferer_inr &&
            distance > s->config.guard_rad) {
            candidates[count++] = k;
        }
    }
    for (int i = 0; i + 1 < count; i++) { /* strongest first */
        for (int j = i + 1; j < count; j++) {
            if (powers[candidates[j]] > powers[candidates[i]]) {
                const int swap = candidates[i];
                candidates[i] = candidates[j];
                candidates[j] = swap;
            }
        }
    }
    int limit = s->config.num_antennas - 1 - (s->config.derivative_constraint ? 1 : 0);
    if (limit > s->config.max_interferers) {
        limit = s->config.max_interferers;
    }
    if (count > limit) {
        result->status |= ABFP_NULLS_DROPPED;
        count = limit;
    }
    for (int k = 0; k < count; k++) {
        result->nulls_rad[k] = result->doas_rad[candidates[k]];
    }
    result->num_nulls = count;
}

/* ---- adaptation ---------------------------------------------------------------------- */

static int update_covariance(abfp_state* s, const abf_cf32* x, size_t k) {
    const size_t n = (size_t)s->config.num_antennas;
    if (!block_covariance(s->r, x, n, k)) {
        return 0;
    }
    const abfp_real beta = (abfp_real)s->config.covariance_beta;
    const abfp_real fresh = ABFP_R(1) - beta;
    s->weight_sum = beta * s->weight_sum + fresh;
    s->weight_squared = beta * beta * s->weight_squared + fresh * fresh;
    for (size_t i = 0; i < n * n; i++) {
        s->r_sum[i].re = beta * s->r_sum[i].re + fresh * s->r[i].re;
        s->r_sum[i].im = beta * s->r_sum[i].im + fresh * s->r[i].im;
        s->r[i] = abfp_scale(s->r_sum[i], ABFP_R(1) / s->weight_sum);
    }
    return 1;
}

/* Noise-loaded MVDR on the triangular factor, kept in r_sum. */
static void adapt_sqrt(abfp_state* s, const abf_cf32* x, size_t k, abfp_result* result) {
    const size_t n = (size_t)s->config.num_antennas;
    const abfp_real beta = (abfp_real)s->config.covariance_beta;
    const abfp_real fresh = ABFP_R(1) - beta;
    memcpy(s->r, s->r_sum, sizeof s->r); /* to be restored if the block overflows */
    if (!abfp_sqrt_update(s->r_sum, n, x, k, beta)) {
        memcpy(s->r_sum, s->r, sizeof s->r);
        result->status |= ABFP_WEIGHTS_HELD;
        return;
    }
    s->weight_sum = beta * s->weight_sum + fresh;
    s->weight_squared = beta * beta * s->weight_squared + fresh * fresh;
    const abfp_real effective = (abfp_real)k * s->weight_sum * s->weight_sum / s->weight_squared;
    if (abfp_sqrt_eigenvalues(s->r_sum, n, s->work, s->values) != ABF_OK ||
        !(s->values[n - 1] > ABFP_TINY)) {
        result->status |= ABFP_WEIGHTS_HELD;
        return;
    }
    const int order = abfp_mdl(s->values, n, effective);
    abfp_real noise = 0;
    for (size_t i = 0; i < n - (size_t)order; i++) {
        noise += s->values[i];
    }
    noise /= (abfp_real)(n - (size_t)order);
    result->num_sources = order;
    result->noise_power = (float)(noise / s->weight_sum); /* r_sum is not bias-corrected */
    abfp_complex w[ABFP_N];
    if (abfp_sqrt_mvdr(s->r_sum, n, (abfp_real)s->config.noise_factor * noise, s->a_target, s->work,
                       w) &&
        accept(s, w)) {
        result->method = ABFP_METHOD_MVDR;
        return;
    }
    result->status |= ABFP_FALLBACK_DAS;
    set_das(s);
    result->method = ABFP_METHOD_DAS;
}

static void adapt(abfp_state* s, size_t k, abfp_result* result) {
    const size_t n = (size_t)s->config.num_antennas;
    if (!(trace(s->r, n) > ABFP_TINY)) { /* silence: nothing to learn */
        result->status |= ABFP_WEIGHTS_HELD;
        return;
    }
    const abfp_real effective = (abfp_real)k * s->weight_sum * s->weight_sum / s->weight_squared;
    memcpy(s->work, s->r, n * n * sizeof *s->work);
    if (abfp_eigh(s->work, n, s->values, s->vectors) != ABF_OK) {
        result->status |= ABFP_WEIGHTS_HELD;
        return;
    }
    /* Eigenvalues of a covariance carry an absolute error of about n eps times the largest one.
     * Smaller values (possibly negative) are meaningless: clamp them and say so. */
    const abfp_real resolution = (abfp_real)n * ABFP_EPS * s->values[n - 1];
    if (s->values[0] < ABFP_R(2) * resolution) {
        result->status |= ABFP_PRECISION_LIMITED;
    }
    for (size_t i = 0; i < n; i++) {
        s->values[i] = s->values[i] > resolution ? s->values[i] : resolution;
    }
    const int order = abfp_mdl(s->values, n, effective);
    abfp_real noise = 0;
    for (size_t i = 0; i < n - (size_t)order; i++) {
        noise += s->values[i];
    }
    noise /= (abfp_real)(n - (size_t)order);
    result->num_sources = order;
    result->noise_power = (float)noise;

    if (s->config.mode == ABFP_NOISE_LOADED) {
        if (factor_loaded(s, (abfp_real)s->config.noise_factor * noise) && solve_mvdr(s)) {
            result->method = ABFP_METHOD_MVDR;
            return;
        }
        result->status |= ABFP_FALLBACK_DAS;
        set_das(s);
        result->method = ABFP_METHOD_DAS;
        return;
    }

    int derivative = s->config.derivative_constraint != 0;
    if (order >= (int)n - 1) {
        result->status |= ABFP_TOO_MANY_SOURCES;
        derivative = 0; /* the degree of freedom is worth more as a null */
    } else if (order > 0) {
        result->num_doas = abfp_root_music(s->vectors, n, (size_t)order, s->config.d_over_lambda,
                                           result->doas_rad);
        select_interferers(s, noise, result);
    }
    const abfp_real loading = (abfp_real)s->config.relative_loading * trace(s->r, n) / (abfp_real)n;
    const int factored = factor_loaded(s, loading);
    if (factored && solve_lcmv(s, result, derivative)) {
        result->method = ABFP_METHOD_LCMV;
        return;
    }
    result->status |= ABFP_FALLBACK_MVDR;
    result->num_nulls = 0;
    if (factored && solve_mvdr(s)) {
        result->method = ABFP_METHOD_MVDR;
        return;
    }
    result->status |= ABFP_FALLBACK_DAS;
    set_das(s);
    result->method = ABFP_METHOD_DAS;
}

static uint32_t track_link(abfp_state* s, uint32_t sequence, uint32_t flags) {
    uint32_t status = 0;
    if (s->has_sequence && sequence != s->last_sequence + 1u) {
        status |= ABFP_SEQUENCE_GAP;
    }
    s->has_sequence = 1;
    s->last_sequence = sequence;
    if (flags & ABF_FLAG_ADC_OVERFLOW) {
        status |= ABFP_ADC_OVERFLOW;
    }
    if (flags & ABF_FLAG_CLOCK_UNLOCKED) {
        status |= ABFP_CLOCK_UNLOCKED; /* phases restart at random: calibration is lost */
        s->calibrated = 0;
        reset_covariance(s);
    }
    if (flags & ABF_FLAG_GAIN_CHANGED) {
        reset_covariance(s);
    }
    if (!s->calibrated) {
        status |= ABFP_UNCALIBRATED;
    }
    return status;
}

abf_status abfp_process(abfp_state* s, abf_cf32* x, size_t k, uint32_t sequence,
                        uint32_t frame_flags, abf_cf32* y, abfp_result* result) {
    if (s == NULL || x == NULL || y == NULL || result == NULL || k == 0 || k > ABF_MAX_SAMPLES ||
        s->config.num_antennas < 2) {
        return ABF_ERR_ARG;
    }
    const size_t n = (size_t)s->config.num_antennas;
    memset(result, 0, sizeof *result);
    result->status = track_link(s, sequence, frame_flags);

    if (s->calibrated) {
        for (size_t t = 0; t < k; t++) {
            for (size_t i = 0; i < n; i++) {
                const abf_cf32 v = x[t * n + i];
                const abf_cf32 g = s->calibration_inverse[i];
                x[t * n + i].re = v.re * g.re - v.im * g.im;
                x[t * n + i].im = v.re * g.im + v.im * g.re;
            }
        }
    }
    /* Non-finite data must not reach the recursive sum: the block is tested first. */
    float energy = 0.0f;
    for (size_t i = 0; i < n * k; i++) {
        energy += x[i].re * 0.0f + x[i].im * 0.0f; /* NaN or infinity times zero is NaN */
    }
    if (energy != 0.0f) {
        result->status |= ABFP_INVALID_DATA | ABFP_WEIGHTS_HELD;
        memset(y, 0, k * sizeof *y);
    } else {
        if (result->status & (ABFP_ADC_OVERFLOW | ABFP_CLOCK_UNLOCKED)) {
            result->status |= ABFP_WEIGHTS_HELD;
        } else if (s->config.mode == ABFP_NOISE_LOADED_SQRT) {
            adapt_sqrt(s, x, k, result);
        } else if (update_covariance(s, x, k)) {
            adapt(s, k, result);
        } else {
            result->status |= ABFP_WEIGHTS_HELD; /* overflow of the accumulator */
        }
        (void)abf_apply_weights(s->weights, x, n, k, y);
    }
    abf_cf32 target[ABFP_N];
    for (size_t i = 0; i < n; i++) {
        target[i].re = (float)s->a_target[i].re;
        target[i].im = (float)s->a_target[i].im;
    }
    result->wng = abf_white_noise_gain(s->weights, target, n);
    return ABF_OK;
}

abf_status abfp_calibrate(abfp_state* s, const abf_cf32* x, size_t k, float source_rad) {
    if (s == NULL || x == NULL || k == 0 || !(source_rad >= -1.5708f && source_rad <= 1.5708f)) {
        return ABF_ERR_ARG;
    }
    const size_t n = (size_t)s->config.num_antennas;
    if (!block_covariance(s->work, x, n, k) ||
        abfp_eigh(s->work, n, s->values, s->vectors) != ABF_OK) {
        return ABF_ERR_NUMERIC;
    }
    abfp_complex a[ABFP_N];
    abf_cf32 gains[ABFP_N];
    steering(s, (double)source_rad, a, 1);
    abfp_complex reference = abfp_c(0, 0);
    abfp_real largest = 0;
    for (size_t i = 0; i < n; i++) { /* principal eigenvector, steering phases removed */
        const abfp_complex g = abfp_cmul(a[i], s->vectors[i * n + n - 1]);
        if (i == 0) {
            reference = g;
        }
        largest = abfp_norm2(g) > largest ? abfp_norm2(g) : largest;
    }
    const abfp_real energy = abfp_norm2(reference);
    if (!(energy > ABFP_R(1e-9) * largest)) {
        return ABF_ERR_NUMERIC; /* reference channel carries no signal */
    }
    for (size_t i = 0; i < n; i++) {
        const abfp_complex g = abfp_cmul(a[i], s->vectors[i * n + n - 1]);
        const abfp_complex ratio = abfp_scale(abfp_cmul(reference, g), ABFP_R(1) / energy);
        gains[i].re = (float)ratio.re;
        gains[i].im = (float)ratio.im;
    }
    return abfp_set_calibration(s, gains);
}
