import * as universal from '../entries/pages/_layout.js';

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export { universal };
export const universal_id = "src/routes/+layout.js";
export const imports = ["app/immutable/nodes/0.D0pNu9UO.js","app/immutable/chunks/CKJeDt6v.js","app/immutable/chunks/BGLSpct9.js","app/immutable/chunks/DhHERQ0H.js","app/immutable/chunks/Lv6X1L9C.js","app/immutable/chunks/DmsL5u-h.js","app/immutable/chunks/4IuUw14A.js","app/immutable/chunks/Ceiogtv-.js","app/immutable/chunks/Ck05D3r0.js","app/immutable/chunks/Bt-ccFBx.js","app/immutable/chunks/B9ygI19o.js"];
export const stylesheets = ["app/immutable/assets/0.CNNRFB-t.css"];
export const fonts = [];
