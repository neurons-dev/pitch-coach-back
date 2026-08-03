package com.pitchcoach.core.session.domain;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = false)
public class PracticeSessionStatusConverter implements AttributeConverter<PracticeSessionStatus, String> {

    @Override
    public String convertToDatabaseColumn(PracticeSessionStatus attribute) {
        return attribute == null ? null : attribute.name().toLowerCase();
    }

    @Override
    public PracticeSessionStatus convertToEntityAttribute(String dbData) {
        return dbData == null ? null : PracticeSessionStatus.valueOf(dbData.toUpperCase());
    }
}
