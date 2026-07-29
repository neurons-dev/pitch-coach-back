package com.pitchcoach.core.user.domain;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = false)
public class OauthProviderConverter implements  AttributeConverter<OauthProvider, String> {
    @Override
    public String convertToDatabaseColumn(OauthProvider attribute) {
        return attribute == null ? null : attribute.name().toLowerCase();
    }

    @Override
    public OauthProvider convertToEntityAttribute(String dbData) {
        return dbData == null ? null : OauthProvider.valueOf(dbData.toUpperCase());
    }
}
