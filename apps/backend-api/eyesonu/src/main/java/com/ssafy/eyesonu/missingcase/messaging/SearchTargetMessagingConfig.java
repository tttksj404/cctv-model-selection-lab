package com.ssafy.eyesonu.missingcase.messaging;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SearchTargetMessagingConfig {

	@Bean
	TopicExchange searchTargetExchange() {
		return new TopicExchange(SearchTargetEventPublisher.EXCHANGE, true, false);
	}

	@Bean
	Queue realtimeSearchTargetQueue() {
		return QueueBuilder.durable(SearchTargetEventPublisher.REALTIME_QUEUE).build();
	}

	@Bean
	Binding realtimeSearchTargetBinding(Queue realtimeSearchTargetQueue, TopicExchange searchTargetExchange) {
		return BindingBuilder.bind(realtimeSearchTargetQueue)
				.to(searchTargetExchange)
				.with(SearchTargetEventPublisher.ROUTING_KEY);
	}
}
