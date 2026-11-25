/* Adaptive receive pipeline in portable C99, on top of the Phase 1 core (embedded/core).
 *
 * Three modes:
 *   ABFP_PHASE1       same algorithm as embedded/common/pipeline.py (LCMV, MDL, root-MUSIC)
 *   ABFP_NOISE_LOADED MVDR with loading proportional to the estimated noise (research study 1)
 *   ABFP_NOISE_LOADED_SQRT  the same, computed on the triangular factor of the covariance:
 *                     single precision then suffices up to 80 dB of interference
 *
 * No heap, no globals, reentrant. All working memory is inside abfp_state, so stack use is small
 * and known. Input and output are float32; the statistics use abfp_real, which is float by
 * default and double when ABFP_DOUBLE is defined (library and caller must agree).
 */
#ifndef ABF_PIPELINE_H
#define ABF_PIPELINE_H

#include <stddef.h>
#include <stdint.h>

#include "abf.h"

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) && defined(ABFP_SHARED)
#define ABFP_API __declspec(dllexport)
#else
#define ABFP_API
#endif

#ifdef ABFP_DOUBLE
typedef double abfp_real;
#else
typedef float abfp_real;
#endif

typedef struct {
    abfp_real re;
    abfp_real im;
} abfp_complex;

#define ABFP_N ABF_MAX_ANTENNAS

typedef enum { ABFP_PHASE1 = 0, ABFP_NOISE_LOADED = 1, ABFP_NOISE_LOADED_SQRT = 2 } abfp_mode;
typedef enum {
    ABFP_METHOD_HELD = 0,
    ABFP_METHOD_LCMV = 1,
    ABFP_METHOD_MVDR = 2,
    ABFP_METHOD_DAS = 3
} abfp_method;

/* Bits 0 to 9: same order and meaning as Status in embedded/common/pipeline.py. */
enum {
    ABFP_UNCALIBRATED = 1 << 0,
    ABFP_SEQUENCE_GAP = 1 << 1,
    ABFP_ADC_OVERFLOW = 1 << 2,
    ABFP_CLOCK_UNLOCKED = 1 << 3,
    ABFP_INVALID_DATA = 1 << 4,
    ABFP_TOO_MANY_SOURCES = 1 << 5,
    ABFP_NULLS_DROPPED = 1 << 6,
    ABFP_FALLBACK_MVDR = 1 << 7,
    ABFP_FALLBACK_DAS = 1 << 8,
    ABFP_WEIGHTS_HELD = 1 << 9,
    /* Not in Python: the noise eigenvalues of the covariance are below what abfp_real resolves.
     * Use double precision or the square-root mode. */
    ABFP_PRECISION_LIMITED = 1 << 10
};

typedef struct {
    int32_t num_antennas; /* 2 to 16 */
    int32_t mode;         /* abfp_mode */
    float d_over_lambda;  /* at most 0.5005 */
    float target_rad;
    float covariance_beta;  /* [0, 1) */
    float relative_loading; /* Phase 1 mode, relative to tr(R) / n */
    float noise_factor;     /* noise-loaded mode, multiple of the noise power */
    int32_t max_interferers;
    float guard_rad;
    float min_interferer_inr; /* linear */
    int32_t derivative_constraint;
    float min_wng_ratio;
} abfp_config;

typedef struct {
    uint32_t status;
    int32_t method; /* abfp_method */
    int32_t num_sources;
    int32_t num_doas;
    int32_t num_nulls;
    float doas_rad[ABFP_N];
    float nulls_rad[ABFP_N];
    float wng;
    float noise_power;
} abfp_result;

/* Private working memory. Declared here so that the caller can place it (static, TCM, ...). */
typedef struct {
    abfp_config config;
    abfp_complex a_target[ABFP_N];
    abf_cf32 weights[ABFP_N];
    abf_cf32 calibration_inverse[ABFP_N];
    int32_t calibrated;
    int32_t has_sequence;
    uint32_t last_sequence;
    abfp_real weight_sum;
    abfp_real weight_squared;
    abfp_complex r_sum[ABFP_N * ABFP_N];
    abfp_complex r[ABFP_N * ABFP_N];
    abfp_complex work[ABFP_N * ABFP_N];
    abfp_complex vectors[ABFP_N * ABFP_N];
    abfp_complex constraints[ABFP_N * ABFP_N];
    abfp_complex solved[ABFP_N * ABFP_N];
    abfp_real values[ABFP_N];
} abfp_state;

ABFP_API abf_status abfp_init(abfp_state* state, const abfp_config* config);

/* Known channel gains; resets the covariance. */
ABFP_API abf_status abfp_set_calibration(abfp_state* state, const abf_cf32* gains);

/* Estimates the gains from a block dominated by one source of known direction. */
ABFP_API abf_status abfp_calibrate(abfp_state* state, const abf_cf32* x, size_t k,
                                   float source_rad);

/* One block: x holds k snapshots of n antennas, sample by sample; y receives k samples.
 * x may be modified (calibration is applied in place). Bad data never returns an error: it is
 * reported in result->status. ABF_ERR_ARG is returned for invalid pointers or sizes only. */
ABFP_API abf_status abfp_process(abfp_state* state, abf_cf32* x, size_t k, uint32_t sequence,
                                 uint32_t frame_flags, abf_cf32* y, abfp_result* result);

ABFP_API size_t abfp_state_size(void);

/* ---- numerical kernels, exposed for tests -------------------------------------------- */

/* Eigenvalues (ascending) and eigenvectors (columns) of a Hermitian matrix, cyclic Jacobi.
 * a is destroyed. Returns ABF_ERR_NUMERIC if it does not converge. */
ABFP_API abf_status abfp_eigh(abfp_complex* a, size_t n, abfp_real* values, abfp_complex* vectors);

/* Minimum description length on ascending eigenvalues. */
ABFP_API int abfp_mdl(const abfp_real* values, size_t n, abfp_real snapshots);

/* Angles (ascending, radians) from the n - sources noise eigenvectors stored in the first
 * columns of vectors. Returns the number of angles. */
ABFP_API int abfp_root_music(const abfp_complex* vectors, size_t n, size_t sources,
                             float d_over_lambda, float* angles);

/* Roots of sum c[k] z^(degree - k) by Aberth iterations, double precision, degree <= 30. */
ABFP_API int abfp_polynomial_roots(const double* c_re, const double* c_im, int degree, double* z_re,
                                   double* z_im);

#ifdef __cplusplus
}
#endif

#endif
