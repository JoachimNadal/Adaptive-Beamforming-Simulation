/* Runs the pipeline over an ABF1 recording.
 *
 *   abf_replay input.abf output.cf32 phase1|noise|sqrt target_deg d_over_lambda [calibrated]
 *
 * Prints one JSON line per block with its processing time. The same file can be given to the
 * Python pipeline, which makes the two directly comparable. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "abf_pipeline.h"

enum { MAX_FRAME = ABF_FRAME_HEADER_SIZE + ABFP_N * 4096 * 8 };
static uint8_t buffer[MAX_FRAME];
static abf_cf32 samples[ABFP_N * 4096], output[4096];
static abfp_state state;

static uint32_t u32(const uint8_t* p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

int main(int argc, char** argv) {
    if (argc < 6) {
        fprintf(stderr,
                "usage: %s in.abf out.cf32 phase1|noise|sqrt target_deg d_over_lambda [cal]\n",
                argv[0]);
        return 2;
    }
    FILE* in = fopen(argv[1], "rb");
    FILE* out = fopen(argv[2], "wb");
    if (in == NULL || out == NULL) {
        fprintf(stderr, "cannot open files\n");
        return 1;
    }
    abfp_config c;
    memset(&c, 0, sizeof c);
    c.mode = strcmp(argv[3], "noise") == 0  ? ABFP_NOISE_LOADED
             : strcmp(argv[3], "sqrt") == 0 ? ABFP_NOISE_LOADED_SQRT
                                            : ABFP_PHASE1;
    c.target_rad = (float)(atof(argv[4]) * 3.14159265358979323846 / 180.0);
    c.d_over_lambda = (float)atof(argv[5]);
    c.covariance_beta = 0.5f;
    c.relative_loading = 1e-2f;
    c.noise_factor = 10.0f;
    c.max_interferers = 2;
    c.guard_rad = (float)(6.0 * 3.14159265358979323846 / 180.0);
    c.min_interferer_inr = 1.99526231f; /* 3 dB */
    c.derivative_constraint = 1;
    c.min_wng_ratio = 0.1f;

    int initialised = 0;
    int status = 0;
    while (fread(buffer, 1, ABF_FRAME_HEADER_SIZE, in) == ABF_FRAME_HEADER_SIZE) {
        /* sizes are only used to read; abf_frame_parse validates everything afterwards */
        const size_t channels = (size_t)buffer[6] | (size_t)buffer[7] << 8;
        const size_t count = u32(buffer + 8);
        const size_t width = buffer[5] == ABF_FORMAT_CI16 ? 4u : 8u;
        if (channels > ABFP_N || count > 4096) {
            fprintf(stderr, "frame too large\n");
            status = 1;
            break;
        }
        const size_t payload = channels * count * width;
        abf_frame frame;
        if (fread(buffer + ABF_FRAME_HEADER_SIZE, 1, payload, in) != payload ||
            abf_frame_parse(buffer, ABF_FRAME_HEADER_SIZE + payload, &frame) != ABF_OK ||
            abf_frame_samples(&frame, samples, sizeof samples / sizeof *samples) != ABF_OK) {
            fprintf(stderr, "invalid frame\n");
            status = 1;
            break;
        }
        if (!initialised) {
            c.num_antennas = frame.channels;
            abf_cf32 ones[ABFP_N];
            for (int i = 0; i < ABFP_N; i++) {
                ones[i].re = 1.0f;
                ones[i].im = 0.0f;
            }
            if (abfp_init(&state, &c) != ABF_OK ||
                (argc > 6 && abfp_set_calibration(&state, ones) != ABF_OK)) {
                fprintf(stderr, "invalid configuration\n");
                status = 1;
                break;
            }
            initialised = 1;
        } else if (frame.channels != c.num_antennas) {
            fprintf(stderr, "channel count changed\n");
            status = 1;
            break;
        }
        abfp_result r;
        const clock_t start = clock();
        if (abfp_process(&state, samples, frame.samples, frame.sequence, frame.flags, output, &r) !=
            ABF_OK) {
            status = 1;
            break;
        }
        const double us = 1e6 * (double)(clock() - start) / CLOCKS_PER_SEC;
        (void)fwrite(output, sizeof *output, frame.samples, out);
        printf("{\"seq\":%u,\"status\":%u,\"method\":%d,\"sources\":%d,\"wng\":%.9g,\"us\":%.1f,",
               (unsigned)frame.sequence, (unsigned)r.status, (int)r.method, (int)r.num_sources,
               (double)r.wng, us);
        printf("\"doas\":[");
        for (int i = 0; i < r.num_doas; i++) {
            printf("%s%.9g", i ? "," : "", (double)r.doas_rad[i]);
        }
        printf("],\"nulls\":[");
        for (int i = 0; i < r.num_nulls; i++) {
            printf("%s%.9g", i ? "," : "", (double)r.nulls_rad[i]);
        }
        printf("],\"weights\":[");
        for (int i = 0; i < c.num_antennas; i++) {
            printf("%s[%.9g,%.9g]", i ? "," : "", (double)state.weights[i].re,
                   (double)state.weights[i].im);
        }
        printf("]}\n");
    }
    (void)fclose(in);
    (void)fclose(out);
    return status;
}
