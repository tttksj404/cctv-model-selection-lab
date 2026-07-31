package com.ssafy.eyesonu.missingcase.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/** 실시간 검색용 프롬프트를 정해진 영어 색상·상의 형태로 정규화한다. */
@Component
public class RealtimePromptNormalizer {

	private static final Pattern COLOR_PATTERN = Pattern.compile(
			"black|blue|brown|green|gray|orange|pink|purple|red|white|yellow",
			Pattern.CASE_INSENSITIVE);

	public String normalize(String source) {
		if (source == null || source.isBlank()) return "";
		String value = source.trim().toLowerCase(Locale.ROOT);
		String gender = value.contains("woman") || value.contains("female") || value.contains("여성") || value.contains("여자")
				? "a woman" : value.contains("man") || value.contains("male") || value.contains("남성") || value.contains("남자")
						? "a man" : "a person";
		List<ColorMatch> colors = findColors(value);
		String upperColor = colors.size() >= 1 ? colors.getFirst().color() : "";
		String lowerColor = colors.size() >= 2 ? colors.get(1).color() : "";
		String sleeve = value.contains("short sleeve") || value.contains("short-sleeve") || value.contains("반팔")
				? "short sleeve" : value.contains("long sleeve") || value.contains("long-sleeve") || value.contains("긴팔")
						? "long sleeve" : "";
		if (upperColor.isEmpty() || lowerColor.isEmpty() || sleeve.isEmpty()) return "";
		return gender + " wearing a " + upperColor + " " + sleeve + " top and " + lowerColor + " pants";
	}

	private List<ColorMatch> findColors(String value) {
		List<ColorMatch> matches = new ArrayList<>();
		addKoreanColor(matches, value, "검은색", "black");
		addKoreanColor(matches, value, "검정색", "black");
		addKoreanColor(matches, value, "파란색", "blue");
		addKoreanColor(matches, value, "파랑", "blue");
		addKoreanColor(matches, value, "갈색", "brown");
		addKoreanColor(matches, value, "초록색", "green");
		addKoreanColor(matches, value, "녹색", "green");
		addKoreanColor(matches, value, "회색", "gray");
		addKoreanColor(matches, value, "주황색", "orange");
		addKoreanColor(matches, value, "분홍색", "pink");
		addKoreanColor(matches, value, "핑크", "pink");
		addKoreanColor(matches, value, "보라색", "purple");
		addKoreanColor(matches, value, "빨간색", "red");
		addKoreanColor(matches, value, "흰색", "white");
		addKoreanColor(matches, value, "하얀색", "white");
		addKoreanColor(matches, value, "노란색", "yellow");
		addKoreanColor(matches, value, "청바지", "blue");
		var english = COLOR_PATTERN.matcher(value);
		while (english.find()) matches.add(new ColorMatch(english.start(), english.group().toLowerCase(Locale.ROOT)));
		matches.sort(Comparator.comparingInt(ColorMatch::position));
		return matches;
	}

	private void addKoreanColor(List<ColorMatch> matches, String value, String source, String color) {
		int position = value.indexOf(source);
		if (position >= 0 && matches.stream().noneMatch(match -> match.position() == position)) {
			matches.add(new ColorMatch(position, color));
		}
	}

	private record ColorMatch(int position, String color) {
	}
}
