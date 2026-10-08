# Needle — Home Assistant add-on

Run [Cactus Compute Needle](https://github.com/cactus-compute/needle) locally
on Home Assistant as a lightweight, schema-constrained LLM tool router.

This add-on provides a Needle server, web playground, and HTTP API
(`GET /model`, `POST /complete`, and `POST /reset`). The add-on by itself
does **not** register a Home Assistant Assist conversation agent.

## Use Needle with Home Assistant Assist

Pair this add-on with **[Needle LLM for Home Assistant](https://github.com/BelphegorPrime/ha-needle-llm)**,
the separate HACS custom integration that connects Needle to Home Assistant's
native Assist LLM tools.

```text
LLM conversation agent
  -> Needle LLM integration
  -> Needle add-on (selects a tool)
  -> integration validates the selected tool
  -> native Home Assistant Assist tool executes
```

The integration exposes a selectable LLM API, dynamically discovers native
Assist tools, and respects Home Assistant's entity exposure and tool validation.

## Installation

1. Add the [Home Assistant add-on collection](https://github.com/BelphegorPrime/ha-addon-collection)
   to your Home Assistant add-on store.
2. Install and start the **Needle** add-on (available for `amd64` and `aarch64`).
3. Follow the [add-on documentation](DOCS.md) to configure its local HTTP endpoint.
4. If using an LLM conversation agent, install and configure the
   [Needle LLM custom integration](https://github.com/BelphegorPrime/ha-needle-llm).

For direct REST calls, example automations, configuration and troubleshooting,
see the [full add-on documentation](DOCS.md). For an alternative setup using
Home Assistant's built-in custom sentences rather than an LLM conversation
agent, see the [manual Assist setup guide](FULL_ASSIST_SETUP.md).
