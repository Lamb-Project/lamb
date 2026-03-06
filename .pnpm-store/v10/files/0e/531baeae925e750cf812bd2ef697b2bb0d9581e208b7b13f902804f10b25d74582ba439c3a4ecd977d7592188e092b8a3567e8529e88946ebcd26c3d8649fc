<script context="module"></script>

<script>import { setContext } from "svelte";
import { twMerge } from "tailwind-merge";
import { writable } from "svelte/store";
export let activeUrl = "";
export let asideClass = "w-64";
export let nonActiveClass = "flex items-center p-2 text-base font-normal text-gray-900 rounded-lg dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700";
export let activeClass = "flex items-center p-2 text-base font-normal text-gray-900 bg-gray-200 dark:bg-gray-700 rounded-lg dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700";
export let ariaLabel = "Sidebar";
const activeUrlStore = writable("");
setContext("sidebarContext", { activeClass, nonActiveClass });
$: {
  activeUrlStore.set(activeUrl);
}
setContext("activeUrl", activeUrlStore);
</script>

<aside {...$$restProps} class={twMerge(asideClass, $$props.class)} aria-label={ariaLabel}>
  <slot />
</aside>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let activeUrl: NonNullable<$$Props['activeUrl']> = '';
@prop export let asideClass: $$Props['asideClass'] = 'w-64';
@prop export let nonActiveClass: NonNullable<$$Props['nonActiveClass']> = 'flex items-center p-2 text-base font-normal text-gray-900 rounded-lg dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700';
@prop export let activeClass: NonNullable<$$Props['activeClass']> = 'flex items-center p-2 text-base font-normal text-gray-900 bg-gray-200 dark:bg-gray-700 rounded-lg dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700';
@prop export let ariaLabel: $$Props['ariaLabel'] = 'Sidebar';
-->
