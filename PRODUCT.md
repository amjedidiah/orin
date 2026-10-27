# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Power users of AI: people who use two or more AI models or assistants every day, pay for some of them, and move between phone and laptop.
Their job in the moment is getting a task done without first deciding which AI to use and without re-explaining themselves to it.
The demo persona is Ada, an indie developer in Lagos launching a side project, but the product is not limited to developers.

## Product Purpose

You talk to Orin.
Orin picks the best-fit AI model or agent for each task, sends the work with everything it needs to know, and brings the answer back, falling back to a free open-weights model when no paid one is available.
Success: the user asks once, in one place, and never has to choose a tool or re-explain context.

## Positioning

Orin is a router with a memory, not another chatbot.
Every answer shows where it went and why (target, reason, alternatives, fallback steps, who served it), and one memory and prompt history follows the user across every model and agent.
Meta's Muse models do the routing and the model work; Muse Spark Open is the free fallback.

## Operating Context

- Used in short bursts throughout the day, on phone (installable web app, voice input planned) and on desktop.
- Hosted as a personal instance protected by an owner token; a public demo instance with a made-up persona exists for hackathon judges.
- Evaluated in a 3-minute demo video for the Meta Global AI Developer Hackathon (deadline Nov 4, 2026).

## Capabilities and Constraints

- Targets: Meta models now (Muse Spark, Muse Spark Open, Muse Image); agents over MCP (Cursor, plus Claude, Grok or ChatGPT where their plans allow) from stage 2.
- Every reply streams in; image requests return inline images.
- Routing must stay transparent: the user can always see the target, the reason, alternatives, any fallback, and whether a free model answered.
- Grok Bot and dots are "designed for, not yet tested"; never claim otherwise in the UI.

## Brand Commitments

- Name: Orin, from the Yoruba word _orín_ (song, harmony): many voices, one coherent melody. The identity may draw on this meaning.
- Voice: calm and precise like a trustworthy instrument, with some warmth. Short, factual, transparent about every routing decision, but human rather than robotic.
- No Meta, Muse, Llama or vendor logos anywhere; models and vendors are named in plain text only.
- Only openly licensed fonts (e.g. SIL OFL) and icons (e.g. Lucide, ISC).

## Evidence on Hand

- No testimonials, customers, usage numbers or press exist. Do not fabricate any.
- Real measurements that may be shown when current: router accuracy from `backend/evals/router_cases.json` (10/10 on Oct 26, 2026), test counts from CI.

## Product Principles

1. Ask once: the user never picks the tool or repeats context.
2. Show the routing: every answer says where it went and why.
3. Never strand the user: when a paid option is unavailable, fall back and say so.
4. Honest claims only: untested integrations are labelled as such.

## Accessibility & Inclusion

WCAG 2.2 AA: contrast, full keyboard use, screen-reader support for streamed answers and routing details.
