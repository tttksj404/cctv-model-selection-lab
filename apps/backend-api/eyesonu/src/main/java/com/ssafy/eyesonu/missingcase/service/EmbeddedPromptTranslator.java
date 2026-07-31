package com.ssafy.eyesonu.missingcase.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/** 임베디드용 프롬프트를 한글에서 영어로 변환하는 임시 무료 번역기. */
@Component
public class EmbeddedPromptTranslator {

	private static final String ENDPOINT = "https://api.mymemory.translated.net/get";
	private static final Duration TIMEOUT = Duration.ofSeconds(3);
	private static final Pattern UPPER_MARKER = Pattern.compile("상의|상 의|셔츠|티셔츠|후드|맨투맨|패딩|자켓|재킷|코트|바람막이");
	private static final Pattern LOWER_MARKER = Pattern.compile("하의|하 의|바지|청바지|치마|반바지|슬랙스");
	private static final Pattern SLEEVE_MARKER = Pattern.compile("반팔|긴팔");

	private final HttpClient httpClient;
	private final ObjectMapper objectMapper;
	private final Map<String, String> cache = new ConcurrentHashMap<>();

	public EmbeddedPromptTranslator() {
		this(HttpClient.newBuilder().connectTimeout(TIMEOUT).build(), new ObjectMapper());
	}

	EmbeddedPromptTranslator(HttpClient httpClient, ObjectMapper objectMapper) {
		this.httpClient = httpClient;
		this.objectMapper = objectMapper;
	}

	public String translate(String source) {
		if (source == null || source.isBlank()) return null;
		String normalized = source.trim();
		if (!containsKorean(normalized)) return normalized;
		String cached = cache.get(normalized);
		if (cached != null) return cached;

		try {
			String translatedResult = translateOrderedClothing(normalized);
			cache.put(normalized, translatedResult);
			return translatedResult;
		} catch (Exception ignored) {
			// 번역 실패 시 한국어 원문을 임베디드 장치로 전달하지 않는다.
			return null;
		}
	}

	private String translateOrderedClothing(String source) throws Exception {
		String gender = source.contains("남") ? "a man" : source.contains("여") ? "a woman" : "a person";
		Matcher upperMatcher = UPPER_MARKER.matcher(source);
		Matcher lowerMatcher = LOWER_MARKER.matcher(source);
		Matcher sleeveMatcher = SLEEVE_MARKER.matcher(source);
		if (!upperMatcher.find() || !lowerMatcher.find() || !sleeveMatcher.find()) {
			return translateText(source);
		}

		String upperColorSource = source.substring(lastDelimiter(source, 0, sleeveMatcher.start()) + 1, sleeveMatcher.start()).trim();
		String lowerColorSource = source.substring(lastDelimiter(source, upperMatcher.end(), lowerMatcher.start()) + 1, lowerMatcher.start()).trim();
		String upperColor = cleanColor(translateText(upperColorSource));
		String lowerColor = cleanColor(translateText(lowerColorSource));
		String sleeve = source.substring(sleeveMatcher.start(), sleeveMatcher.end()).equals("반팔")
				? "short sleeve" : "long sleeve";
		return gender + " wearing a " + upperColor + " " + sleeve + " top and " + lowerColor + " pants";
	}

	private int lastDelimiter(String source, int start, int end) {
		int delimiter = start - 1;
		for (int i = start; i < end; i++) {
			char ch = source.charAt(i);
			if (ch == ',' || ch == '와' || ch == '과' || ch == '및') delimiter = i;
		}
		return delimiter;
	}

	private String cleanColor(String translated) {
		return translated.replaceAll("(?i)\\b(color|colour|색상)\\b", "").trim();
	}

	private String translateText(String source) throws Exception {
		String query = URLEncoder.encode(source, StandardCharsets.UTF_8);
		HttpRequest request = HttpRequest.newBuilder()
				.uri(URI.create(ENDPOINT + "?q=" + query + "&langpair=ko|en"))
				.timeout(TIMEOUT)
				.header("Accept", "application/json")
				.GET()
				.build();
		HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
		if (response.statusCode() / 100 != 2) return source;
		JsonNode translated = objectMapper.readTree(response.body()).path("responseData").path("translatedText");
		String result = translated.asText().trim();
		return result.isEmpty() ? source : result;
	}

	private boolean containsKorean(String value) {
		return value.codePoints().anyMatch(codePoint ->
				(codePoint >= 0xAC00 && codePoint <= 0xD7A3)
						|| (codePoint >= 0x1100 && codePoint <= 0x11FF));
	}
}
