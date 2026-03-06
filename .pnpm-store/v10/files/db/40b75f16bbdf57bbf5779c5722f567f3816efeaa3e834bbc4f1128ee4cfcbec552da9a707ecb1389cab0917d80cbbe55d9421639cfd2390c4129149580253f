<script>import { getContext } from "svelte";
import { twMerge } from "tailwind-merge";
export let btnName = "";
export let appBtnPosition = "middle";
export let activeClass = void 0;
export let href = "";
export let exact = true;
export let spanClass = "";
const navType = getContext("navType");
const context = getContext("bottomNavType") ?? {};
const activeUrlStore = getContext("activeUrl");
let navUrl = "";
activeUrlStore.subscribe((value) => {
  navUrl = value;
});
$: active = navUrl && exact ? href === navUrl : navUrl ? navUrl.startsWith(href) : false;
const btnClasses = {
  default: "inline-flex flex-col items-center justify-center px-5 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 group",
  border: "inline-flex flex-col items-center justify-center px-5 border-gray-200 border-x text-gray-500 dark:text-gray-400  hover:bg-gray-50 dark:hover:bg-gray-800 group dark:border-gray-600",
  application: "",
  pagination: "inline-flex flex-col items-center justify-center px-5 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 group",
  group: "inline-flex flex-col items-center justify-center p-4 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 group",
  card: "inline-flex flex-col items-center justify-center px-5 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 group",
  meeting: "",
  video: ""
};
const spanClasses = {
  default: "text-sm text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500",
  border: "text-sm text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500",
  application: "sr-only",
  pagination: "sr-only",
  group: "sr-only",
  card: "text-sm text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-500",
  meeting: "",
  video: ""
};
const appBtnClasses = {
  left: "inline-flex flex-col items-center justify-center px-5 rounded-s-full hover:bg-gray-50 dark:hover:bg-gray-800 group",
  middle: "inline-flex flex-col items-center justify-center px-5 hover:bg-gray-50 dark:hover:bg-gray-800 group",
  right: "inline-flex flex-col items-center justify-center px-5 rounded-e-full hover:bg-gray-50 dark:hover:bg-gray-800 group"
};
let btnClass;
$: btnClass = twMerge(btnClasses[navType], appBtnClasses[appBtnPosition], active && (activeClass ?? context.activeClass), $$props.btnClass);
let spanCls;
$: spanCls = twMerge(spanClasses[navType], active && (activeClass ?? context.activeClass), spanClass);
</script>

<svelte:element this={href ? 'a' : 'button'} aria-label={btnName} {href} role={href ? 'link' : 'button'} {...$$restProps} class={btnClass} on:click on:change on:keydown on:keyup on:focus on:blur on:mouseenter on:mouseleave>
  <slot />
  <span class={spanCls}>{btnName}</span>
</svelte:element>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let btnName: $$Props['btnName'] = '';
@prop export let appBtnPosition: NonNullable<$$Props['appBtnPosition']> = 'middle';
@prop export let activeClass: $$Props['activeClass'] = undefined;
@prop export let href: string = '';
@prop export let exact: $$Props['exact'] = true;
@prop export let spanClass: $$Props['spanClass'] = '';
-->
