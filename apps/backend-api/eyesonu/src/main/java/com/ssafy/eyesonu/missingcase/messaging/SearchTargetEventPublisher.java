package com.ssafy.eyesonu.missingcase.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.time.Instant;
import java.util.UUID;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class SearchTargetEventPublisher {

	public static final String EXCHANGE = "search.target.exchange";
	public static final String REALTIME_QUEUE = "search.target.realtime.queue";
	public static final String ROUTING_KEY = "search.target.updated";
	public static final String TARGET_UPDATED = "SEARCH_TARGET_UPDATED";
	public static final String TARGET_DISABLED = "SEARCH_TARGET_DISABLED";

	private final RabbitTemplate rabbitTemplate;
	private final ObjectMapper objectMapper = JsonMapper.builder().findAndAddModules().build();

	public SearchTargetEventPublisher(RabbitTemplate rabbitTemplate) {
		this.rabbitTemplate = rabbitTemplate;
	}

	public void publish(String eventType, Long caseId, Instant updatedAt) {
		SearchTargetEvent event = new SearchTargetEvent(
				UUID.randomUUID().toString(), eventType, caseId, updatedAt, Instant.now());
		try {
			rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, objectMapper.writeValueAsString(event), message -> {
				message.getMessageProperties().setContentType("application/json");
				message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
				return message;
			});
		} catch (JsonProcessingException exception) {
			throw new IllegalStateException("Search target event could not be serialized", exception);
		}
	}
}
