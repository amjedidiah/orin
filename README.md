# Orin

> From the Yoruba word _orín_ (song, harmony). Many voices, one coherent melody.

You talk to Orin. Orin picks the best-fit AI model or agent for each task, sends the work with everything it needs to know, and brings the answer back, falling back to a free model when no paid one is available.

**Status:** in progress.

## What Orin does

- **Holds your context and prompts.** One memory and one prompt history across every model and agent you use, so you never re-explain yourself when you switch.
- **Picks the best-fit model or agent for each task.** Meta's Muse models decide where each task goes and what context it needs. Models answer through Orin. Tasks that need an agent's own tools, such as editing your repository in Cursor, are handed off over MCP; the agent picks them up automatically and reports the result back to Orin.
- **Falls back to a free model.** When no paid model or agent is available, Orin answers with Muse Spark Open, an open-weights model.
- **Works with agents that accept custom MCP servers.** It is designed for persistent agents such as xAI's Grok Bot and OpenAI's dots, but not yet tested with them; what each can do depends on the vendor's plan.

## Progress

| Capability                                                                      | Stage | Status  |
| ------------------------------------------------------------------------------- | ----- | ------- |
| Route each request to the best-fit Meta model and answer through Orin           | 1     | Planned |
| Prompt history for everything that passes through Orin                          | 1     | Planned |
| Free fallback to Muse Spark Open                                                | 1     | Planned |
| Shared memory and prompt history over MCP with connected agents                 | 2     | Planned |
| Agent handoffs with automatic pickup and completion                             | 2     | Planned |
| Memory summaries on open weights and chat history import                        | 3     | Planned |
| Dashboard of models and agents, memory editor, voice input, installable web app | 3     | Planned |

## Built during the Hackathon

Orin is being built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) (Indie Developer track, Oct 26 – Nov 4, 2026). All code in this repository was written during the event; the git history is the record.

## License

[MIT](LICENSE)
