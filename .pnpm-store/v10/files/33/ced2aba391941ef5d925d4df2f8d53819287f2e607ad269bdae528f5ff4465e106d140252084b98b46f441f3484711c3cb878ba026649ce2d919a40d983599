<script>import { twMerge } from "tailwind-merge";
export let spanClass = "block text-sm text-gray-500 sm:text-center dark:text-gray-400";
export let aClass = "hover:underline";
export let year = (/* @__PURE__ */ new Date()).getFullYear();
export let href = "";
export let by = "";
export let target = void 0;
export let copyrightMessage = "All Rights Reserved.";
export let classSpan = "";
export let classA = "";
let spanCls = twMerge(spanClass, classSpan);
let aCls = twMerge(aClass, classA);
</script>

<span class={spanCls}>
  &copy; {year}
  {#if href}
    <a {...$$restProps} {href} {target} class={aCls}>
      {by}
    </a>
  {:else}
    <span class="ms-1">{by}</span>
  {/if}
  {copyrightMessage}
</span>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let spanClass: $$Props['classSpan'] = 'block text-sm text-gray-500 sm:text-center dark:text-gray-400';
@prop export let aClass: $$Props['aClass'] = 'hover:underline';
@prop export let year: $$Props['year'] = new Date().getFullYear();
@prop export let href: $$Props['href'] = '';
@prop export let by: $$Props['by'] = '';
@prop export let target: $$Props['target'] = undefined;
@prop export let copyrightMessage: $$Props['copyrightMessage'] = 'All Rights Reserved.';
@prop export let classSpan: $$Props['classSpan'] = '';
@prop export let classA: $$Props['classA'] = '';
-->
