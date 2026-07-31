package com.ssafy.eyesonu.missingcase.messaging;

import java.time.Instant;
import java.util.UUID;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.stereotype.Component;

@Component
public class SearchTargetEventPublisher {

	public static final String EXCHANGE = "search.target.exchange";
	public static final String REALTIME_QUEUE = "search.target.realtime.queue";
	public static final String ROUTING_KEY = "search.target.updated";
	public static final String TARGET_UPDATED = "SEARCH_TARGET_UPDATED";
	public static final String TARGET_DISABLED = "SEARCH_TARGET_DISABLED";

	private final RabbitTemplate rabbitTemplate;

	public SearchTargetEventPublisher(RabbitTemplate rabbitTemplate) {
		this.rabbitTemplate = rabbitTemplate;
	}

	public void publishAfterCommit(String eventType, Long caseId, Instant updatedAt) {
		if (!TransactionSynchronizationManager.isSynchronizationActive()) {
			throw new IllegalStateException("Search target events must be published inside a transaction");
		}
		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				publish(eventType, caseId, updatedAt);
			}
		});
	}

	private void publish(String eventType, Long caseId, Instant updatedAt) {
		SearchTargetEvent event = new SearchTargetEvent(
				UUID.randomUUID().toString(), eventType, caseId, updatedAt, Instant.now());
		rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
			message.getMessageProperties().setDeliveryMode(
					org.springframework.amqp.core.MessageDeliveryMode.PERSISTENT);
			return message;
		});
	}
}
