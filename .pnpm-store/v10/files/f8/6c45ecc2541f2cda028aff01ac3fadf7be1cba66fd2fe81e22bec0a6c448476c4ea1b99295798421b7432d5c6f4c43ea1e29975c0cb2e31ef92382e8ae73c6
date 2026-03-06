<script>import { getContext } from "svelte";
import { twMerge } from "tailwind-merge";
export let href = "";
export let activeClass = void 0;
export let nonActiveClass = void 0;
const context = getContext("navbarContext") ?? {};
const activeUrlStore = getContext("activeUrl");
let navUrl = "";
activeUrlStore.subscribe((value) => {
  navUrl = value;
});
$: active = navUrl ? href === navUrl : false;
$: liClass = twMerge("block py-2 pe-4 ps-3 md:p-0 rounded-sm md:border-0", active ? activeClass ?? context.activeClass : nonActiveClass ?? context.nonActiveClass, $$props.class);
</script>

<li>
  <svelte:element
    this={href ? 'a' : 'div'}
    role={href ? 'link' : 'presentation'}
    {href}
    {...$$restProps}
    on:blur
    on:change
    on:click
    on:focus
    on:keydown
    on:keypress
    on:keyup
    on:mouseenter
    on:mouseleave
    on:mouseover
    class={liClass}
  >
    <slot />
  </svelte:element>
</li>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let href: $$Props['href'] = '';
@prop export let activeClass: $$Props['activeClass'] = undefined;
@prop export let nonActiveClass: $$Props['nonActiveClass'] = undefined;
-->
