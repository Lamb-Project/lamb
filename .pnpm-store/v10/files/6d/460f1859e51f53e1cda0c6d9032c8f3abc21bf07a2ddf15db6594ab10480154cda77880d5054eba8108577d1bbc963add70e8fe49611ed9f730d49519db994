<script>import Button from "../buttons/Button.svelte";
import Tooltip from "../tooltip/Tooltip.svelte";
import { twMerge } from "tailwind-merge";
import { getContext } from "svelte";
const context = getContext("speed-dial");
export let btnDefaultClass = "w-[52px] h-[52px] shadow-xs p-2!";
export let name = "";
export let tooltip = context.tooltip;
export let pill = context.pill;
export let textOutside = context.textOutside;
export let textOutsideClass = "block absolute -start-14 top-1/2 mb-px text-sm font-medium -translate-y-1/2";
export let textDefaultClass = "block mb-px text-xs font-medium";
let btnClass;
$: btnClass = twMerge(btnDefaultClass, tooltip === "none" && "flex-col", textOutside && "relative", $$props.class);
</script>

<Button {pill} outline color="light" {...$$restProps} class={btnClass} on:click>
  <slot />
  {#if tooltip !== 'none'}
    <span class="sr-only">{name}</span>
  {:else if textOutside}
    <span class={textOutsideClass}>{name}</span>
  {:else}
    <span class={textDefaultClass}>{name}</span>
  {/if}
</Button>

{#if tooltip !== 'none'}
  <Tooltip placement={tooltip} style="dark">{name}</Tooltip>
{/if}

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let btnDefaultClass: $$Props['defaultClass'] = 'w-[52px] h-[52px] shadow-xs p-2!';
@prop export let name: $$Props['name'] = '';
@prop export let tooltip: $$Props['tooltip'] = context.tooltip;
@prop export let pill: $$Props['pill'] = context.pill;
@prop export let textOutside: $$Props['textOutside'] = context.textOutside;
@prop export let textOutsideClass: $$Props['textOutsideClass'] = 'block absolute -start-14 top-1/2 mb-px text-sm font-medium -translate-y-1/2';
@prop export let textDefaultClass: $$Props['textDefaultClass'] = 'block mb-px text-xs font-medium';
-->
