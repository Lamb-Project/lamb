import { beforeEach, it, expect, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
import { getConfig, getApiUrl, getLambApiUrl } from './config.js';
beforeEach(() => { delete window.LAMB_CONFIG; });
it('uses relative routes without runtime config', () => {
 expect(getApiUrl('assistant/defaults')).toBe('/creator/assistant/defaults');
 expect(getLambApiUrl('/lamb/v1/completions/list')).toBe('/lamb/v1/completions/list');
});
it('merges partial config and follows the Creator host and prefix', () => {
 window.LAMB_CONFIG = {api:{baseUrl:'https://example.test/heavy/creator/'},features:{enableLibraries:false}};
 expect(getLambApiUrl('/lamb/v1/completions/list')).toBe('https://example.test/heavy/lamb/v1/completions/list');
 expect(getConfig().features.enableOpenWebUi).toBe(true);
 expect(getConfig().features.enableLibraries).toBe(false);
});
it('retains explicitly configured split-server routes', () => {
 window.LAMB_CONFIG = {api:{baseUrl:'https://creator.test/creator',lambServer:'https://core.test/'}};
 expect(getApiUrl('assistant/capabilities')).toBe('https://creator.test/creator/assistant/capabilities');
 expect(getLambApiUrl('lamb/v1/completions/list')).toBe('https://core.test/lamb/v1/completions/list');
});
it('accepts an explicit empty same-origin server', () => {
 window.LAMB_CONFIG = {api:{lambServer:''}};
 expect(getLambApiUrl('lamb/v1/completions/list')).toBe('/lamb/v1/completions/list');
});
