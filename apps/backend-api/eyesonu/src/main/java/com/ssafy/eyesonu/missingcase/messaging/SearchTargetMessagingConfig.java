package com.ssafy.eyesonu.missingcase.messaging;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.support.converter.JacksonJsonMessageConverter;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;

@Configuration
public class SearchTargetMessagingConfig {

	@Bean
	JsonMapper rabbitJsonMapper() {
		return JsonMapper.builder().findAndAddModules().build();
	}

	@Bean
	JacksonJsonMessageConverter rabbitMessageConverter(JsonMapper rabbitJsonMapper) {
		return new JacksonJsonMessageConverter(rabbitJsonMapper);
	}

	@Bean
	TopicExchange searchTargetExchange() {
		return new TopicExchange(SearchTargetEventPublisher.EXCHANGE, true, false);
	}

	@Bean
	Queue realtimeSearchTargetQueue() {
		return QueueBuilder.durable(SearchTargetEventPublisher.REALTIME_QUEUE).build();
	}

	@Bean
	Binding realtimeSearchTargetBinding(
			@Qualifier("realtimeSearchTargetQueue") Queue realtimeSearchTargetQueue,
			TopicExchange searchTargetExchange) {
		return BindingBuilder.bind(realtimeSearchTargetQueue)
				.to(searchTargetExchange)
				.with(SearchTargetEventPublisher.ROUTING_KEY);
	}

	@Bean
	Queue recordingAnalysisJobQueue() {
		return QueueBuilder.durable(RecordingAnalysisJobPublisher.QUEUE).build();
	}

	@Bean
	Binding recordingAnalysisJobBinding(
			@Qualifier("recordingAnalysisJobQueue") Queue recordingAnalysisJobQueue,
			TopicExchange searchTargetExchange) {
		return BindingBuilder.bind(recordingAnalysisJobQueue)
				.to(searchTargetExchange)
				.with(RecordingAnalysisJobPublisher.ROUTING_KEY);
	}
}
