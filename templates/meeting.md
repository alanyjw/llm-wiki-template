<%*
const date = tp.date.now("YYYY-MM-DD");
const title = await tp.system.prompt("Meeting title (e.g. Chat with Alice, Team huddle, 1-1 with Bob)");
const filename = `${date} - ${title}`;
await tp.file.move(`/raw/meetings/${filename}`);
-%>
**Outcome:** 
**Attendees:** 

## Decisions made
- 

## Open questions
- 

## Action items
- [ ] 

## Notes
- 
