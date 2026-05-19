<%*
const date = tp.date.now("YYYY-MM-DD");
await tp.file.move(`/raw/captures/daily/${date} - Daily`);
-%>

- [<% tp.date.now("HH:mm") %>] <% tp.file.cursor() %>
