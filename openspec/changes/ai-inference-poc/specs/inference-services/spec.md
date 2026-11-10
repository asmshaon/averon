## Purpose

Provides self-hosted speech-to-text (Whisper.cpp) and translation (llama.cpp) inference on the existing VPS. The services stay private and resource-bounded and cost nothing beyond the server already owned.

## ADDED Requirements

### Requirement: Inference services are private
The speech-to-text and translation services SHALL be reachable only from the AI runner (and, later, the Laravel worker) over the private container network. They SHALL NOT bind or publish any port on a public host interface.

#### Scenario: No public exposure
- **WHEN** the inference stack is running on the VPS and an external host scans the VPS public IP
- **THEN** neither the speech-to-text nor the translation service port is reachable

#### Scenario: Runner can reach services
- **WHEN** the AI runner runs inside the private network
- **THEN** it can call both the speech-to-text and the translation service by internal service name

### Requirement: Models stay loaded between turns
Each inference service SHALL load its model once at startup and keep it loaded across requests, so a turn does not pay the model-load time.

#### Scenario: Consecutive turns reuse loaded model
- **WHEN** two turns are processed one after the other
- **THEN** the second turn's measured stage time does not include a model reload, and the service process stays up between them

### Requirement: Resource bounds on the shared VPS
Each inference service SHALL run with an explicit memory limit and CPU thread count, and SHALL process at most one inference request at a time. The memory limits SHALL leave room for the OS, MySQL, PHP-FPM and the queue worker that run on the same VPS later.

#### Scenario: Memory limit enforced
- **WHEN** a service is started
- **THEN** its container has a configured memory limit, and the sum of the inference limits plus a documented reserve for the other components does not exceed 8 GB

#### Scenario: Single inference at a time
- **WHEN** a second translation request arrives while one is being processed
- **THEN** the service queues or rejects it instead of running two inferences at once

### Requirement: Only one model-serving stack
The deployment SHALL use llama.cpp as the only LLM serving runtime and SHALL NOT run Ollama or any GPU-dependent model alongside it.

#### Scenario: Deployment manifest check
- **WHEN** the deployment configuration is inspected
- **THEN** it defines exactly one STT service and one llama.cpp translation service, with no Ollama service and no GPU device reservations

### Requirement: Model files outside the repository with documented licenses
Model weight files SHALL be stored on a host path outside the source repository and mounted read-only into the services. Every model used or benchmarked SHALL be recorded with its source, exact file name, quantization, checksum and license.

#### Scenario: Repository contains no weights
- **WHEN** the repository is searched for model weight files (for example `*.bin`, `*.gguf`)
- **THEN** none are found, and the model directory is configured through an environment variable

#### Scenario: License recorded before use
- **WHEN** a model is added to the benchmark candidates
- **THEN** the model registry document lists its license and source before any benchmark results for it are reported

### Requirement: Services recover from process failure
Each inference service SHALL restart automatically if its process exits, and SHALL expose a health check the runner can use to tell "service unavailable" apart from "inference failed".

#### Scenario: Service crash
- **WHEN** an inference service process is killed
- **THEN** the container is restarted automatically, and requests made while it is down fail with a service-unavailable condition, not a hang
