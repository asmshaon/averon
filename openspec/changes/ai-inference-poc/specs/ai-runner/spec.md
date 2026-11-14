## Purpose

Defines the command-line contract of the Python AI runner, which processes a single translation turn (speech-to-text, then translation) against the private inference services. Laravel queue jobs depend on this contract later.

## ADDED Requirements

### Requirement: Turn invocation inputs
The runner SHALL accept a turn ID, a source language, a target language, an optional dialect instruction, and exactly one input: either an audio file path or a text input (for translation-only runs). The only supported language codes SHALL be `bn-BD` and `ar`, and the source and target SHALL differ.

#### Scenario: Valid audio invocation
- **WHEN** the runner is invoked with a turn ID, an existing audio path, `--source bn-BD` and `--target ar`
- **THEN** it transcribes the audio as Bangla and translates the result into Arabic

#### Scenario: Translation-only invocation
- **WHEN** the runner is invoked with a text input instead of an audio path
- **THEN** it skips speech-to-text and returns a translation of the given text, with the transcription field equal to the input text

#### Scenario: Unsupported language
- **WHEN** the runner is invoked with a language code other than `bn-BD` or `ar` (including the former `ar-SA`), or with the same source and target
- **THEN** it exits non-zero with error code `invalid_arguments` and makes no inference call

### Requirement: Structured JSON result
The runner SHALL write exactly one JSON object to standard output for every invocation, success or failure. The object SHALL contain: `turn_id`, `status` (`completed` or `failed`), `source_language`, `target_language`, `transcription`, `translation`, `models` (STT and translation model identifiers), `timings_ms` (per stage and total), `audio_duration_seconds`, and `error_code` (null on success).

#### Scenario: Successful turn
- **WHEN** a turn completes
- **THEN** stdout holds a single JSON object with `status: "completed"`, non-empty `transcription` and `translation`, both model identifiers, stage and total timings, and `error_code: null`, and the process exits 0

#### Scenario: Failed turn
- **WHEN** any stage fails
- **THEN** stdout still holds a single JSON object with `status: "failed"` and a normalized `error_code`, and the process exits non-zero

### Requirement: Normalized error codes
The runner SHALL report failures using only this fixed set of error codes: `invalid_arguments`, `audio_unreadable`, `audio_empty`, `audio_too_long`, `stt_unavailable`, `stt_timeout`, `stt_failed`, `transcription_empty`, `translation_unavailable`, `translation_timeout`, `translation_failed`, `internal_error`. Each code SHALL be marked as retryable (transient) or not, and the marker SHALL appear in the output.

#### Scenario: Service down
- **WHEN** the translation service cannot be reached
- **THEN** the result has `error_code: "translation_unavailable"` and `retryable: true`

#### Scenario: Silent audio
- **WHEN** the audio contains no recognizable speech
- **THEN** the result has `error_code: "transcription_empty"` and `retryable: false`, and no translation call is made

### Requirement: Audio limits enforced from content
The runner SHALL work out audio duration and readability from the file content itself, not from the file name or any caller-supplied metadata. It SHALL reject audio longer than 30 seconds, and it SHALL normalize accepted audio to the format the speech-to-text service needs.

#### Scenario: Over-length clip
- **WHEN** the audio content is 31 seconds long
- **THEN** the runner fails with `audio_too_long` without calling speech-to-text

#### Scenario: Mislabelled file
- **WHEN** a file named `clip.wav` contains bytes that are not decodable audio
- **THEN** the runner fails with `audio_unreadable`

### Requirement: Explicit timeouts
Every call to an inference service SHALL have a configurable timeout. If a timeout is exceeded, the runner SHALL abort that stage and report the matching `*_timeout` error code within a bounded time.

#### Scenario: Translation hangs
- **WHEN** the translation service does not respond within the configured timeout
- **THEN** the runner returns `translation_timeout` and exits non-zero no later than shortly after the timeout

### Requirement: Modern Standard Arabic is requested explicitly
When the target language is `ar`, the runner SHALL instruct the translation model to produce clear Modern Standard Arabic suitable for everyday conversation, not a regional dialect. When the target is `bn-BD`, it SHALL ask for natural everyday Bangladeshi Bangla. The output SHALL contain only the translation, with no explanations, transliteration or quotes.

#### Scenario: Bangla to Arabic
- **WHEN** a Bangla sentence is translated to `ar`
- **THEN** the request sent to the model includes an explicit Modern Standard Arabic instruction, and the returned `translation` contains only the translated sentence

#### Scenario: Register override
- **WHEN** a register instruction is passed on the command line (`--dialect`)
- **THEN** it is used in place of the default Arabic register instruction for that turn

### Requirement: No content logging
The runner SHALL NOT write audio bytes, transcriptions or translations to logs or standard error. Logs SHALL contain only turn ID, stage names, timings, model identifiers and error codes. Transcription and translation text SHALL appear only in the standard-output JSON result.

#### Scenario: Log inspection
- **WHEN** a turn is processed with verbose logging enabled
- **THEN** stderr and log files contain no transcription or translation text

### Requirement: Local-only processing with no paid fallback
The runner SHALL call only the self-hosted inference services. It SHALL contain no enabled path to any paid or external AI provider. When local inference fails, it SHALL return the failure, not retry through another provider.

#### Scenario: Local failure
- **WHEN** speech-to-text fails
- **THEN** the runner returns a failed result, and no network request is made to any host outside the private inference network

### Requirement: Usage data for every stage
For each stage it runs, the runner SHALL report the provider (`local`), the operation (`stt` or `translation`), the model identifier, the elapsed time, the input units (audio seconds for STT, input characters for translation) and an estimated cost of `0`.

#### Scenario: Usage in result
- **WHEN** a turn completes
- **THEN** the JSON result includes a `usage` array with one entry per executed stage, each with `estimated_cost: 0`
