/** Parse complete directives; hide unfinished canvas markup while streaming. */
export function splitCanvasContent(text = '') {
 const events = [];
 const clean = text.replace(/<<<CANVAS(?:\s+title="([^"]*)")?>>>([\s\S]*?)<<<END_CANVAS>>>|<<<CANVAS_CLEAR>>>/g, (all, title, content, offset) => {
  events.push(all === '<<<CANVAS_CLEAR>>>' ? null : {title: title || '', content: content.trim(), offset});
  return '';
 }).replace(/<<<CANVAS[\s\S]*$/, '').trim();
 return {text: clean, events};
}
export function canvasFromMessages(messages) {
 let canvas = null;
 messages.forEach((message, index) => {
  if (message.role !== 'assistant') return;
  for (const event of splitCanvasContent(message.content).events) {
   canvas = event ? {...event, key: `${index}:${event.offset}:${event.content}`} : null;
  }
 });
 return canvas;
}
