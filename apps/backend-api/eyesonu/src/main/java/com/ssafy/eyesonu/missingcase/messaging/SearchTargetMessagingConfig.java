package com.ssafy.eyesonu.missingcase.messaging;

import com.ssafy.eyesonu.recording.config.RecordingAnalysisProperties;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Declarable;
import org.springframework.amqp.core.Declarables;
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
import java.util.ArrayList;
import java.util.List;

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
		return QueueBuilder.durable(RecordingAnalysisJobPublisher.QUEUE)
				.withArgument("x-dead-letter-exchange", RecordingAnalysisJobPublisher.DEAD_LETTER_EXCHANGE)
				.withArgument("x-dead-letter-routing-key", RecordingAnalysisJobPublisher.DEAD_LETTER_ROUTING_KEY)
				.build();
	}

	@Bean
	TopicExchange recordingAnalysisJobExchange() {
		return new TopicExchange(RecordingAnalysisJobPublisher.EXCHANGE, true, false);
	}

	@Bean
	Binding recordingAnalysisJobBinding(
			@Qualifier("recordingAnalysisJobQueue") Queue recordingAnalysisJobQueue,
			@Qualifier("recordingAnalysisJobExchange") TopicExchange recordingAnalysisJobExchange) {
		return BindingBuilder.bind(recordingAnalysisJobQueue)
				.to(recordingAnalysisJobExchange)
				.with(RecordingAnalysisJobPublisher.ROUTING_KEY);
	}

	@Bean
	TopicExchange recordingAnalysisRetryExchange() {
		return new TopicExchange(RecordingAnalysisJobPublisher.RETRY_EXCHANGE, true, false);
	}

	@Bean
	Declarables recordingAnalysisRetryTopology(
			@Qualifier("recordingAnalysisRetryExchange") TopicExchange recordingAnalysisRetryExchange,
			RecordingAnalysisProperties properties) {
		List<Declarable> declarations = new ArrayList<>();
		for (Integer delaySeconds : properties.getRetryDelayBucketsSeconds()) {
			Queue retryQueue = retryQueue(delaySeconds);
			declarations.add(retryQueue);
			declarations.add(retryBinding(retryQueue, recordingAnalysisRetryExchange, delaySeconds));
		}
		return new Declarables(declarations);
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
			RabbitTemplate rabbitTemplate,
			RecordingAnalysisProperties properties) {
		RecordingAnalysisProperties.BackendConsumer.Retry retry =
				properties.getBackendConsumer().getRetry();
		SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
		factory.setConnectionFactory(connectionFactory);
		factory.setMessageConverter(rabbitMessageConverter);
		factory.setContainerCustomizer(container -> container.setAdviceChain(
				RetryInterceptorBuilder.stateless()
						.maxRetries(retry.getMaxAttempts())
						.backOffOptions(
								retry.getInitialIntervalMs(),
								retry.getMultiplier(),
								retry.getMaxIntervalMs())
						.recoverer(new RepublishMessageRecoverer(
								rabbitTemplate,
								RecordingAnalysisJobPublisher.DEAD_LETTER_EXCHANGE,
								RecordingAnalysisJobPublisher.DEAD_LETTER_ROUTING_KEY))
						.build()));
		return factory;
	}

	private Queue retryQueue(int delaySeconds) {
		return QueueBuilder.durable(RecordingAnalysisJobPublisher.retryQueueName(delaySeconds))
				.withArgument("x-message-ttl", delaySeconds * 1_000)
				.withArgument("x-dead-letter-exchange", RecordingAnalysisJobPublisher.EXCHANGE)
				.withArgument("x-dead-letter-routing-key", RecordingAnalysisJobPublisher.ROUTING_KEY)
				.build();
	}

	private Binding retryBinding(Queue retryQueue, TopicExchange retryExchange, int delaySeconds) {
		return BindingBuilder.bind(retryQueue)
				.to(retryExchange)
				.with(RecordingAnalysisJobPublisher.retryRoutingKey(delaySeconds));
	}
}
