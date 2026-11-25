/* Ring buffer: limits, then two real threads. */
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <string.h>

#include "abf_ring.h"

enum { SLOT = 64, CAPACITY = 8, MESSAGES = 200000 };
static uint8_t storage[SLOT * CAPACITY];
static uint32_t sizes[CAPACITY];
static abf_ring ring;
static int failures = 0;

#define CHECK(condition)                                   \
    do {                                                   \
        if (!(condition)) {                                \
            printf("FAIL %d: %s\n", __LINE__, #condition); \
            failures++;                                    \
        }                                                  \
    } while (0)

static void* producer(void* unused) {
    (void)unused;
    for (uint32_t i = 0; i < MESSAGES;) {
        uint8_t* slot = abf_ring_reserve(&ring);
        if (slot == NULL) {
            sched_yield(); /* the test wants every message; real acquisition would drop */
            continue;
        }
        memset(slot, (int)(i & 0xFFu), SLOT);
        memcpy(slot, &i, sizeof i);
        abf_ring_commit(&ring, SLOT - (i % 7u));
        i++;
    }
    return NULL;
}

int main(void) {
    uint32_t size = 0;
    CHECK(!abf_ring_init(&ring, storage, sizes, SLOT, 6)); /* not a power of two */
    CHECK(abf_ring_init(&ring, storage, sizes, SLOT, CAPACITY));
    CHECK(abf_ring_peek(&ring, &size) == NULL);
    for (int i = 0; i < CAPACITY; i++) {
        CHECK(abf_ring_reserve(&ring) != NULL);
        abf_ring_commit(&ring, (uint32_t)i);
    }
    CHECK(abf_ring_reserve(&ring) == NULL && abf_ring_dropped(&ring) == 1);
    CHECK(abf_ring_peek(&ring, &size) != NULL && size == 0);
    abf_ring_release(&ring);
    CHECK(abf_ring_reserve(&ring) != NULL);

    CHECK(abf_ring_init(&ring, storage, sizes, SLOT, CAPACITY));
    pthread_t thread;
    CHECK(pthread_create(&thread, NULL, producer, NULL) == 0);
    for (uint32_t expected = 0; expected < MESSAGES;) {
        const uint8_t* slot = abf_ring_peek(&ring, &size);
        if (slot == NULL) {
            sched_yield();
            continue;
        }
        uint32_t value;
        memcpy(&value, slot, sizeof value);
        if (value != expected || size != SLOT - (expected % 7u) ||
            slot[SLOT - 1] != (uint8_t)(expected & 0xFFu)) {
            failures++;
        }
        abf_ring_release(&ring);
        expected++;
    }
    CHECK(pthread_join(thread, NULL) == 0);
    printf(failures == 0 ? "ring tests passed\n" : "%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
