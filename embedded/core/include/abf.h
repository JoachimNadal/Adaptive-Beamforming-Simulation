/* Adaptive beamforming core: portable C99, single precision, no heap, no globals.
 *
 * It implements the parts that must run at sample or block rate. The Python package is the
 * reference: tests/test_c_core.py checks every function against it.
 *
 * Conventions (identical to the Python side)
 *   - a[m] = exp(-j 2 pi m (d / lambda) sin(theta)), angles in radians from broadside
 *   - output y = w^H x
 *   - blocks are stored sample by sample: x[k * n + m] is antenna m of snapshot k,
 *     the order in which a multichannel ADC delivers data
 *   - matrices are n * n, row-major and Hermitian
 *
 * All functions are reentrant and take caller-owned memory. Functions that can fail return
 * abf_status and leave their outputs untouched on error unless stated otherwise.
 */
#ifndef ABF_H
#define ABF_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) && defined(ABF_SHARED)
#define ABF_API __declspec(dllexport)
#else
#define ABF_API
#endif

#define ABF_MAX_ANTENNAS      16
#define ABF_MAX_CHANNELS      64
#define ABF_MAX_SAMPLES       65536u
#define ABF_FRAME_HEADER_SIZE 64

typedef struct {
    float re;
    float im;
} abf_cf32;

typedef enum {
    ABF_OK = 0,
    ABF_ERR_ARG = 1,        /* null pointer or size out of range */
    ABF_ERR_NOT_POSDEF = 2, /* covariance not positive definite: increase the loading */
    ABF_ERR_NUMERIC = 3,    /* NaN, infinity or vanishing normalisation */
    ABF_ERR_FRAME = 4       /* malformed frame */
} abf_status;

/* ---- steering and application ------------------------------------------------------ */

ABF_API abf_status abf_steering_ula(float theta, float d_over_lambda, size_t n, abf_cf32* a);

/* y[k] = sum_m conj(w[m]) x[k n + m] */
ABF_API abf_status abf_apply_weights(const abf_cf32* w, const abf_cf32* x, size_t n, size_t k,
                                     abf_cf32* y);

/* ---- covariance -------------------------------------------------------------------- */

/* R <- beta R + (1 - beta) (1/k) sum x x^H. beta = 0 ignores the previous content of R. */
ABF_API abf_status abf_covariance_update(abf_cf32* r, const abf_cf32* x, size_t n, size_t k,
                                         float beta);

/* ---- closed-form weights ------------------------------------------------------------ */

ABF_API abf_status abf_das_weights(const abf_cf32* a, size_t n, abf_cf32* w);

/* MVDR with loading relative_loading * tr(R) / n, solved by Cholesky. */
ABF_API abf_status abf_mvdr_weights(const abf_cf32* r, const abf_cf32* a, size_t n,
                                    float relative_loading, abf_cf32* w);

/* |w^H a|^2 / ||w||^2, or 0 for a null weight vector. */
ABF_API float abf_white_noise_gain(const abf_cf32* w, const abf_cf32* a, size_t n);

/* ---- recursive weights -------------------------------------------------------------- */

/* Each returns the a-priori error e = d - w^H x through *error (may be NULL). */
ABF_API abf_status abf_lms_step(abf_cf32* w, const abf_cf32* x, abf_cf32 d, size_t n, float mu,
                                abf_cf32* error);
ABF_API abf_status abf_nlms_step(abf_cf32* w, const abf_cf32* x, abf_cf32 d, size_t n, float mu,
                                 float eps, abf_cf32* error);

/* P must be initialised to identity / delta. It is kept exactly Hermitian: only the upper
 * triangle is computed. Freeze the recursion when the input vanishes (P would overflow). */
ABF_API abf_status abf_rls_step(abf_cf32* w, abf_cf32* p, const abf_cf32* x, abf_cf32 d, size_t n,
                                float forgetting, abf_cf32* error);

/* ---- ABF1 frames -------------------------------------------------------------------- */

typedef enum { ABF_FORMAT_CI16 = 0, ABF_FORMAT_CF32 = 1 } abf_sample_format;

enum {
    ABF_FLAG_ADC_OVERFLOW = 1,
    ABF_FLAG_CLOCK_UNLOCKED = 2,
    ABF_FLAG_CALIBRATION_ON = 4,
    ABF_FLAG_GAIN_CHANGED = 8
};

typedef struct {
    abf_sample_format format;
    uint16_t channels;
    uint32_t samples;
    uint32_t sequence;
    uint32_t flags;
    uint64_t timestamp_ns;
    double sample_rate_hz;
    double center_frequency_hz;
    float scale;
    const uint8_t* payload; /* points into the parsed buffer */
    size_t payload_size;
} abf_frame;

ABF_API uint32_t abf_crc32(const uint8_t* data, size_t size);

/* Validates everything, including both CRCs, before filling *frame. */
ABF_API abf_status abf_frame_parse(const uint8_t* buffer, size_t size, abf_frame* frame);

/* Converts the payload to scaled cf32, channels * samples values in block order. */
ABF_API abf_status abf_frame_samples(const abf_frame* frame, abf_cf32* out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
