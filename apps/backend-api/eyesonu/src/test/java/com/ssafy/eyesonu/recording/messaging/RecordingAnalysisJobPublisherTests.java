package com.ssafy.eyesonu.recording.messaging;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobPublisherTests {

    @Mock
    private RabbitTemplate rabbitTemplate;

    @AfterEach
    void clearSynchronization() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    @Test
    void requiresTransactionSynchronization() {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(rabbitTemplate);

        assertThrows(IllegalStateException.class, () -> publisher.publishAfterCommit(5001L, 101L));
    }

    @Test
    void publishesOnlyAfterCommit() {
        TransactionSynchronizationManager.initSynchronization();
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(rabbitTemplate);

        publisher.publishAfterCommit(5001L, 101L);

        org.junit.jupiter.api.Assertions.assertTrue(
                TransactionSynchronizationManager.getSynchronizations().stream().findFirst().isPresent());
        for (TransactionSynchronization synchronization
                : TransactionSynchronizationManager.getSynchronizations()) {
            synchronization.afterCommit();
        }

        verify(rabbitTemplate).convertAndSend(
                eq(RecordingAnalysisJobPublisher.EXCHANGE),
                eq(RecordingAnalysisJobPublisher.ROUTING_KEY),
                any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class));
    }
}
