package com.ssafy.eyesonu.missingcase.messaging;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.rabbit.config.RetryInterceptorBuilder;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.retry.RepublishMessageRecoverer;
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

	@Bean
	TopicExchange recordingAnalysisDeadLetterExchange() {
		return new TopicExchange(RecordingAnalysisJobPublisher.DEAD_LETTER_EXCHANGE, true, false);
	}

	@Bean
	Queue recordingAnalysisDeadLetterQueue() {
		return QueueBuilder.durable(RecordingAnalysisJobPublisher.DEAD_LETTER_QUEUE).build();
	}

	@Bean
	Binding recordingAnalysisDeadLetterBinding(
			@Qualifier("recordingAnalysisDeadLetterQueue") Queue recordingAnalysisDeadLetterQueue,
			@Qualifier("recordingAnalysisDeadLetterExchange") TopicExchange recordingAnalysisDeadLetterExchange) {
		return BindingBuilder.bind(recordingAnalysisDeadLetterQueue)
				.to(recordingAnalysisDeadLetterExchange)
				.with(RecordingAnalysisJobPublisher.DEAD_LETTER_ROUTING_KEY);
	}

	@Bean(name = "recordingAnalysisJobListenerContainerFactory")
	SimpleRabbitListenerContainerFactory recordingAnalysisJobListenerContainerFactory(
			ConnectionFactory connectionFactory,
			JacksonJsonMessageConverter rabbitMessageConverter,
			RabbitTemplate rabbitTemplate) {
		SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
		factory.setConnectionFactory(connectionFactory);
		factory.setMessageConverter(rabbitMessageConverter);
		factory.setContainerCustomizer(container -> container.setAdviceChain(
				RetryInterceptorBuilder.stateless()
						.maxRetries(2)
						.backOffOptions(1_000L, 2.0, 10_000L)
						.recoverer(new RepublishMessageRecoverer(
								rabbitTemplate,
								RecordingAnalysisJobPublisher.DEAD_LETTER_EXCHANGE,
								RecordingAnalysisJobPublisher.DEAD_LETTER_ROUTING_KEY))
						.build()));
		return factory;
	}
}
