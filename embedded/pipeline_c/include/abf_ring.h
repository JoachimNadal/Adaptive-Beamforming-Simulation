/* Single-producer single-consumer ring of fixed-size frames, lock-free, C11.
 *
 * Intended use: an acquisition thread or DMA interrupt writes frames, a processing thread reads
 * them. Neither ever waits for the other. When the ring is full the producer drops the new frame
 * and counts it, so that acquisition is never blocked by slow processing.
 *
 * head and tail are free-running counters; the capacity must be a power of two.
 */
#ifndef ABF_RING_H
#define ABF_RING_H

#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t* storage; /* capacity * slot_size bytes, owned by the caller */
    uint32_t* sizes;  /* capacity entries */
    size_t slot_size;
    uint32_t capacity;
    /* on separate cache lines: each is written by one side only */
    _Alignas(64) _Atomic uint32_t head; /* producer */
    _Alignas(64) _Atomic uint32_t tail; /* consumer */
    _Alignas(64) _Atomic uint32_t dropped;
} abf_ring;

static inline int abf_ring_init(abf_ring* r, uint8_t* storage, uint32_t* sizes, size_t slot_size,
                                uint32_t capacity) {
    if (r == NULL || storage == NULL || sizes == NULL || slot_size == 0 || capacity == 0 ||
        (capacity & (capacity - 1u)) != 0) {
        return 0;
    }
    r->storage = storage;
    r->sizes = sizes;
    r->slot_size = slot_size;
    r->capacity = capacity;
    atomic_init(&r->head, 0);
    atomic_init(&r->tail, 0);
    atomic_init(&r->dropped, 0);
    return 1;
}

/* Producer: slot to fill, or NULL if the ring is full (the frame is counted as dropped). */
static inline uint8_t* abf_ring_reserve(abf_ring* r) {
    const uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    const uint32_t tail = atomic_load_explicit(&r->tail, memory_order_acquire);
    if (head - tail >= r->capacity) {
        atomic_fetch_add_explicit(&r->dropped, 1, memory_order_relaxed);
        return NULL;
    }
    return r->storage + (size_t)(head & (r->capacity - 1u)) * r->slot_size;
}

/* Producer: publishes the slot obtained from abf_ring_reserve. */
static inline void abf_ring_commit(abf_ring* r, uint32_t size) {
    const uint32_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    r->sizes[head & (r->capacity - 1u)] = size;
    atomic_store_explicit(&r->head, head + 1u, memory_order_release);
}

/* Consumer: oldest frame, or NULL if the ring is empty. */
static inline const uint8_t* abf_ring_peek(abf_ring* r, uint32_t* size) {
    const uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    const uint32_t head = atomic_load_explicit(&r->head, memory_order_acquire);
    if (head == tail) {
        return NULL;
    }
    *size = r->sizes[tail & (r->capacity - 1u)];
    return r->storage + (size_t)(tail & (r->capacity - 1u)) * r->slot_size;
}

/* Consumer: releases the frame obtained from abf_ring_peek. */
static inline void abf_ring_release(abf_ring* r) {
    const uint32_t tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    atomic_store_explicit(&r->tail, tail + 1u, memory_order_release);
}

static inline uint32_t abf_ring_dropped(abf_ring* r) {
    return atomic_load_explicit(&r->dropped, memory_order_relaxed);
}

#endif
