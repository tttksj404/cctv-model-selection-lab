package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class RecordingObjectKeyFactoryTests {

    @Test
    void createsUtcTimestampAndUuidKeyWithSixFractionalDigits() {
        String result = new RecordingObjectKeyFactory().create(
                "camera-01",
                Instant.parse("2026-08-04T03:15:30.123456Z"),
                "550e8400-e29b-41d4-a716-446655440000");

        assertEquals(
                "recordings/camera-01/2026/08/04/"
                        + "20260804T031530123456Z_550e8400-e29b-41d4-a716-446655440000.mp4",
                result);
    }

    @Test
    void padsMillisecondsToSixFractionalDigits() {
        String result = new RecordingObjectKeyFactory().create(
                "camera-01",
                Instant.parse("2026-08-04T03:15:30.123Z"),
                "550e8400-e29b-41d4-a716-446655440000");

        assertEquals(
                "recordings/camera-01/2026/08/04/"
                        + "20260804T031530123000Z_550e8400-e29b-41d4-a716-446655440000.mp4",
                result);
    }

    @Test
    void usesUtcDateAndPadsWholeSecondsAtDateBoundary() {
        String result = new RecordingObjectKeyFactory().create(
                "camera-01",
                Instant.parse("2026-08-03T15:00:00Z"),
                "550e8400-e29b-41d4-a716-446655440000");

        assertEquals(
                "recordings/camera-01/2026/08/03/"
                        + "20260803T150000000000Z_550e8400-e29b-41d4-a716-446655440000.mp4",
                result);
    }
}
