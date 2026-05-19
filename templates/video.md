<%*
const creator = await tp.system.prompt("Creator slug (e.g. creator-name, channel-name)");
const title = await tp.system.prompt("Title slug (e.g. talk-title, video-topic)");
const url = await tp.system.prompt("Video URL");
const filename = `video-${creator}-${title}`;
await tp.file.move(`/raw/web-clippings/${filename}`);
-%>
**URL:** <% url %>
**Creator:** 
**Duration:** 
**Date watched:** <% tp.date.now("YYYY-MM-DD") %>

## Key timestamps
_Copy shareable `t=XXs` links for the moments that struck you._
- [t=] <% tp.file.cursor() %>

## One-liners (verbatim or paraphrased)
- 

## My response / reflection
- 

## Open threads
- 
