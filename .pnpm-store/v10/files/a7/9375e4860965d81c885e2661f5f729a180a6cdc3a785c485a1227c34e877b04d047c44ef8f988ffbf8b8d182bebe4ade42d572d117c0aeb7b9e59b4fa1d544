<script>import { setContext } from "svelte";
import { twMerge } from "tailwind-merge";
export let size = "md";
export let divClass = "inline-flex rounded-lg shadow-xs";
setContext("group", { size });
</script>

<div {...$$restProps} class={twMerge(divClass, $$props.class)} role="group">
  <slot />
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let size: $$Props['size'] = 'md';
@prop export let divClass: $$Props['divClass'] = 'inline-flex rounded-lg shadow-xs';
-->
