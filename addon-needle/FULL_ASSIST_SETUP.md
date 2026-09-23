# Full Assist setup with Needle

This guide connects the Needle add-on to a Home Assistant Assist voice
pipeline.

After completing the main setup, you can say:

> Ask Needle to dim the living room to 30 percent.

The request follows this path:

```text
Voice or typed Assist request
  → Home Assistant speech-to-text
  → Home Assistant custom sentence
  → Needle POST /complete
  → validation and allowlist
  → Home Assistant action
  → spoken response
```

This setup uses Home Assistant's built-in conversation agent and does not
require a custom Python integration. The phrase must begin with **Ask Needle
to** so Home Assistant knows that the rest of the sentence should be sent to
Needle.

> [!IMPORTANT]
> This guide starts with lighting because it is easy to test and relatively
> low risk. Do not add locks, alarms, garage doors, purchases, or other
> sensitive actions until you have implemented explicit confirmation.

## What you need

Before starting, make sure that you have:

- Home Assistant OS or Home Assistant Supervised;
- an `amd64` or `aarch64` Home Assistant system;
- File editor, Studio Code Server, Samba, or another way to edit files under
  `/config`;
- a working Assist pipeline;
- speech-to-text and text-to-speech providers if you want to use voice;
- at least one light entity for the example.

You can also complete the setup and test it with typed Assist input before
configuring a microphone.

## Overview

Complete the following stages in order:

1. Install and test the Needle add-on.
2. Identify the Home Assistant host address.
3. Create a REST command that calls Needle.
4. Create a safe Home Assistant script that validates Needle's response.
5. Add a custom Assist sentence.
6. Connect the custom sentence to the script.
7. Restart Home Assistant and test typed input.
8. Test the complete voice pipeline.
9. Add more allowlisted tools only after the first one works.

## Stage 1: Install the Needle add-on

1. Open **Settings → Add-ons → Add-on Store**.
2. Open the menu in the upper-right corner.
3. Select **Repositories**.
4. Add this repository:

   ```text
   https://github.com/BelphegorPrime/ha-addon-collection
   ```

5. Close the repository dialog.
6. Find and open **Needle**.
7. Select **Install**.
8. Leave the add-on configuration at its default value:

   ```yaml
   weights: ""
   ```

9. Enable **Start on boot**.
10. Enable **Watchdog**.
11. Start the add-on.
12. Wait until the log reports that Needle is listening.
13. Select **Open Web UI** and verify that the playground opens.

Initial model loading can take several minutes on slower systems.

## Stage 2: Find an address Home Assistant can use

Home Assistant Core and the add-on run in separate containers. Do not use
`localhost` in `configuration.yaml`.

Use the LAN IP address of the Home Assistant host. You can find it under
**Settings → System → Network**. This guide uses the following example:

```text
192.168.1.50
```

Replace that address in every example.

The add-on uses host port `7860` by default. Under the add-on's **Network**
section, confirm that container port `7860/tcp` is mapped to host port `7860`.

From another computer on the same network, test:

```bash
curl http://192.168.1.50:7860/model
```

A ready add-on returns model information similar to:

```json
{"name": "needle (base)"}
```

If this request fails, do not continue yet. Check:

- that the add-on is running;
- that its log contains no model-loading error;
- that the IP address is correct;
- that port `7860` is configured;
- that a firewall or VLAN is not blocking the connection.

## Stage 3: Add the Needle REST command

Open `/config/configuration.yaml` and add the following block.

If the file already contains a `rest_command:` section, add only
`needle_route_light_command` below the existing section. YAML files must not
contain two top-level `rest_command:` keys.

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

Replace `192.168.1.50` with your Home Assistant host address.

Do not expand the room enum yet. First complete the guide with the two example
room keys.

## Stage 4: Create the safe dispatch script

Open `/config/scripts.yaml` and add the following script.

If you manage scripts inside `configuration.yaml`, place the script below your
existing `script:` key instead. Do not create a second top-level `script:` key.

```yaml
needle_light_command:
  alias: "Needle: route light command"
  description: "Route an allowlisted lighting request through Needle"
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

    - if:
        - condition: template
          value_template: >-
            {{
              not result.success | default(false)
              or calls | count != 1
              or calls[0].name != "set_light"
              or result.confidence | float(0) < 0.80
            }}
      then:
        - stop: "Needle did not return one sufficiently confident set_light call"

    - variables:
        arguments: "{{ calls[0].arguments }}"
        light_entities:
          living_room: light.living_room
          bedroom: light.bedroom
        selected_entity: "{{ light_entities.get(arguments.room) }}"

    - if:
        - condition: template
          value_template: >-
            {{
              selected_entity is none
              or arguments.state not in ["on", "off"]
              or (
                arguments.brightness is defined
                and (
                  arguments.brightness | int < 1
                  or arguments.brightness | int > 100
                )
              )
            }}
      then:
        - stop: "Needle returned unsupported light arguments"

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

Replace these example entity IDs with real entities from your installation:

```yaml
living_room: light.living_room
bedroom: light.bedroom
```

Keep the keys on the left unchanged for now. Only replace the entity IDs on the
right.

For example:

```yaml
light_entities:
  living_room: light.living_room_ceiling
  bedroom: light.bedroom_lamp
```

The script deliberately maps model output to fixed entities. It never treats a
model-provided string as an entity ID, domain, or service.

## Stage 5: Test the REST command and script

Before adding Assist, test the lower layers.

### Check the YAML configuration

1. Open **Developer Tools → YAML**.
2. Select **Check configuration**.
3. Correct any reported YAML errors.
4. Restart Home Assistant so that the REST command is registered.

### Test the REST command

Open **Developer Tools → Actions** and run:

```yaml
action: rest_command.needle_route_light_command
data:
  query: "dim the living room to 30 percent"
response_variable: needle_response
```

Inspect the response. It should contain one `set_light` function call with
allowlisted arguments.

### Test the script

Open **Developer Tools → Actions** and run:

```yaml
action: script.needle_light_command
data:
  query: "dim the living room to 30 percent"
```

Confirm that the mapped light changes.

Also test:

```yaml
action: script.needle_light_command
data:
  query: "turn off the bedroom light"
```

Do not continue until both requests control only the expected entities.

## Stage 6: Add an Assist custom sentence

Create this directory if it does not already exist:

```text
/config/custom_sentences/en/
```

Create the file:

```text
/config/custom_sentences/en/needle.yaml
```

Add:

```yaml
language: "en"

intents:
  NeedleCommand:
    data:
      - sentences:
          - "(ask|tell) needle [to] {query}"

lists:
  query:
    wildcard: true
```

The `{query}` wildcard captures the words after “Ask Needle to”. Home Assistant
passes those words to the intent handler in the next stage.

Examples that should match:

- “Ask Needle to turn off the bedroom light.”
- “Tell Needle to set the living room light to 50 percent.”
- “Ask Needle dim the living room.”

Examples without “Ask Needle” or “Tell Needle” continue to use the normal
Home Assistant conversation behavior.

### Other languages

Create a file under the matching language directory and translate only the
trigger sentence. Keep the intent name `NeedleCommand` and slot name `query`
unchanged.

For example, the directory for German is:

```text
/config/custom_sentences/de/
```

The exact wording and sentence syntax should be tested with Home Assistant's
sentence parser for the language in use.

## Stage 7: Connect the sentence to the script

Open `/config/configuration.yaml` and add:

```yaml
intent_script:
  NeedleCommand:
    action:
      - action: script.needle_light_command
        data:
          query: "{{ query }}"
    speech:
      text: "I sent the lighting request to Needle."
```

If `configuration.yaml` already contains `intent_script:`, add only the
`NeedleCommand` entry below it.

The intent name must exactly match the name in `needle.yaml`, including
capitalization.

The simple spoken response confirms that Home Assistant dispatched the
request. It does not guarantee that the physical device reached the requested
state. A companion custom conversation integration is needed for rich,
outcome-specific responses and multi-turn confirmation.

## Stage 8: Reload and test typed Assist

1. Open **Developer Tools → YAML**.
2. Select **Check configuration**.
3. Fix any reported issue.
4. Restart Home Assistant.
5. Open Assist from the Home Assistant header or mobile app.
6. Type:

   ```text
   Ask Needle to dim the living room to 30 percent
   ```

7. Confirm all three results:
   - Assist displays the configured response;
   - the expected light changes;
   - no other entity changes.

If Assist says that it did not understand the request:

1. confirm that `needle.yaml` is under
   `/config/custom_sentences/en/`;
2. confirm that the selected Assist pipeline uses English;
3. check indentation and capitalization;
4. restart Home Assistant after changing custom sentence files;
5. inspect **Settings → System → Logs**.

## Stage 9: Configure and test voice

If typed Assist works, configure the voice components.

1. Open **Settings → Voice assistants**.
2. Create a new assistant or edit an existing one.
3. Select the normal Home Assistant conversation agent.
4. Select a speech-to-text provider.
5. Select a text-to-speech provider.
6. Select the language matching the custom-sentence directory.
7. Assign the assistant to the Home Assistant mobile app, browser, or voice
   satellite.
8. Say:

   > Ask Needle to turn off the bedroom light.

Home Assistant Cloud can provide speech-to-text and text-to-speech. A fully
local pipeline can instead use supported local providers such as Whisper and
Piper. Their installation is independent of Needle.

If typed input works but voice does not, inspect the Assist pipeline debug
view. Confirm that speech-to-text produced a sentence beginning with “Ask
Needle to”.

## Stage 10: Add your own rooms

For each new room, update all of these places:

1. the `room` enum in `rest_command.needle_route_light_command`;
2. the `light_entities` mapping in `script.needle_light_command`;
3. your tests.

Example:

```yaml
"enum": ["living_room", "bedroom", "kitchen"]
```

```yaml
light_entities:
  living_room: light.living_room_ceiling
  bedroom: light.bedroom_lamp
  kitchen: light.kitchen_ceiling
```

Use short stable keys in the schema and map them to actual entity IDs in the
script.

Restart Home Assistant after changing the REST command. Reloading scripts is
usually sufficient after changing only `scripts.yaml`.

This manual mapping is appropriate for the built-in custom-sentence setup in
this guide. For large installations, use the companion-integration approach
described under [Automatically expose a large
installation](#automatically-expose-a-large-installation) instead of copying
hundreds of entities into YAML.

## Stage 11: Add more tools safely

Do not immediately replace the lighting tool with unrestricted Home Assistant
access.

For each new tool:

1. create or identify a dedicated Home Assistant script;
2. give the tool one narrow purpose;
3. define a restrictive JSON schema;
4. use enums instead of arbitrary entity IDs;
5. validate all fields after Needle responds;
6. map accepted values to fixed scripts or entities;
7. reject unknown or additional fields;
8. test low-confidence and invalid responses;
9. add confirmation if the action is sensitive.

Good next tools include:

- starting a bedtime script;
- activating a movie scene;
- setting a bounded comfort temperature;
- starting a known music playlist;
- making an announcement to a fixed speaker.

Do not expose arbitrary:

- service names;
- entity IDs;
- event names;
- URLs;
- templates;
- shell commands;
- file paths.

## What this setup does and does not provide

This guide provides a complete, usable Assist path with:

- the Needle add-on;
- typed or spoken Assist input;
- a natural-language wildcard after a clear trigger phrase;
- Needle tool selection;
- strict server-side validation;
- a Home Assistant action;
- a spoken acknowledgement.

It intentionally keeps Home Assistant's built-in conversation agent selected.
This means normal Home Assistant sentences still work and only requests
beginning with “Ask Needle” are routed to Needle.

It does not make Needle the conversation agent for every Assist utterance.
That advanced setup requires a companion Home Assistant custom integration
that implements a conversation entity.

## Optional: make Needle the selected conversation agent

Use this path only if a compatible `needle_conversation` custom integration is
available or you are developing one.

The add-on alone cannot register itself as an Assist conversation agent because
Home Assistant add-ons and Home Assistant integrations are different
extension types.

A compatible integration must:

1. register a Home Assistant conversation entity;
2. accept Assist conversation input;
3. build only allowlisted Needle tools;
4. call this add-on's `/complete` endpoint;
5. validate the complete response;
6. preserve Home Assistant user context;
7. call fixed intents, scripts, or services;
8. return a Home Assistant intent response;
9. store and expire pending confirmations;
10. handle unavailable, busy, and timed-out inference safely.

After installing such an integration:

1. Restart Home Assistant.
2. Open **Settings → Devices & services**.
3. Add the Needle conversation integration.
4. Configure the URL as
   `http://HOME_ASSISTANT_LAN_IP:7860`.
5. Verify that its connection test reads `GET /model`.
6. Open **Settings → Voice assistants**.
7. Edit the desired assistant.
8. Select the Needle conversation entity as its conversation agent.
9. Keep the existing speech-to-text and text-to-speech providers.
10. Test harmless commands before exposing more tools.

See the **Full Assist integration** section in `DOCS.md` for implementation,
validation, context propagation, confirmation, and response-design
requirements.

## Automatically expose a large installation

The YAML setup above is intentionally explicit and small. If your Home
Assistant instance contains many sensors and actors, do not manually create a
Needle function for every entity. Install or implement a companion Home
Assistant custom integration that creates the catalog automatically.

The add-on cannot perform this discovery itself. It runs outside Home
Assistant Core and cannot directly inspect Home Assistant's entity, device,
area, service, or Assist-exposure registries.

### Discovery source

Use Home Assistant's existing exposure controls as the source of truth:

1. Open **Settings → Voice assistants**.
2. Open the **Expose** configuration.
3. Expose only entities that Needle may read or control.
4. Have the companion integration read that filtered catalog.
5. Rebuild its internal catalog when registries or exposure settings change.

This avoids maintaining a second entity allowlist while preserving a visible
Home Assistant control for granting and revoking access. Entity names, aliases,
areas, and current states can contain private information; document that they
are sent to the locally running Needle process.

### Generate domain-level tools

Prefer a small set of tools organized by capability:

- `set_light(light_or_area, state, brightness)`;
- `set_cover(cover_or_area, action, position)`;
- `set_climate(climate_or_area, temperature, mode)`;
- `activate_scene(scene)`;
- `run_script(script)`;
- `get_entity_state(entity)`;
- `get_area_state(area, domain)`.

Populate enum values from the currently exposed catalog. Keep the mapping from
each enum value to its actual entity ID inside the integration. Do not permit
Needle to supply an arbitrary entity ID.

For example, the generated light tool can use:

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

Sensors generally belong in read-only state-query tools or selected request
context rather than becoming separate executable functions. A compact
domain-level catalog also gives Needle fewer overlapping functions to
distinguish than one tool per entity.

### Validate and authorize every call

The integration must treat Needle's response as untrusted. Before execution,
verify that:

1. the function is in the integration's allowlist;
2. the target is still exposed to Assist;
3. arguments match the expected names and types;
4. enums and numeric ranges are valid;
5. the operation is valid for the target domain;
6. the originating Home Assistant user context is authorized;
7. confidence meets the configured threshold;
8. any required confirmation is valid and unexpired.

Use the context from the Assist request when calling Home Assistant. Do not
replace it with an unrestricted system context.

### Never expose an unrestricted service caller

Do not generate a catch-all function such as:

```text
call_service(domain, service, entity_id, data)
```

That design would let model output choose arbitrary services, targets, and
data. JSON schemas and confidence scores improve structured output but are not
authorization boundaries.

Automatically expose harmless sensors, lights, selected scenes and scripts,
media players, and bounded climate capabilities as appropriate. Require
explicit confirmation—or refuse voice execution—for locks, exterior doors,
garage doors, covers, alarms, purchases, deletion, security changes, and
externally visible messages.

The resulting scalable path is:

```text
Assist request
  → companion Needle conversation integration
  → read Assist-exposed entities and areas
  → generate compact domain-level schemas
  → Needle POST /complete
  → validate output and Home Assistant context
  → confirm sensitive operation when required
  → execute a fixed Home Assistant action
  → return deterministic speech
```

This provides broad automatic coverage without granting unrestricted access to
Home Assistant's complete service registry.

## Troubleshooting checklist

### Assist does not recognize “Ask Needle”

- Confirm the custom sentence file path and language.
- Confirm that the Assist pipeline uses the same language.
- Confirm the intent and slot names match exactly.
- Check the Home Assistant configuration.
- Restart Home Assistant.
- Review Home Assistant logs.

### Assist recognizes the sentence but no light changes

Test each layer independently:

1. `GET /model`;
2. the REST command;
3. the script;
4. typed Assist;
5. spoken Assist.

The first failing layer identifies where to troubleshoot.

### Needle times out

- Check the add-on log.
- Wait for model initialization.
- Keep the REST timeout at 120 seconds while testing.
- Avoid sending simultaneous commands.
- Check available memory and CPU.

### Needle selects the wrong room or action

- Make tool and argument descriptions more explicit.
- Keep enum values short and distinct.
- Add natural aliases to descriptions.
- Keep the tool list small.
- Raise the confidence threshold.
- Never bypass the allowlist because one prompt failed.

### Assist speaks success when the script rejected the call

The built-in `intent_script` example returns a simple dispatch
acknowledgement. For verified outcome-specific speech, implement a companion
conversation integration that waits for dispatch and returns the appropriate
intent response.

## Security checklist

Before considering the setup complete:

- [ ] Port `7860` is reachable only from trusted networks.
- [ ] Port `7860` is not forwarded by the router.
- [ ] Every Needle function name is allowlisted.
- [ ] Automatically discovered targets are explicitly exposed to Assist.
- [ ] Every argument is validated after inference.
- [ ] Model output cannot choose a service or entity ID directly.
- [ ] No unrestricted `call_service`-style tool is available.
- [ ] Sensitive operations are unavailable or require confirmation.
- [ ] No API keys or secrets appear in prompts or schemas.
- [ ] Invalid and low-confidence calls stop without changing state.
- [ ] Each configured action has been tested independently.