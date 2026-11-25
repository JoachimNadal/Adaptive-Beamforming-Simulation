/* Live receiver for embedded Linux: UDP thread, lock-free ring, processing thread.
 *
 *   abf_receiver port phase1|noise|sqrt target_deg d_over_lambda [max_frames]
 *
 * Structure meant for a Raspberry Pi or Jetson. It has only been run on PCs and CI runners.
 * Exits after max_frames or two seconds without data, and prints a JSON summary. */
#include <arpa/inet.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include "abf_pipeline.h"
#include "abf_ring.h"

enum { SLOT = 65536, CAPACITY = 64, MAX_SAMPLES = 4096 };
static uint8_t storage[(size_t)SLOT * CAPACITY];
static uint32_t sizes[CAPACITY];
static abf_ring ring;
static atomic_int finished;
static int socket_fd;

static void* acquire(void* unused) {
    (void)unused;
    static uint8_t scratch[SLOT];
    for (;;) {
        uint8_t* slot = abf_ring_reserve(&ring);
        /* when full, the datagram is read into scratch so that the socket keeps draining */
        const ssize_t size = recv(socket_fd, slot != NULL ? slot : scratch, SLOT, 0);
        if (size <= 0) { /* timeout or error: end of stream */
            break;
        }
        if (slot != NULL) {
            abf_ring_commit(&ring, (uint32_t)size);
        }
    }
    atomic_store(&finished, 1);
    return NULL;
}

static double microseconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return 1e6 * (double)t.tv_sec + 1e-3 * (double)t.tv_nsec;
}

int main(int argc, char** argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: %s port phase1|noise|sqrt target_deg d_over_lambda [max_frames]\n",
                argv[0]);
        return 2;
    }
    const long max_frames = argc > 5 ? atol(argv[5]) : 0;
    socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    const int receive_buffer = 1 << 22;
    const struct timeval timeout = {2, 0};
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_RCVBUF, &receive_buffer, sizeof receive_buffer);
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_port = htons((uint16_t)atoi(argv[1]));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (socket_fd < 0 || bind(socket_fd, (struct sockaddr*)&address, sizeof address) != 0) {
        perror("socket");
        return 1;
    }
    abfp_config c;
    memset(&c, 0, sizeof c);
    c.mode = strcmp(argv[2], "noise") == 0  ? ABFP_NOISE_LOADED
             : strcmp(argv[2], "sqrt") == 0 ? ABFP_NOISE_LOADED_SQRT
                                            : ABFP_PHASE1;
    c.target_rad = (float)(atof(argv[3]) * 3.14159265358979323846 / 180.0);
    c.d_over_lambda = (float)atof(argv[4]);
    c.covariance_beta = 0.5f;
    c.relative_loading = 1e-2f;
    c.noise_factor = 10.0f;
    c.max_interferers = 2;
    c.guard_rad = 0.105f;
    c.min_interferer_inr = 2.0f;
    c.derivative_constraint = 1;
    c.min_wng_ratio = 0.1f;

    (void)abf_ring_init(&ring, storage, sizes, SLOT, CAPACITY);
    pthread_t thread;
    if (pthread_create(&thread, NULL, acquire, NULL) != 0) {
        return 1;
    }
    printf("{\"listening\":%s}\n", argv[1]);
    (void)fflush(stdout);

    static abfp_state state;
    static abf_cf32 x[(size_t)ABFP_N * MAX_SAMPLES], y[MAX_SAMPLES];
    long processed = 0, rejected = 0, gaps = 0;
    double total_us = 0.0, worst_us = 0.0;
    abfp_result r;
    memset(&r, 0, sizeof r);
    while (max_frames == 0 || processed < max_frames) {
        uint32_t size;
        const uint8_t* slot = abf_ring_peek(&ring, &size);
        if (slot == NULL) {
            if (atomic_load(&finished)) {
                break;
            }
            const struct timespec pause = {0, 100000}; /* 0.1 ms */
            (void)nanosleep(&pause, NULL);
            continue;
        }
        abf_frame frame;
        const int valid = abf_frame_parse(slot, size, &frame) == ABF_OK &&
                          frame.channels <= ABFP_N && frame.samples <= MAX_SAMPLES &&
                          abf_frame_samples(&frame, x, sizeof x / sizeof *x) == ABF_OK;
        if (valid && processed == 0) {
            c.num_antennas = frame.channels;
            if (abfp_init(&state, &c) != ABF_OK) {
                fprintf(stderr, "invalid configuration\n");
                return 1;
            }
        }
        if (valid && frame.channels == c.num_antennas) {
            const double start = microseconds();
            (void)abfp_process(&state, x, frame.samples, frame.sequence, frame.flags, y, &r);
            const double us = microseconds() - start;
            total_us += us;
            worst_us = us > worst_us ? us : worst_us;
            gaps += (r.status & ABFP_SEQUENCE_GAP) != 0;
            processed++;
        } else {
            rejected++;
        }
        abf_ring_release(&ring);
    }
    printf(
        "{\"processed\":%ld,\"rejected\":%ld,\"gaps\":%ld,\"dropped\":%u,\"mean_us\":%.2f,"
        "\"worst_us\":%.2f,\"sources\":%d,\"wng\":%.4f}\n",
        processed, rejected, gaps, (unsigned)abf_ring_dropped(&ring),
        processed ? total_us / (double)processed : 0.0, worst_us, (int)r.num_sources,
        (double)r.wng);
    (void)fflush(stdout);
    (void)close(socket_fd);
    return 0;
}
