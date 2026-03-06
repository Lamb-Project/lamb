export * from './components/index.js';
export { authService, configService } from './services/index.js';
export { user, user as userStore, configStore } from './stores/index.js';
export { setupI18n, initI18n, setLocale, locale, _, waitLocale, fallbackLocale, supportedLocales } from './i18n/index.js';
export { VERSION_INFO } from './version.js';
