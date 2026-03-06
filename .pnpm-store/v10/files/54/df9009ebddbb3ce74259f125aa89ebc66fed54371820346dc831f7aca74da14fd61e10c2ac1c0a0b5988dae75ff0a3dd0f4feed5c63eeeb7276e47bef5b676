<script>import { getContext } from "svelte";
import { twMerge } from "tailwind-merge";
export let action = () => {
};
export let params = {};
export let href = "";
export let label = "";
export let spanClass = "ms-3";
export let activeClass = void 0;
export let nonActiveClass = void 0;
const context = getContext("sidebarContext") ?? {};
const activeUrlStore = getContext("activeUrl");
let sidebarUrl = "";
activeUrlStore.subscribe((value) => {
  sidebarUrl = value;
});
$: active = sidebarUrl ? href === sidebarUrl : false;
$: aClass = twMerge(active ? activeClass ?? context.activeClass : nonActiveClass ?? context.nonActiveClass, $$props.class);
</script>

<li>
  <a {...$$restProps} {href} use:action={params} on:blur on:click on:focus on:keydown on:keypress on:keyup on:mouseenter on:mouseleave on:mouseover class={aClass}>
    <slot name="icon" />
    <span class={spanClass}>{label}</span>
    {#if $$slots.subtext}
      <slot name="subtext" />
    {/if}
  </a>
</li>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let action: NonNullable<$$Props['action']> = () => {};
@prop export let params: $$Props['params'] = {};
@prop export let href: $$Props['href'] = '';
@prop export let label: $$Props['label'] = '';
@prop export let spanClass: $$Props['spanClass'] = 'ms-3';
@prop export let activeClass: $$Props['activeClass'] = undefined;
@prop export let nonActiveClass: $$Props['nonActiveClass'] = undefined;
-->
