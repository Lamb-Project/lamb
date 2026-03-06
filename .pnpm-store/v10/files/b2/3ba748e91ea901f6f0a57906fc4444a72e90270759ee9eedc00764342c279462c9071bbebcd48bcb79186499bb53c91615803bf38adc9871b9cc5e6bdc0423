<script context="module"></script>

<script>import { twMerge } from "tailwind-merge";
import Button from "../buttons/Button.svelte";
import Popper from "../utils/Popper.svelte";
import { setContext } from "svelte";
import generateId from "../utils/generateId";
import GradientButton from "../buttons/GradientButton.svelte";
export let defaultClass = "fixed end-6 bottom-6";
export let popperDefaultClass = "flex items-center mb-4 gap-2";
export let placement = "top";
export let pill = true;
export let tooltip = "left";
export let trigger = "hover";
export let textOutside = false;
export let id = generateId();
export let name = "Open actions menu";
export let gradient = false;
export let open = false;
setContext("speed-dial", { pill, tooltip, textOutside });
let divClass;
$: divClass = twMerge(defaultClass, "group", $$props.class);
let poperClass;
$: poperClass = twMerge(popperDefaultClass, ["top", "bottom"].includes(placement.split("-")[0]) && "flex-col");
</script>

<div class={divClass}>
  <slot name="button">
    {#if gradient}
      <GradientButton {pill} {name} aria-controls={id} aria-expanded={open} {...$$restProps} class="p-3!">
        <slot name="icon">
          <svg aria-hidden="true" class="w-8 h-8 transition-transform group-hover:rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </slot>
        <span class="sr-only">{name}</span>
      </GradientButton>
    {:else}
      <Button {pill} {name} aria-controls={id} aria-expanded={open} {...$$restProps} class="p-3!">
        <slot name="icon">
          <svg aria-hidden="true" class="w-8 h-8 transition-transform group-hover:rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </slot>
        <span class="sr-only">{name}</span>
      </Button>
    {/if}
  </slot>
  <Popper {id} {trigger} arrow={false} color="none" activeContent {placement} class={poperClass} bind:open>
    <slot />
  </Popper>
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let defaultClass: $$Props['defaultClass'] = 'fixed end-6 bottom-6';
@prop export let popperDefaultClass: $$Props['popperDefaultClass'] = 'flex items-center mb-4 gap-2';
@prop export let placement: NonNullable<$$Props['placement']> = 'top';
@prop export let pill: NonNullable<$$Props['pill']> = true;
@prop export let tooltip: NonNullable<$$Props['tooltip']> = 'left';
@prop export let trigger: $$Props['trigger'] = 'hover';
@prop export let textOutside: NonNullable<$$Props['textOutside']> = false;
@prop export let id: $$Props['id'] = generateId();
@prop export let name: $$Props['name'] = 'Open actions menu';
@prop export let gradient: $$Props['gradient'] = false;
@prop export let open: $$Props['open'] = false;
-->
