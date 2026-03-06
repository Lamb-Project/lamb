<script context="module">import { writable } from "svelte/store";
</script>

<script>import Frame from "../utils/Frame.svelte";
import { twMerge } from "tailwind-merge";
import { setContext } from "svelte";
export let multiple = false;
export let flush = false;
export let activeClass = "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-800";
export let inactiveClass = "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800";
export let defaultClass = "text-gray-500 dark:text-gray-400";
export let classActive = "";
export let classInactive = "";
const ctx = {
  flush,
  activeClass: twMerge(activeClass, classActive),
  inactiveClass: twMerge(inactiveClass, classInactive),
  selected: multiple ? void 0 : writable()
};
setContext("ctx", ctx);
let frameClass;
$: frameClass = twMerge(defaultClass, $$props.class);
</script>

<Frame {...$$restProps} class={frameClass} color="none">
  <slot />
</Frame>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let multiple: $$Props['multiple'] = false;
@prop export let flush: $$Props['flush'] = false;
@prop export let activeClass: $$Props['activeClass'] = 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-800';
@prop export let inactiveClass: $$Props['inactiveClass'] = 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800';
@prop export let defaultClass: $$Props['defaultClass'] = 'text-gray-500 dark:text-gray-400';
@prop export let classActive: $$Props['classActive'] = '';
@prop export let classInactive: $$Props['classInactive'] = '';
-->
