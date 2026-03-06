import { s as setupI18n } from "../../chunks/i18n.js";
import { w as waitLocale } from "../../chunks/runtime.js";
const load = async () => {
  console.log("Running i18n setup in +layout.js load...");
  setupI18n();
  await waitLocale();
  return {};
};
export {
  load
};
