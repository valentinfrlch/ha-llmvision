# Token usage tracking

## Enable and read it

In Home Assistant, reconfigure **LLM Vision Settings → General → Track token usage**.
It defaults to **off** for new and existing installations. One setting applies to
all configured providers; existing automations need no changes.

Each provider has a diagnostic device with lifetime counters for calls, errors,
calls without reported usage, input/output/total tokens, optional cache and
reasoning tokens, and separate analysis/title input/output/total tokens. All
sensors use `total_increasing` for Recorder statistics and Utility Meter helpers.
Choose a daily/monthly Utility Meter or a statistics chart rather than resetting
these lifetime counters. No currency or estimated price is asserted.

Disabling tracking stops updates and makes sensors unavailable while retaining
their totals. Re-enabling resumes from those totals. Removing a provider removes
its stored counters. Removing or unloading Settings stops all tracking. Reloading
a provider does not reset totals; restarting HA restores them from HA's local
versioned storage independently of Recorder retention.

## Sensor reference

Each configured provider entry gets the following 15 sensors. Their names and
meanings are the same across providers; Home Assistant may add the device name
to the displayed name. Separate entries for the same provider have separate
counters. Changing a model within an entry does not reset or split its totals.

The first three sensors use **calls**. The remaining sensors use **tokens**.
All values are cumulative over the periods when tracking is enabled. They are
not the usage of the latest request, daily totals, remaining quotas or prices.

| Sensor | What it tracks |
| --- | --- |
| **API calls** | Observed analysis and separate title invocations for which a provider transport attempt started, including failed calls. Each fallback invocation counts against the provider actually called. |
| **API errors** | Those observed calls that ended in an error, including transport failures and responses rejected by the provider adapter's existing validation. A failed call may still have reported billable token usage. |
| **Calls without usage** | Observed calls for which complete, valid normalized token usage was unavailable. This includes missing or malformed counts and failures without a usable response. It can overlap with **API errors**. |
| **Input tokens** | Reported input tokens across analysis and title calls, including reported cached input after normalization. |
| **Output tokens** | Reported generated tokens across analysis and title calls, including reported reasoning/thinking output after normalization. |
| **Total tokens** | Reported total tokens across analysis and title calls, or the normalized input-plus-output sum when the reported total is missing, invalid or smaller. A larger reported total is retained. |
| **Cache read tokens** | Reported input tokens served from the provider's cache. These are already included in **Input tokens** and **Total tokens**. |
| **Cache write tokens** | Reported input tokens written to the provider's cache. These are already included in **Input tokens** and **Total tokens**. |
| **Reasoning tokens** | Reported reasoning/thinking tokens. These are already included in **Output tokens** and **Total tokens**. |
| **Analysis input tokens** | The **Input tokens** definition, restricted to analysis calls made by the image, video, stream or data analyzer. |
| **Analysis output tokens** | The **Output tokens** definition, restricted to those analysis calls. |
| **Analysis total tokens** | The **Total tokens** definition, restricted to those analysis calls. |
| **Title input tokens** | The **Input tokens** definition, restricted to separate title-generation calls. |
| **Title output tokens** | The **Output tokens** definition, restricted to separate title-generation calls. |
| **Title total tokens** | The **Total tokens** definition, restricted to separate title-generation calls. |

The analysis and title counters divide the corresponding overall totals; do not
add them to the overall totals again. Cache and reasoning counters are also
breakdowns, not additional consumption. A title embedded in an analysis response
contributes only to analysis counters because there was no separate title call.

Token counters sum only usable reported amounts. Missing usage leaves them
unchanged and increments **Calls without usage** instead. Optional cache and
reasoning breakdowns may be absent even when the main input/output counts exist,
so zero in a breakdown sensor does not prove that the model never used that
feature. Missing data is not backfilled or estimated.

## What a count means

The feature observes the **existing** provider requests. It does not change model
payloads, response variables, output limits, title generation or fallback policy,
and does not make any additional model requests.

- Each analysis and any subsequent title request is counted separately.
- A structured/Glimpse response that already contains a title has no extra title
  call to count. Its usage remains analysis usage.
- A fallback is counted against the provider actually called. Existing title
  fallback behavior may repeat analysis on the fallback provider; both actual
  requests count rather than hiding that consumption.
- Failed calls count as errors. A response rejected by the provider adapter still
  contributes any token usage the provider actually returned. This feature does
  not change which responses each adapter accepts.
- Missing, incomplete or malformed core usage is **unknown**, not an estimated
  zero. The call-without-usage counter increments; no token event is fabricated.
- Missing optional cache/reasoning breakdowns do not imply no cache/reasoning
  occurred. Those counters sum only reported breakdowns.
- Configuration validation calls are excluded: these are outside attributed
  analysis/title requests and may precede creation of a provider entry. They may
  incur charges, but this feature adds no validation calls.
- A timeout, cancellation or network failure can occur after the provider bills a
  request. Missing responses cannot be reconstructed. Bedrock's SDK may retry
  internally; the counter measures one SDK invocation, not every wire attempt.
  Treat totals as **observed consumption**, not a replacement for provider bills.
- Tracking starts when enabled. It cannot import historical provider usage.

## Normalization

Only nonnegative JSON integers are accepted. Booleans, numeric strings, floats
and negative core counts are rejected rather than coerced. Both input and output
counts must exist. Normalized input includes cached input; normalized output
includes reported reasoning output. Cache/reasoning fields are informational
subsets, never values to add a second time.

The material provider differences are:

- **Anthropic Messages and Bedrock Converse** report cache reads and writes
  separately from uncached input. Those cache amounts are added to input so the
  input sensor has the same inclusive meaning as for other providers.
- **Gemini** reports thinking tokens separately from candidate output. Those
  thoughts are added to output. Other APIs that already include cache/reasoning
  breakdowns in their main counts are not added a second time.
- **Optional usage reporting varies by provider and compatible server.** An
  unsupported or omitted cache/reasoning breakdown stays uncounted. Missing or
  invalid core usage increments **Calls without usage** instead of inventing
  token counts. Ordinary analysis results are still returned.

A reported total is retained when it is at least the normalized input plus output;
otherwise the normalized sum is used. This handles provider totals that exclude
separately reported cache amounts. A larger provider total can include categories
not exposed separately. No tokenizer or token estimates are used.

Bedrock's separate-cache semantics are documented in the
[AWS prompt caching guide](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html).

## Events and privacy

`llmvision_token_usage` fires once when complete normalized usage is available.
`llmvision_call_finished` fires for each observed analysis/title invocation,
including errors and missing usage. Do not accumulate both as independent calls.
Both preserve the original HA service context for automation tracing.

Both include only these fixed metadata fields: schema version, configured provider
label, config entry ID, bounded configured model identifier (if safe; URLs and account-specific ARNs are omitted), known service
name, request type (`analysis` or `title`), success/error status, a usage-availability
flag and elapsed milliseconds. The token event additionally includes normalized
counts and valid optional cache/reasoning breakdowns. No raw provider response
model/ID is copied. Unknown service names become `unknown`.

Prompts, response text, images, image paths, camera names, event IDs, prompt hashes,
endpoints, headers, keys and exception text are never copied to usage events,
sensor attributes or storage. Existing integration logging outside this feature
is unchanged. Event listeners and Recorder are controlled by the user's HA setup;
this feature sends no usage data to an external service.

Only aggregate integer counters keyed by provider entry ID are persisted, not an
unbounded event history or per-model/camera dimensions. Updates are serialized on
the HA event loop and saved after each observed call. A storage write failure logs
a fixed warning but never fails an otherwise successful analysis. In-memory counts
remain available, with the next successful save including them. A failed initial
restore disables tracking rather than overwriting unknown lifetime totals.

## Maintenance map and invariants

- `usage.py`: provider normalization, strict validation, safe metadata allowlists,
  one manager, durable totals and event emission. It lives at its own top-level
  `hass.data` key so existing provider-config iteration cannot mistake it for a
  configured provider.
- `Provider.vision_request` / `title_request`: scope a single attributed request,
  start timing, preserve success/error outcome, and publish in `finally` without
  replacing the existing result or exception. Preparation errors before transport
  are not API calls. Provider instances are created per `Request.call`, so one
  request's accounting never shares mutable state with another.
- `Provider._post` and `AWSBedrock.invoke_bedrock`: capture normalized usage before
  adapters discard the response envelope. They do not retain the raw envelope.
  HTTP and IAM paths must never both account for the same invocation.
- `sensor.py`: reads manager totals and subscribes to updates. It does not maintain
  a second persistence layer or accumulate event totals again.
- `__init__.py`: initializes storage before provider sensor setup; Settings controls
  the global switch; provider unload preserves counters and removal discards them.
- `config_flow.py`: additive opt-in setting, preserving prior values and existing
  memory data when unrelated form sections are omitted.

For new providers, explicitly document the response schema and whether cache or
reasoning fields are subsets or disjoint. Add fixtures for normal/missing/malformed
usage and ensure the configured label is allowlisted. Never copy raw request or
response dictionaries into accounting metadata. If adding transport retries, emit
for each completed response rather than overwriting one attempt's usage.

## Attribution and comparison

Credit **[bforejt](https://github.com/bforejt)** for identifying the gap, proposing
provider-normalized token usage events and the billed-input/output normalization
convention in [upstream discussion #714](https://github.com/valentinfrlch/ha-llmvision/discussions/714).
Reviewed references: `feat/token-usage-events` at `e50fa60` and `main` at `323643b`.
Their fork already includes native restored sensors and analysis/title distinctions.
Those are shared ideas, **not novelty claims** for this implementation.

Deliberate differences from the reviewed reference:

1. Global opt-in control, default off, with disabled sensors retaining totals.
2. Smaller metadata surface: no camera/media/file names, hashes, request/response
   IDs or raw provider fields; aggregate-only HA Store persistence.
3. Strict unknown/malformed-count handling and explicit calls-without-usage.
4. Counts and status after existing provider response parsing, including usage
   from locally rejected responses, with distinct completed-call and token-usage
   events.
5. Explicit Bedrock Converse cache-input normalization.
6. Configuration validation calls are excluded and documented.
7. Separate analysis/title lifetime sensors, alongside total counters.

The reference's event schema is not promised as drop-in compatible: this uses
`request_type: analysis` rather than `vision`, intentionally omits richer source
fields, and has its own completed-call event contract. Document this for any
existing consumers before migration.
