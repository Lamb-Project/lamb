<script>import { twMerge } from "tailwind-merge";
export let href = "";
export let ariaLabel = "";
export let aClass = "text-gray-500 hover:text-gray-900 dark:hover:text-white";
export let target = void 0;
</script>

{#if href}
  <a {...$$restProps} {href} {target} aria-label={ariaLabel} class={twMerge(aClass, $$props.class)}>
    <slot />
  </a>
{:else}
  <slot />
{/if}

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let href: $$Props['href'] = '';
@prop export let ariaLabel: $$Props['ariaLabel'] = '';
@prop export let aClass: $$Props['aClass'] = 'text-gray-500 hover:text-gray-900 dark:hover:text-white';
@prop export let target: $$Props['target'] = undefined;
-->
