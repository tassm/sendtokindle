# Design diagrams

UML diagrams for sendtokindle. The PlantUML sources (`.puml`) are the source of truth. The `.svg` files are generated from them.

## Component diagram

Shows how the system is structured: the Python modules inside the container, the `mcp` SDK and Pandoc they depend on, and the external parts (Claude client, mounted folder, env file, Gmail SMTP, Amazon and the Kindle).

![Component diagram](components.svg)

Source: [components.puml](components.puml)

## Activity diagram

Shows how data flows through a `send_markdown` or `send_pdf` call, with one swimlane per participant. Pink actions are tool errors; each one is returned to Claude with `isError: true`. After Gmail accepts the message, Amazon delivers it to the Kindle asynchronously, in parallel with the tool returning its result.

![Activity diagram](activity.svg)

Source: [activity.puml](activity.puml)

## Regenerating

```bash
docker run --rm -v "$PWD/docs:/docs" plantuml/plantuml -tsvg /docs/activity.puml /docs/components.puml
```
