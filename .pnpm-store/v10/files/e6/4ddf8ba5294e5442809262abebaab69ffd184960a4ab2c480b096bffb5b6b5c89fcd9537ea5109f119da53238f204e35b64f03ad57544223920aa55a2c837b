<script>import Button from "../buttons/Button.svelte";
import { twMerge } from "tailwind-merge";
export let group = "";
export let value = "";
export let inline = true;
export let pill = false;
export let outline = false;
export let size = void 0;
export let color = void 0;
export let shadow = false;
let buttonClass;
$: buttonClass = twMerge(inline ? "inline-flex" : "flex", $$props.class);
</script>

<Button tag="label" checked={value === group} {pill} {outline} {size} {color} {shadow} class={buttonClass}>
  <input type="radio" bind:group {value} {...$$restProps} class="sr-only" on:keyup on:keydown on:keypress on:focus on:blur on:click on:mouseover on:mouseenter on:mouseleave on:paste on:change />
  <slot />
</Button>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let group: $$Props['group'] = '';
@prop export let value: $$Props['value'] = '';
@prop export let inline: $$Props['inline'] = true;
@prop export let pill: $$Props['pill'] = false;
@prop export let outline: $$Props['outline'] = false;
@prop export let size: $$Props['size'] = undefined;
@prop export let color: $$Props['color'] = undefined;
@prop export let shadow: $$Props['shadow'] = false;
-->
