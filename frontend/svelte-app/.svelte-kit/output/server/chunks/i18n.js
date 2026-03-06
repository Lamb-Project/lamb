import { r as registerLocaleLoader, i as init } from "./runtime.js";
const __variableDynamicImportRuntimeHelper = (glob, path, segs) => {
  const v = glob[path];
  if (v) {
    return typeof v === "function" ? v() : Promise.resolve(v);
  }
  return new Promise((_, reject) => {
    (typeof queueMicrotask === "function" ? queueMicrotask : setTimeout)(
      reject.bind(
        null,
        new Error(
          "Unknown variable dynamic import: " + path + (path.split("/").length !== segs ? ". Note that variables only represent file names one level deep." : "")
        )
      )
    );
  });
};
let isInitialized = false;
const supportedLocales = ["en", "es", "ca", "eu"];
const fallbackLocale = "en";
supportedLocales.forEach((lang) => {
  registerLocaleLoader(lang, () => __variableDynamicImportRuntimeHelper(/* @__PURE__ */ Object.assign({ "./locales/ca.json": () => import("./ca.js"), "./locales/en.json": () => import("./en.js"), "./locales/es.json": () => import("./es.js"), "./locales/eu.json": () => import("./eu.js") }), `./locales/${lang}.json`, 3));
});
function getInitialLocale() {
  {
    return fallbackLocale;
  }
}
function setupI18n() {
  if (isInitialized) return;
  const initial = getInitialLocale();
  console.log(`Initializing svelte-i18n with initial locale: ${initial}, fallback: ${fallbackLocale}`);
  init({
    fallbackLocale,
    initialLocale: initial
  });
  isInitialized = true;
}
export {
  setupI18n as s
};
