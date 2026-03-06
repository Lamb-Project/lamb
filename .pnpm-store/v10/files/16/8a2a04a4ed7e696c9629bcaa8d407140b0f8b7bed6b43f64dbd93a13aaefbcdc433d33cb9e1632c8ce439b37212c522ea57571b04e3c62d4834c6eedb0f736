<script>import Wrapper from "../utils/Wrapper.svelte";
import { twMerge } from "tailwind-merge";
import { getContext } from "svelte";
export let defaultClass = "font-medium py-2 px-4 text-sm hover:bg-gray-100 dark:hover:bg-gray-600";
export let href = void 0;
export let activeClass = void 0;
const context = getContext("DropdownType") ?? {};
const activeUrlStore = getContext("activeUrl");
let sidebarUrl = "";
activeUrlStore.subscribe((value) => {
  sidebarUrl = value;
});
$: active = sidebarUrl ? href === sidebarUrl : false;
$: liClass = twMerge(defaultClass, href ? "block" : "w-full text-left", active && (activeClass ?? context.activeClass), $$props.class);
let wrap = true;
function init(node) {
  wrap = node.parentElement?.tagName === "UL";
}
</script>

<Wrapper tag="li" show={wrap} use={init}>
  <svelte:element this={href ? 'a' : 'button'} {href} type={href ? undefined : 'button'} role={href ? 'link' : 'button'} {...$$restProps} class={liClass} on:click on:change on:keydown on:keyup on:focus on:blur on:mouseenter on:mouseleave>
    <slot />
  </svelte:element>
</Wrapper>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let defaultClass: $$Props['defaultClass'] = 'font-medium py-2 px-4 text-sm hover:bg-gray-100 dark:hover:bg-gray-600';
@prop export let href: $$Props['href'] = undefined;
@prop export let activeClass: $$Props['activeClass'] = undefined;
@prop export let active: boolean = false;
-->
