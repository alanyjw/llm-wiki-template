<%*
const date = tp.date.now("YYYY-MM-DD");
const source = await tp.system.prompt("Source (e.g. book title, essay, author)");
const filename = `${date} - Reading - ${source}`;
await tp.file.move(`/raw/captures/daily/${filename}`);
-%>
**Source:** <% source %>
**Location:** 

## Passage
_The excerpt that struck you. Copy it out in full — the slowdown is the point; a paraphrase loses what caught you._

<% tp.file.cursor() %>

## What I notice
_Plain reading first. What is the author actually claiming? What surprised you, or cut against something you already believe?_

1. 

## What this requires of me
_The turn from reading to doing. One concrete thing — in your work, your relationships, your craft, or how you think._

1. 

## My response
_Write back to it in your own words: argue, agree, extend. This is the part that makes the note worth re-reading months later._

