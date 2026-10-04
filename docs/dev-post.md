---
title: "Gemma Garage: a local Gemma reads my uncle's scribbled notes and orders the parts"
tags: devchallenge, weekendchallenge, hf26challenge, opensource
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

## What I Built

A small appointment book for a relative who runs a car workshop. He keeps his jobs as scribbles like `cambio aceite motor opel aceite 5w30`, then spends his evenings phoning the parts distributor and chasing customers for the yearly oil change and ITV (the Spanish roadworthiness test).

**Gemma Garage** keeps the scribbles and does the paperwork:

- He types the job the way he would write it on paper. A **local Gemma model** reads it and shows, live, what it understood: the job, the car, the parts and how often it repeats.
- The **business day before** the appointment, the parts are ordered from the distributor (Monday for Tuesday, Friday for Monday). He can review and edit the order first, and failed orders are flagged to retry.
- A **shopping list** groups the parts of the day.
- Repeating jobs trigger a **Telegram reminder** to the customer a week before the year is up.
- When the job is done he types the part prices from the delivery note (they are never stored, because they depend on the distributor), labour comes from his own tariffs, and an **invoice** with VAT is generated.

Everything in the interface is in Spanish because that is what he reads.

## Demo

<!-- Pega aquí el vídeo (docs/media/taller-demo.mp4) o el enlace de YouTube -->

**Typing a note and watching Gemma read it, live:**

![New appointment](https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/01-nueva-cita.gif)

A real capture with `gemma3` running locally through Ollama:

![Gemma interpretation](https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/gemma-interpretation.png)

**Reviewing and sending the order** (with a "Pidiendo recambios…" spinner while it goes out):

![Order](https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/02-pedido.gif)

**Done → invoice.** Part prices typed from the delivery note, labour from his tariffs, live total:

![Invoice](https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/04-factura.gif)

**Tariffs, search and customers**, and the phone view he uses in the workshop:

![Tariffs and search](https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/05-tarifas-busqueda.gif)

<img src="https://raw.githubusercontent.com/antoniahp/gemma-garage/main/docs/media/06-movil.gif" width="260" alt="Mobile view">

All customers, plates and phone numbers in the demo are made up (`python manage.py demo`).

## Code

{% github https://github.com/antoniahp/gemma-garage %}

Django + Postgres (SQLite fallback), server-rendered pages, Django admin for the advanced bits. 48 tests. `python manage.py demo --reset` loads sample data and `python docs/record_demo.py` regenerates every screenshot and video above.

## How I Built It

- **Gemma, locally, via Ollama.** The note goes to `gemma3` with a strict Spanish prompt, two worked examples, `temperature 0` and JSON output. The result is cleaned (no invented viscosities or parts) and checked against a list of known jobs. Responses are cached and the model is kept warm (`keep_alive`) so the live preview is quick.
- **A model that can be wrong has to fail visibly.** The panel says which engine answered ("Entendido con Gemma" or "reglas simples") and why Gemma was not used (not running, timeout, bad JSON). If Ollama is down, a small rule-based parser takes over, so the workshop never stops.
- **Nothing leaves the machine.** Customer names, plates and phone numbers never go to a cloud API. The only outside calls are the distributor order and the Telegram bot he opts into.
- **Boring where it should be.** Order date = previous business day, invoice numbers `YYYY-NNNN`, VAT 21 %, backup/restore with `dumpdata`. The model only interprets text; the schedule and the money are plain code.
- **Built with an AI coding agent**, and recorded by a Playwright script that drives the real app, so the media is regenerated, not mocked.

## Why Does Open Innovation Matter?

A one-person workshop will not send its customers' data to a cloud model, and will not pay per call to read three words about an oil filter. An open-weight model that runs on the laptop already on his desk makes this possible: private, free after the download, and good enough once you give it a narrow job and check its output. Open weights also mean he (or I) can swap the model, read the prompt and fix it when it gets something wrong, which matters more than a bigger model when the notes are in Spanish workshop slang.

## My Agent Session

<!-- Opcional: enlace a la sesión de Claude Code -->

## Prize Categories

**Best Use of Gemma**: Gemma (`gemma3`, local via Ollama) is the core of the app: it turns free-text workshop notes into structured jobs, parts and reminders.
