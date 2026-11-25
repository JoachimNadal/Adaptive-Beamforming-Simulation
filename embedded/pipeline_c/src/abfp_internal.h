/* Functions shared between translation units, not part of the public interface. */
#ifndef ABFP_INTERNAL_H
#define ABFP_INTERNAL_H

#include "abfp_math.h"

/* T <- factor of beta T^H T + (1 - beta) / k sum x x^H. Returns 0 if the result is not finite. */
int abfp_sqrt_update(abfp_complex* T, size_t n, const abf_cf32* x, size_t k, abfp_real beta);

/* Eigenvalues of T^H T, ascending. */
abf_status abfp_sqrt_eigenvalues(const abfp_complex* T, size_t n, abfp_complex* work,
                                 abfp_real* values);

/* MVDR weights of T^H T + loading I, with unit gain toward a. Returns 0 if singular. */
int abfp_sqrt_mvdr(const abfp_complex* T, size_t n, abfp_real loading, const abfp_complex* a,
                   abfp_complex* work, abfp_complex* w);

#endif
