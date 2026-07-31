ALTER TABLE search_conditions
    ADD COLUMN embedded_prompt TEXT NULL AFTER prompt,
    ADD COLUMN embedded_exclusion_prompt TEXT NULL AFTER exclusion_prompt;

UPDATE search_conditions
SET embedded_prompt = CASE
        WHEN prompt NOT REGEXP '[가-힣]' THEN prompt
        ELSE NULL
    END,
    embedded_exclusion_prompt = CASE
        WHEN exclusion_prompt IS NULL OR exclusion_prompt NOT REGEXP '[가-힣]'
            THEN exclusion_prompt
        ELSE NULL
    END
WHERE embedded_prompt IS NULL;
