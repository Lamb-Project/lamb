<script context="module"></script>

<script>import { setContext } from "svelte";
import { writable } from "svelte/store";
import { twMerge } from "tailwind-merge";
export let activeUrl = "";
export let position = "fixed";
export let navType = "default";
export let outerClass = "w-full z-50 border-gray-200 dark:bg-gray-700 dark:border-gray-600";
export let innerClass = "grid h-full max-w-lg mx-auto";
export let activeClass = "text-primary-700 dark:text-primary-700 hover:text-primary-900 dark:hover:text-primary-900";
export let classActive = "";
export let classOuter = "";
export let classInner = "";
let activeCls = "";
const activeUrlStore = writable("");
activeCls = twMerge(activeClass, classActive);
setContext("navType", navType);
setContext("bottomNavType", { activeClass: activeCls });
$: {
  activeUrlStore.set(activeUrl);
}
setContext("activeUrl", activeUrlStore);
const outerDivClasses = {
  default: "bottom-0 start-0 h-16 bg-white border-t",
  border: "bottom-0 start-0 h-16 bg-white border-t",
  application: "h-16 max-w-lg -translate-x-1/2 rtl:translate-x-1/2 bg-white border rounded-full bottom-4 start-1/2",
  pagination: "bottom-0 h-16 -translate-x-1/2 rtl:translate-x-1/2 bg-white border-t start-1/2",
  group: "bottom-0 -translate-x-1/2 rtl:translate-x-1/2 bg-white border-t start-1/2",
  card: "bottom-0 start-0 h-16 bg-white border-t",
  meeting: "bottom-0 start-0 grid h-16 grid-cols-1 px-8 bg-white border-t md:grid-cols-3",
  video: "bottom-0 start-0 grid h-24 grid-cols-1 px-8 bg-white border-t md:grid-cols-3"
};
const innerDivClasses = {
  default: "",
  border: "",
  application: "",
  pagination: "",
  group: "",
  card: "",
  meeting: "flex items-center justify-center mx-auto",
  video: "flex items-center w-full"
};
$: outerCls = twMerge(position, outerClass, outerDivClasses[navType], classOuter);
$: innerCls = twMerge(innerClass, innerDivClasses[navType], classInner);
</script>

<div {...$$restProps} class={outerCls}>
  <slot name="header" />
  <div class={innerCls}>
    <slot />
  </div>
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let activeUrl: $$Props['activeUrl'] = '';
@prop export let position: $$Props['position'] = 'fixed';
@prop export let navType: NonNullable<$$Props['navType']> = 'default';
@prop export let outerClass: $$Props['outerClass'] = 'w-full z-50 border-gray-200 dark:bg-gray-700 dark:border-gray-600';
@prop export let innerClass: $$Props['innerClass'] = 'grid h-full max-w-lg mx-auto';
@prop export let activeClass: $$Props['activeClass'] = 'text-primary-700 dark:text-primary-700 hover:text-primary-900 dark:hover:text-primary-900';
@prop export let classActive: $$Props['classActive'] = '';
@prop export let classOuter: $$Props['classOuter'] = '';
@prop export let classInner: $$Props['classInner'] = '';
-->
