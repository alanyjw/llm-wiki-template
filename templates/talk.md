<%*
const date = tp.date.now("YYYY-MM-DD");
const speaker = await tp.system.prompt("Speaker (e.g. Alice Chen, conference keynote, podcast guest)");
const title = await tp.system.prompt("Talk / session title");
// Talks you attended file alongside meetings — same dated folder, same "YYYY-MM-DD - Title" shape.
const filename = `${date} - ${speaker} - ${title}`;
await tp.file.move(`/raw/meetings/${filename}`);
-%>
**Speaker:** <% speaker %>
**Event:** 
**Format:** 
**Date attended:** <% tp.date.now("YYYY-MM-DD") %>

## Notes
_Live and rough. Claims, examples, numbers, and anything you want verbatim later — a talk is not re-watchable, so capture it now._
- <% tp.file.cursor() %>

## My reflection
_Written after the talk, not during. What landed, what you disagree with, what it changes about how you work._
- 

## Open threads
_Questions the talk opened but didn't close — the follow-ups worth chasing._
- 
