/* ABF1 parser. Fields are read byte by byte: no alignment or endianness assumption. */
#include <float.h>
#include <math.h>
#include <string.h>

#include "abf_math.h"

static uint16_t read_u16(const uint8_t* p) {
    return (uint16_t)(p[0] | (uint16_t)(p[1] << 8));
}

static uint32_t read_u32(const uint8_t* p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint64_t read_u64(const uint8_t* p) {
    return (uint64_t)read_u32(p) | (uint64_t)read_u32(p + 4) << 32;
}

static float read_f32(const uint8_t* p) {
    const uint32_t bits = read_u32(p);
    float value;
    memcpy(&value, &bits, sizeof value);
    return value;
}

static double read_f64(const uint8_t* p) {
    const uint64_t bits = read_u64(p);
    double value;
    memcpy(&value, &bits, sizeof value);
    return value;
}

/* CRC-32 (IEEE 802.3), nibble table: 64 bytes of constants instead of 1 KiB. */
uint32_t abf_crc32(const uint8_t* data, size_t size) {
    static const uint32_t table[16] = {0x00000000u, 0x1DB71064u, 0x3B6E20C8u, 0x26D930ACu,
                                       0x76DC4190u, 0x6B6B51F4u, 0x4DB26158u, 0x5005713Cu,
                                       0xEDB88320u, 0xF00F9344u, 0xD6D6A3E8u, 0xCB61B38Cu,
                                       0x9B64C2B0u, 0x86D3D2D4u, 0xA00AE278u, 0xBDBDF21Cu};
    uint32_t crc = 0xFFFFFFFFu;
    if (data == NULL) {
        return 0;
    }
    for (size_t i = 0; i < size; i++) {
        crc ^= data[i];
        crc = (crc >> 4) ^ table[crc & 0x0Fu];
        crc = (crc >> 4) ^ table[crc & 0x0Fu];
    }
    return ~crc;
}

abf_status abf_frame_parse(const uint8_t* buffer, size_t size, abf_frame* frame) {
    if (buffer == NULL || frame == NULL) {
        return ABF_ERR_ARG;
    }
    if (size < ABF_FRAME_HEADER_SIZE || memcmp(buffer, "ABF1", 4) != 0 || buffer[4] != 1 ||
        read_u32(buffer + 60) != abf_crc32(buffer, 60) || buffer[5] > ABF_FORMAT_CF32) {
        return ABF_ERR_FRAME;
    }
    abf_frame f;
    f.format = (abf_sample_format)buffer[5];
    f.channels = read_u16(buffer + 6);
    f.samples = read_u32(buffer + 8);
    f.sequence = read_u32(buffer + 12);
    f.flags = read_u32(buffer + 16);
    f.timestamp_ns = read_u64(buffer + 24);
    f.sample_rate_hz = read_f64(buffer + 32);
    f.center_frequency_hz = read_f64(buffer + 40);
    f.scale = read_f32(buffer + 48);
    if (f.channels == 0 || f.channels > ABF_MAX_CHANNELS || f.samples == 0 ||
        f.samples > ABF_MAX_SAMPLES || !(f.sample_rate_hz > 0.0 && f.sample_rate_hz <= DBL_MAX) ||
        !(fabs(f.center_frequency_hz) <= DBL_MAX) || !(f.scale > 0.0f && f.scale <= FLT_MAX)) {
        /* written so that NaN fails every test */
        return ABF_ERR_FRAME;
    }
    /* at most 64 * 65536 * 8 = 32 MiB: cannot overflow a 32-bit size_t */
    f.payload_size = (size_t)f.channels * f.samples * (f.format == ABF_FORMAT_CI16 ? 4u : 8u);
    f.payload = buffer + ABF_FRAME_HEADER_SIZE;
    if (size != ABF_FRAME_HEADER_SIZE + f.payload_size ||
        read_u32(buffer + 52) != abf_crc32(f.payload, f.payload_size)) {
        return ABF_ERR_FRAME;
    }
    *frame = f;
    return ABF_OK;
}

abf_status abf_frame_samples(const abf_frame* frame, abf_cf32* out, size_t capacity) {
    if (frame == NULL || out == NULL || frame->payload == NULL) {
        return ABF_ERR_ARG;
    }
    const size_t count = (size_t)frame->channels * frame->samples;
    if (capacity < count) {
        return ABF_ERR_ARG;
    }
    const uint8_t* p = frame->payload;
    if (frame->format == ABF_FORMAT_CI16) {
        for (size_t i = 0; i < count; i++, p += 4) {
            out[i] = abf_make((float)(int16_t)read_u16(p) * frame->scale,
                              (float)(int16_t)read_u16(p + 2) * frame->scale);
        }
    } else {
        for (size_t i = 0; i < count; i++, p += 8) {
            out[i] = abf_make(read_f32(p) * frame->scale, read_f32(p + 4) * frame->scale);
        }
    }
    return ABF_OK;
}
