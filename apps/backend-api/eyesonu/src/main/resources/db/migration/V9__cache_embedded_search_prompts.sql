ALTER TABLE search_conditions
    ADD COLUMN embedded_prompt TEXT NULL AFTER prompt,
    ADD COLUMN embedded_exclusion_prompt TEXT NULL AFTER exclusion_prompt;

UPDATE search_conditions
SET embedded_prompt = prompt,
    embedded_exclusion_prompt = exclusion_prompt
WHERE embedded_prompt IS NULL;
