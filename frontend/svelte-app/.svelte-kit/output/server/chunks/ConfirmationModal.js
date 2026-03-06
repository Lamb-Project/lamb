import { c as store_get, a as attr_class, s as stringify, b as attr, u as unsubscribe_stores, d as bind_props } from "./index2.js";
import "./i18n.js";
import { $ as $locale, a as $format } from "./runtime.js";
import { e as escape_html } from "./context.js";
function ConfirmationModal($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let {
      isOpen = false,
      isLoading = false,
      title = "",
      message = "",
      confirmText = "",
      cancelText = "",
      variant = "danger",
      // 'danger' | 'warning' | 'info'
      onconfirm = () => {
      },
      oncancel = () => {
      }
    } = $$props;
    let localeLoaded = !!store_get($$store_subs ??= {}, "$locale", $locale);
    const variantStyles = {
      danger: {
        headerBg: "bg-red-50",
        headerBorder: "border-red-200",
        iconColor: "text-red-600",
        titleColor: "text-red-900",
        confirmBg: "bg-red-600 hover:bg-red-700",
        confirmRing: "focus:ring-red-500"
      },
      warning: {
        headerBg: "bg-yellow-50",
        headerBorder: "border-yellow-200",
        iconColor: "text-yellow-600",
        titleColor: "text-yellow-900",
        confirmBg: "bg-yellow-600 hover:bg-yellow-700",
        confirmRing: "focus:ring-yellow-500"
      },
      info: {
        headerBg: "bg-blue-50",
        headerBorder: "border-blue-200",
        iconColor: "text-blue-600",
        titleColor: "text-blue-900",
        confirmBg: "bg-blue-600 hover:bg-blue-700",
        confirmRing: "focus:ring-blue-500"
      }
    };
    let styles = variantStyles[variant] || variantStyles.danger;
    let displayTitle = title || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.confirm", { default: "Confirm" }) : "Confirm");
    let displayConfirmText = confirmText || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.confirm", { default: "Confirm" }) : "Confirm");
    let displayCancelText = cancelText || (localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.cancel", { default: "Cancel" }) : "Cancel");
    if (isOpen) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity z-40" aria-hidden="true"></div> <div class="fixed inset-0 z-50 flex items-center justify-center p-4"><div class="relative bg-white rounded-lg shadow-xl overflow-hidden max-w-md w-full border border-gray-300 mx-2" role="dialog" aria-modal="true" aria-labelledby="modal-title-confirm"><div${attr_class(`px-4 py-3 sm:px-6 border-b flex items-center ${stringify(styles.headerBg)} ${stringify(styles.headerBorder)}`)}>`);
      if (variant === "danger") {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<svg${attr_class(`h-6 w-6 mr-2 ${stringify(styles.iconColor)}`)} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"></path></svg>`);
      } else {
        $$renderer2.push("<!--[!-->");
        if (variant === "warning") {
          $$renderer2.push("<!--[-->");
          $$renderer2.push(`<svg${attr_class(`h-6 w-6 mr-2 ${stringify(styles.iconColor)}`)} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"></path></svg>`);
        } else {
          $$renderer2.push("<!--[!-->");
          $$renderer2.push(`<svg${attr_class(`h-6 w-6 mr-2 ${stringify(styles.iconColor)}`)} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"></path></svg>`);
        }
        $$renderer2.push(`<!--]-->`);
      }
      $$renderer2.push(`<!--]--> <h3${attr_class(`text-lg leading-6 font-medium ${stringify(styles.titleColor)}`)} id="modal-title-confirm">${escape_html(displayTitle)}</h3></div> <div class="px-4 py-5 sm:p-6"><p class="text-sm text-gray-700 whitespace-pre-line break-words">${escape_html(message)}</p> `);
      if (isLoading) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<p class="text-sm text-gray-500 mt-2 flex items-center"><svg class="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> ${escape_html(localeLoaded ? store_get($$store_subs ??= {}, "$_", $format)("common.processing", { default: "Processing..." }) : "Processing...")}</p>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--></div> <div class="bg-gray-50 px-4 py-3 sm:px-6 flex flex-col-reverse gap-2 sm:flex-row-reverse border-t border-gray-200"><button type="button"${attr_class(`w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 ${stringify(styles.confirmBg)} ${stringify(styles.confirmRing)}`)}${attr("disabled", isLoading, true)} style="min-width:100px">`);
      if (isLoading) {
        $$renderer2.push("<!--[-->");
        $$renderer2.push(`<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`);
      } else {
        $$renderer2.push("<!--[!-->");
      }
      $$renderer2.push(`<!--]--> ${escape_html(displayConfirmText)}</button> <button type="button" class="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"${attr("disabled", isLoading, true)} style="min-width:100px">${escape_html(displayCancelText)}</button></div></div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]-->`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
    bind_props($$props, { isOpen, isLoading });
  });
}
export {
  ConfirmationModal as C
};
