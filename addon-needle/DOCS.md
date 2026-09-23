# Home Assistant Add-on: Needle

Run the [Cactus Compute Needle](https://github.com/cactus-compute/needle) local
tool-calling playground on a Home Assistant system.

Needle is a compact local model for selecting tools and producing structured
arguments. Inference runs locally after the add-on image has been installed.

## Supported systems

This add-on supports:

- `amd64` (x86-64)
- `aarch64` (64-bit ARM)

Needle does not currently provide a compatible Python runtime engine for
Home Assistant's `armv7` architecture.

## Installation

1. In Home Assistant, open **Settings → Add-ons → Add-on Store**.
2. Open the menu in the upper-right corner and select **Repositories**.
3. Add:

   ```text
   https://github.com/BelphegorPrime/ha-addon-collection
   ```

4. Find **Needle** in the store and install it.
5. Start the add-on.
6. Select **Open Web UI**, or select **Needle** in the Home Assistant sidebar.

The first start can take a while while Needle initializes its model. Home
Assistant's watchdog and the container health check wait for the `/model`
endpoint to become available.

The sidebar and **Open Web UI** views use Home Assistant ingress. The add-on
rewrites Needle's bundled root-relative static, API, and download URLs at image
build time so they remain below Home Assistant's tokenized ingress path. Direct
access through the configured port remains supported.

## How Needle fits into Home Assistant

Needle is a local **tool-call router**. You give it:

1. a natural-language request, such as "dim the living room to 30 percent";
2. a small list of tools that it is allowed to select; and
3. JSON schemas describing the permitted arguments.

Needle returns structured JSON containing the selected tool and its arguments.
It does **not** connect to Home Assistant or call Home Assistant services by
itself. An automation, script, Node-RED flow, AppDaemon app, or custom
integration must inspect the response and perform an explicitly allowlisted
action.

This separation is useful for safety: expose only narrow tools such as
`set_light`, `set_temperature`, or `start_bedtime`, rather than giving a model
unrestricted access to every Home Assistant service.

The add-on provides:

- a web playground for testing prompts and tool schemas;
- `GET /model` for health and model information;
- `POST /complete` for one-turn tool selection;
- `POST /reset` to clear the current conversation state.

It is not currently a drop-in Home Assistant conversation agent and does not
automatically appear in Assist.

## Connect Home Assistant to the add-on

### Find the address

Home Assistant Core runs in a different container, so do not use
`localhost:7860` in Home Assistant YAML. Use the IP address or hostname of the
Home Assistant host together with the host port configured on the add-on's
**Network** page, for example:

```text
http://192.168.1.50:7860
```

Replace `192.168.1.50` in all examples below. If you change the add-on's host
port, replace `7860` as well.

Test the address from another device on the same network:

```bash
curl http://192.168.1.50:7860/model
```

A ready add-on returns a response similar to:

```json
{"name": "needle (base)"}
```

### Optional health sensor

Add the following to Home Assistant's `configuration.yaml` to display the
loaded model and monitor availability:

```yaml
rest:
  - resource: "http://192.168.1.50:7860/model"
    scan_interval: 60
    timeout: 10
    sensor:
      - name: "Needle Model"
        unique_id: needle_model
        value_template: "{{ value_json.name }}"
```

Restart Home Assistant after editing `configuration.yaml`. The entity is
created as `sensor.needle_model` and becomes unavailable when the endpoint
cannot be reached.

## Configuration

Example using Needle's bundled base model:

```yaml
weights: ""
```

### `weights`

Optional absolute path to a custom Needle `.cact` weights file.

To keep custom weights across add-on updates:

1. Copy the `.cact` file into Home Assistant's `share` directory.
2. Configure its container path, for example:

   ```yaml
   weights: "/share/my-needle-model.cact"
   ```

3. Restart the add-on.

Startup fails with a descriptive log message if the path is relative or the
file does not exist.

## Network

The playground is available on TCP port `7860`. The default host port is also
`7860`, but it can be changed in the add-on's **Network** settings.

This version of Needle's playground does not provide authentication. Do not
expose the port directly to the internet. Limit access to trusted networks or
place it behind an authenticated reverse proxy.

## Persistence

- Home Assistant add-on data at `/data` is persistent.
- `/share` is mounted read/write for custom `.cact` files.
- The Needle native inference engine is downloaded while the image is built,
  so normal inference does not need to download it at startup.
- Files uploaded through Needle's playground are stored in the container's
  temporary directory and may disappear on restart. Put models in `/share` and
  use the `weights` option when persistence is required.

## Playground usage

The web interface lets you:

- enter tool schemas;
- submit a query;
- inspect the selected function and generated arguments;
- reset the current model state;
- load compatible `.cact` weights;
- use Needle's upstream fine-tuning workflow.

Some optional upstream functions, such as data generation for fine-tuning,
contact external services and may require an OpenRouter API key. The key is
submitted to the upstream Needle process for that operation; it is not an
add-on configuration option.

## Call Needle from Home Assistant

The following example turns a natural-language light request into a structured
`set_light` call. It intentionally exposes only two known rooms and three
fields.

### 1. Add a REST command

Add this to `configuration.yaml`:

```yaml
rest_command:
  needle_route_light_command:
    url: "http://192.168.1.50:7860/complete"
    method: POST
    content_type: "application/json"
    timeout: 120
    payload: >-
      {
        "tools": [
          {
            "name": "set_light",
            "description": "Set a light in a known room",
            "parameters": {
              "type": "object",
              "properties": {
                "room": {
                  "type": "string",
                  "enum": ["living_room", "bedroom"],
                  "description": "Room containing the light"
                },
                "state": {
                  "type": "string",
                  "enum": ["on", "off"],
                  "description": "Requested light state"
                },
                "brightness": {
                  "type": "integer",
                  "minimum": 1,
                  "maximum": 100,
                  "description": "Brightness percentage when explicitly requested"
                }
              },
              "required": ["room", "state"]
            }
          }
        ],
        "query": {{ query | to_json }}
      }
```

Restart Home Assistant after editing `configuration.yaml`. You can test the
command under **Developer Tools → Actions**:

```yaml
action: rest_command.needle_route_light_command
data:
  query: "dim the living room to 30 percent"
response_variable: needle_response
```

A successful response contains a call similar to:

```json
{
  "type": "call",
  "success": true,
  "function_calls": [
    {
      "name": "set_light",
      "arguments": {
        "room": "living_room",
        "state": "on",
        "brightness": 30
      }
    }
  ],
  "confidence": 0.94
}
```

Home Assistant exposes the JSON response under
`needle_response.content`. The exact response-variable display can differ
slightly between Home Assistant releases; inspect the trace of the test action
before building an automation around it.

### 2. Dispatch only allowlisted results

Do not template an arbitrary model-provided service name into an `action`.
Check the function name, validate arguments, apply a confidence threshold, and
map every accepted value to a known entity.

This script demonstrates the pattern:

```yaml
script:
  needle_light_command:
    alias: "Needle: route light command"
    mode: single
    fields:
      query:
        name: Request
        description: Natural-language light request
        required: true
        selector:
          text:
    sequence:
      - action: rest_command.needle_route_light_command
        data:
          query: "{{ query }}"
        response_variable: needle_response

      - variables:
          result: "{{ needle_response.content }}"
          calls: "{{ needle_response.content.function_calls | default([], true) }}"

      - condition: template
        value_template: >-
          {{
            result.success | default(false)
            and calls | count == 1
            and calls[0].name == "set_light"
            and result.confidence | float(0) >= 0.80
          }}

      - variables:
          arguments: "{{ calls[0].arguments }}"
          light_entities:
            living_room: light.living_room
            bedroom: light.bedroom
          selected_entity: "{{ light_entities.get(arguments.room) }}"

      - condition: template
        value_template: >-
          {{
            selected_entity is not none
            and arguments.state in ["on", "off"]
          }}

      - choose:
          - conditions: "{{ arguments.state == 'off' }}"
            sequence:
              - action: light.turn_off
                target:
                  entity_id: "{{ selected_entity }}"
        default:
          - action: light.turn_on
            target:
              entity_id: "{{ selected_entity }}"
            data:
              brightness_pct: "{{ arguments.brightness | default(100) | int }}"
```

Change `light.living_room` and `light.bedroom` to entity IDs that exist in your
installation. Place the script in `configuration.yaml` or `scripts.yaml`,
depending on how your configuration is organized, then restart Home Assistant
or reload scripts.

Call it under **Developer Tools → Actions**:

```yaml
action: script.needle_light_command
data:
  query: "turn off the bedroom light"
```

Once tested, the script can be called from:

- a dashboard button or text-input helper;
- an automation triggered by an event, webhook, NFC tag, or MQTT message;
- another Home Assistant script;
- Node-RED or AppDaemon;
- a custom conversation integration.

Keep human confirmation in front of sensitive operations such as unlocking
doors, opening garages, disabling alarms, purchases, or changing security
settings.

### Conversation and Assist

For an end-to-end, copy-and-paste setup using the add-on, Home Assistant
custom sentences, safe response validation, and a voice pipeline, follow
[Full Assist setup with Needle](FULL_ASSIST_SETUP.md). It starts with a
working lighting example and tests each integration layer separately.

This add-on does not register a Home Assistant
[conversation agent](https://www.home-assistant.io/integrations/conversation/)
and therefore cannot be selected directly as an Assist conversation agent.
Needle produces function calls rather than general conversational text, so it
is best used as the intent/tool-selection stage of a voice pipeline, not as the
speech response generator.

There are two practical integration levels:

1. **Simple commands:** create Home Assistant scripts like the example above
   and invoke them from dashboard controls or existing intent automations.
2. **Full Assist integration:** build or install a custom Home Assistant
   conversation integration that converts exposed actions into Needle tool
   schemas, calls `/complete`, validates the result, dispatches an approved
   Home Assistant action, and returns speech for Assist to read.

#### Full Assist integration

A full integration lets a request follow this path:

```text
Microphone
  → wake word
  → speech-to-text
  → custom Needle conversation agent
  → Needle add-on POST /complete
  → validated Home Assistant intent, script, or service call
  → text response
  → text-to-speech
  → speaker
```

Wake-word detection, speech-to-text, and text-to-speech remain separate Home
Assistant pipeline components. The custom integration replaces only the
**conversation agent** in the middle of the pipeline.

A production integration should be installed under a directory such as:

```text
/config/custom_components/needle_conversation/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── conversation.py
├── coordinator.py
└── translations/
    └── en.json
```

Home Assistant's conversation API changes over time. Consult the current
[conversation entity developer
documentation](https://developers.home-assistant.io/docs/core/entity/conversation/)
when implementing these files. The following sections describe the stable
responsibilities and data flow rather than source code that may become tied to
one Home Assistant release.

##### 1. Configuration flow

The integration's UI configuration flow should collect:

- the Needle base URL, for example `http://192.168.1.50:7860`;
- a request timeout, with a generous default such as 120 seconds;
- the minimum accepted confidence;
- the allowed Home Assistant actions;
- whether actions require confirmation;
- optional debug logging.

During setup, call `GET /model` and reject the configuration if the endpoint
cannot be reached or does not return model information. Do not ask users to
enter `localhost`: Home Assistant Core and the add-on run in different
containers.

Store only stable configuration in the config entry. Do not store arbitrary
tool schemas supplied through a voice command, and never put secrets into the
Needle prompt.

##### 2. Register a conversation entity

The integration should expose a Home Assistant conversation entity. Home
Assistant then makes that entity available as a conversation-agent choice when
an Assist pipeline is configured.

The entity receives a conversation input containing at least:

- the transcribed user text;
- the language;
- a Home Assistant context;
- a conversation identifier when available;
- the device or satellite identifier when available.

The entity should return a Home Assistant conversation result containing an
intent response. That response supplies the plain text which the selected
text-to-speech engine reads back to the user.

Needle's `/complete` endpoint is best treated as one-turn routing. Do not rely
on Needle to preserve an Assist conversation across requests. If follow-up
questions are required, keep that state in the Home Assistant integration and
associate it with Home Assistant's conversation identifier.

##### 3. Build tools from an allowlist

Do not expose the complete Home Assistant service registry to Needle. Define a
small registry of supported tools in the integration. Each tool should contain:

- a stable Needle function name;
- a precise description;
- a restrictive JSON schema;
- a validator for returned arguments;
- a dispatcher that maps validated arguments to fixed Home Assistant actions;
- a response formatter;
- an indication of whether confirmation is required.

For example, an internal registry could conceptually look like this:

```python
TOOLS = {
    "set_light": {
        "schema": {
            "name": "set_light",
            "description": "Set a light in a known room",
            "parameters": {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "enum": ["living_room", "bedroom"],
                    },
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                    },
                    "brightness": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["room", "state"],
            },
        },
        "requires_confirmation": False,
    },
}
```

The dispatcher must separately map `living_room` to
`light.living_room`, rather than allowing the model to generate an entity ID.
The schema limits model output, but it does not replace server-side validation.

A useful first version should expose Home Assistant scripts instead of raw
services. Scripts provide a narrow, auditable interface and keep device-specific
logic in Home Assistant. Example tools include:

- `start_bedtime`;
- `set_downstairs_lighting`;
- `announce_message`;
- `set_comfort_temperature`;
- `activate_movie_scene`.

##### 4. Call Needle

For each utterance, send the allowlisted tool schemas and transcription to the
add-on:

```http
POST /complete
Content-Type: application/json
```

```json
{
  "tools": [
    {
      "name": "set_light",
      "description": "Set a light in a known room",
      "parameters": {
        "type": "object",
        "properties": {
          "room": {
            "type": "string",
            "enum": ["living_room", "bedroom"]
          },
          "state": {
            "type": "string",
            "enum": ["on", "off"]
          },
          "brightness": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100
          }
        },
        "required": ["room", "state"]
      }
    }
  ],
  "query": "dim the living room to 30 percent"
}
```

Use Home Assistant's shared asynchronous HTTP client rather than blocking the
event loop. Apply both a connection timeout and an overall inference timeout.
Only one inference request is processed at a time by the playground, so the
integration should handle busy or timed-out requests gracefully.

##### 5. Validate the response

Treat Needle's output as untrusted input. Before dispatching anything, require
all of the following:

1. the HTTP request succeeded;
2. the body is valid JSON;
3. `success` is true;
4. exactly one function call was returned, unless the integration explicitly
   supports multiple calls;
5. the function name exists in the integration's allowlist;
6. confidence meets the configured threshold;
7. every required argument is present;
8. every argument has the expected type and range;
9. enum values and mapped entity keys are known;
10. the current Home Assistant user or context is permitted to run the action.

Reject extra arguments unless the tool explicitly supports them. Do not
dynamically template model-provided values into a domain, service, entity ID,
URL, shell command, event type, or template.

Conceptual processing logic:

```python
result = await needle.complete(tools=tool_schemas, query=user_text)

if not result.success:
    return speech("I could not match that request to an available action.")

if len(result.function_calls) != 1:
    return speech("I could not determine one safe action.")

call = result.function_calls[0]
tool = allowed_tools.get(call.name)

if tool is None or result.confidence < minimum_confidence:
    return speech("I am not confident enough to perform that action.")

arguments = tool.validate(call.arguments)
await tool.dispatch(hass, arguments, context=input_context)

return speech(tool.format_success(arguments))
```

This is architectural pseudocode, not a drop-in Home Assistant component.

##### 6. Preserve Home Assistant context

When the integration invokes an intent, script, or service, pass through the
context received with the conversation input. Context propagation allows
Home Assistant to associate the resulting state changes with the voice
request, apply authorization checks, and display a useful trace.

Prefer these dispatch layers, in order:

1. a narrowly defined Home Assistant intent;
2. a dedicated Home Assistant script;
3. a fixed domain and service with strictly mapped entities and validated
   data.

Avoid running actions under an unrestricted system context when the original
conversation has a user context.

##### 7. Generate Assist responses

Needle selects a tool but does not generate the final conversational reply.
The custom integration should create deterministic responses, for example:

| Outcome | Suggested response |
| --- | --- |
| Action completed | "The living room light is now at 30 percent." |
| No call returned | "I could not match that request to an available action." |
| Low confidence | "I am not confident enough to perform that action." |
| Invalid arguments | "I understood the action, but its details were invalid." |
| Add-on unavailable | "Needle is currently unavailable." |
| Request timed out | "Needle took too long to respond." |
| Action failed | "I understood the request, but Home Assistant could not complete it." |

Do not claim success until Home Assistant has accepted the action. For actions
where the resulting state matters, optionally wait for or verify the expected
state before returning a success response.

##### 8. Add confirmation for sensitive actions

Sensitive operations should use a two-step flow:

1. Needle identifies the requested action and arguments.
2. The integration stores the pending, fully validated action under the
   conversation ID and asks for confirmation.
3. A deterministic confirmation parser accepts only a narrow answer such as
   "yes" or "cancel".
4. The integration checks that the pending action has not expired and then
   dispatches it without asking Needle to reinterpret it.

A pending action should have a short expiry and be bound to the same
conversation, user, and preferably device. Never execute a different action
from text supplied during the confirmation turn.

Always require confirmation—or refuse voice control entirely—for actions such
as:

- unlocking or opening an exterior entry;
- opening a garage;
- disabling an alarm;
- changing security settings;
- making purchases;
- deleting data;
- sending externally visible messages.

##### 9. Configure the Assist pipeline

After the custom integration has been installed and Home Assistant restarted:

1. Open **Settings → Devices & services**.
2. Add the custom Needle conversation integration.
3. Enter the Home Assistant host address and Needle port.
4. Confirm that its setup test can read `GET /model`.
5. Open **Settings → Voice assistants**.
6. Create a new assistant or edit an existing one.
7. Select the Needle conversation entity as the conversation agent.
8. Select compatible speech-to-text and text-to-speech providers.
9. Assign the assistant to a phone, browser, or voice satellite.
10. Test one harmless tool before enabling additional actions.

The exact labels can differ between Home Assistant releases. If the Needle
entity is not listed, check the custom integration log and verify that it
implements and registers the conversation entity platform required by the
installed Home Assistant version.

##### 10. Test each layer separately

Test the integration from the bottom up:

1. `curl GET /model` from the network.
2. `curl POST /complete` with one tool.
3. Call the custom conversation entity using Home Assistant's conversation
   developer action, if available in the installed release.
4. Test typed input through Assist.
5. Test speech-to-text using the Assist debug view.
6. Test a harmless read-only or lighting action.
7. Test low-confidence, malformed-response, timeout, and unavailable-add-on
   behavior.
8. Verify that confirmation expires and cannot be reused.
9. Review Home Assistant traces and logs to ensure context is propagated.
10. Only then add more tools.

Useful diagnostics to log at debug level include latency, selected tool,
confidence, rejection reason, and dispatched Home Assistant action. Redact
utterances or arguments if they may contain private information, and never log
credentials.

##### Recommended first implementation

Start with a conversation agent that exposes only three to five dedicated
scripts, accepts exactly one function call, uses a conservative confidence
threshold, and does not support follow-up conversation. This is substantially
easier to audit than automatic entity discovery.

Automatic exposure of Home Assistant entities can be added later, but should
use Home Assistant's own exposed-entity controls and convert only supported
entities into narrow schemas. Entity names and aliases may be sent as model
input, so document the privacy implications before enabling automatic
discovery.

### Dashboard access

The add-on's **Open Web UI** button is the simplest way to access the
playground. You can also add a sidebar panel in `configuration.yaml`:

```yaml
panel_iframe:
  needle:
    title: "Needle"
    icon: "mdi:needle"
    url: "http://192.168.1.50:7860"
```

This works only when the browser can reach that address. Browsers may block an
HTTP iframe when Home Assistant itself uses HTTPS. In that case, continue
using **Open Web UI** or place Needle behind an authenticated HTTPS reverse
proxy.

### Node-RED, AppDaemon, and other clients

Any local client can call the same endpoint:

```bash
curl \
  --request POST \
  --header "Content-Type: application/json" \
  --data '{
    "tools": [{
      "name": "start_bedtime",
      "description": "Run the household bedtime routine",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": []
      }
    }],
    "query": "it is time for bed"
  }' \
  http://192.168.1.50:7860/complete
```

In Node-RED, use an HTTP Request node, then a JSON node, a Switch node that
checks the function name and confidence, and finally Home Assistant Call
Service nodes. Apply the same allowlist and validation rules used in the YAML
example.

## Automatically expose a large Home Assistant installation

You do not need to maintain one hand-written Needle tool for every entity.
However, the add-on cannot discover Home Assistant entities by itself. Add-ons
run separately from Home Assistant Core and do not register conversation
entities or receive direct access to Home Assistant's entity and service
registries.

A companion Home Assistant custom integration can automate this process:

1. read Home Assistant's entity, device, and area registries;
2. include only entities explicitly exposed to Assist under
   **Settings → Voice assistants → Expose**;
3. group entities into a small set of domain-level Needle tools;
4. populate tool enums with the currently allowed areas, entities, scenes, and
   scripts;
5. send those schemas to Needle with each request;
6. validate the returned function and arguments against the same catalog;
7. preserve the Home Assistant user context when dispatching the action; and
8. refresh the catalog when entities or exposure settings change.

Prefer a compact catalog such as:

- `set_light(light_or_area, state, brightness)`;
- `set_cover(cover_or_area, action, position)`;
- `set_climate(climate_or_area, temperature, mode)`;
- `activate_scene(scene)`;
- `run_script(script)`;
- `get_entity_state(entity)`;
- `get_area_state(area, domain)`.

For example, a generated lighting schema could resemble:

```json
{
  "name": "set_light",
  "description": "Control a light exposed to Assist",
  "parameters": {
    "type": "object",
    "properties": {
      "light": {
        "type": "string",
        "enum": ["living_room", "kitchen", "bedroom"]
      },
      "state": {
        "type": "string",
        "enum": ["on", "off"]
      },
      "brightness": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100
      }
    },
    "required": ["light", "state"],
    "additionalProperties": false
  }
}
```

The custom integration must map each stable enum value to an actual entity ID.
Needle must never be allowed to invent entity IDs.

Sensors normally belong in read-only state tools or selectively supplied
context rather than becoming individual executable tools. Lights, selected
scenes and scripts, media players, and bounded climate controls are reasonable
candidates for automatic exposure. Locks, garage doors, covers, alarms,
purchases, deletion, and externally visible messages should require explicit
confirmation or remain unavailable.

### Do not create an unrestricted service tool

Do not give Needle a generic tool like:

```text
call_service(domain, service, entity_id, data)
```

Although this would provide access to nearly every Home Assistant capability,
it would also let model output select arbitrary services, targets, and service
data. A JSON schema and a confidence score are not security boundaries.

For every returned call, the companion integration must verify:

1. the function is allowlisted;
2. the entity or area is currently exposed;
3. all arguments have expected names and types;
4. values satisfy enum and numeric restrictions;
5. the requested operation is compatible with the entity domain;
6. the originating Home Assistant context is authorized;
7. confidence meets the configured threshold; and
8. any required confirmation has completed and not expired.

This provides automatic coverage for a large installation without manually
maintaining hundreds of tools, while keeping Home Assistant—not the model—as
the authorization and execution boundary.

## Integration design recommendations

- Start with two to five narrow tools. Needle uses retrieval when more than
  five tools are supplied, but a smaller set is easier to test and secure.
- Use `enum`, numeric ranges, required fields, and clear descriptions in every
  JSON schema.
- Map model outputs to fixed entity IDs or scripts; never accept an arbitrary
  entity ID or service name from a prompt.
- Treat an empty `function_calls` list as "no matching action."
- Choose and test a confidence threshold. `0.80` in the example is only a
  starting point, not a universal safety guarantee.
- Log rejected calls while developing so schemas and prompts can be improved.
- Keep deterministic Home Assistant automations for rules that do not need
  natural-language interpretation.
- Remember that the playground serializes inference requests with an internal
  lock. It is suitable for household-scale experimentation, not a
  high-throughput API.
- The `/complete` playground endpoint resets model state when the same toolset
  is reused, so each request should be treated as an independent command.

## Security considerations

The playground API has no authentication. Anyone who can reach port `7860`
can submit inference requests, load a model, start supported fine-tuning
operations, and consume CPU and memory.

- Keep port `7860` on a trusted LAN.
- Do not configure router port forwarding for it.
- Do not expose it through Home Assistant Cloud.
- If remote access is required, use a VPN or an authenticated HTTPS reverse
  proxy.
- Use a firewall or isolated VLAN when untrusted devices share the network.
- Never place API keys in prompts, tool schemas, automations, or logs.
- Validate every returned call in Home Assistant before executing it.

## Local Docker test

This repository includes `test-local.sh`. With Docker running:

```bash
./test-local.sh
```

Open `http://localhost:7860`. To test compatible custom weights:

```bash
./test-local.sh /absolute/path/to/model.cact
```

Press `Ctrl+C` to stop the test container.

## Troubleshooting

### The add-on remains unhealthy during initial startup

Needle model initialization can be CPU- and memory-intensive. Check the add-on
log and allow up to several minutes on slower ARM systems.

### The add-on exits immediately

Check the configured `weights` value. It must be empty or an existing absolute
path such as `/share/model.cact`.

### The web interface does not open

Check that port `7860` is not already used by another add-on. You can assign a
different host port under the add-on's **Network** settings.

If the ingress page loads without styling or browser developer tools show
requests to the Home Assistant origin such as `/style.css`, confirm that add-on
version `2.0.6-4` or newer is installed. Rebuild or reinstall the add-on after
refreshing its repository metadata; restarting an older container does not
update the bundled playground files.

### A custom model fails to load

The `.cact` format is tied to the Needle engine version. Rebuild or export the
weights with the package version used by this add-on if Needle reports an
incompatible model.