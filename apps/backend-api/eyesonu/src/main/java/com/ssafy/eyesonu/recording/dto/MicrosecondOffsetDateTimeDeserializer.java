package com.ssafy.eyesonu.recording.dto;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.regex.Pattern;
import tools.jackson.core.JacksonException;
import tools.jackson.core.JsonParser;
import tools.jackson.core.JsonToken;
import tools.jackson.databind.DeserializationContext;
import tools.jackson.databind.ValueDeserializer;

/**
 * Parses offset date-times without silently truncating values that cannot be stored in DATETIME(6).
 */
public final class MicrosecondOffsetDateTimeDeserializer extends ValueDeserializer<OffsetDateTime> {

    private static final Pattern RFC_3339_MICROSECOND = Pattern.compile(
            "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{1,6})?(?:Z|[+-]\\d{2}:\\d{2})$");

    @Override
    public OffsetDateTime deserialize(JsonParser parser, DeserializationContext context) throws JacksonException {
        if (!parser.hasToken(JsonToken.VALUE_STRING)) {
            return (OffsetDateTime) context.handleUnexpectedToken(OffsetDateTime.class, parser);
        }

        String value = parser.getString();
        if (value == null || !RFC_3339_MICROSECOND.matcher(value).matches()) {
            throw context.weirdStringException(value, OffsetDateTime.class,
                    "must be an RFC 3339 date-time with an offset and at most 6 fractional digits");
        }

        try {
            return OffsetDateTime.parse(value);
        } catch (DateTimeParseException exception) {
            throw context.weirdStringException(value, OffsetDateTime.class, "must be a valid RFC 3339 date-time");
        }
    }
}
