<script>import { twMerge } from "tailwind-merge";
import { fly, slide, blur, fade } from "svelte/transition";
import { clickOutside } from "../utils/clickOutside";
export let activateClickOutside = true;
export let hidden = true;
export let position = "fixed";
export let leftOffset = "inset-y-0 start-0";
export let rightOffset = "inset-y-0 end-0";
export let topOffset = "inset-x-0 top-0";
export let bottomOffset = "inset-x-0 bottom-0";
export let width = "w-80";
export let backdrop = true;
export let backdropClass = "";
export let bgColor = "bg-gray-900";
export let bgOpacity = "bg-black/75";
export let placement = "left";
export let id = "drawer-example";
export let divClass = "overflow-y-auto z-50 p-4 bg-white dark:bg-gray-800";
export let transitionParams = {};
export let transitionType = "fly";
function multiple(node, params) {
  switch (transitionType) {
    case "slide":
      return slide(node, params);
    case "blur-sm":
      return blur(node, params);
    case "fade":
      return fade(node, params);
    default:
      return fly(node, params);
  }
}
const placements = {
  left: leftOffset,
  right: rightOffset,
  top: topOffset,
  bottom: bottomOffset
};
const handleDrawer = () => {
  hidden = !hidden;
};
const handleClickOutside = () => activateClickOutside && !hidden && handleDrawer();
let backdropDivClass = twMerge("fixed top-0 start-0 z-50 w-full h-full", backdrop && bgColor, backdrop && bgOpacity, backdropClass);
function clickOutsideWrapper(node, callback) {
  return activateClickOutside ? clickOutside(node, callback) : void 0;
}
</script>

{#if !hidden}
  {#if backdrop && activateClickOutside}
    <div role="presentation" class={backdropDivClass} on:click={() => !hidden && handleDrawer()}></div>
  {:else if backdrop && !activateClickOutside}
    <div role="presentation" class={backdropDivClass}></div>
  {/if}

  <div use:clickOutsideWrapper={handleClickOutside} {id} {...$$restProps} class={twMerge(divClass, width, position, placements[placement], $$props.class)} transition:multiple={transitionParams} tabindex="-1" aria-controls={id} aria-labelledby={id}>
    <slot {hidden}></slot>
  </div>
{/if}

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let activateClickOutside: $$Props['activateClickOutside'] = true;
@prop export let hidden: $$Props['hidden'] = true;
@prop export let position: $$Props['position'] = 'fixed';
@prop export let leftOffset: $$Props['leftOffset'] = 'inset-y-0 start-0';
@prop export let rightOffset: $$Props['rightOffset'] = 'inset-y-0 end-0';
@prop export let topOffset: $$Props['topOffset'] = 'inset-x-0 top-0';
@prop export let bottomOffset: $$Props['bottomOffset'] = 'inset-x-0 bottom-0';
@prop export let width: $$Props['width'] = 'w-80';
@prop export let backdrop: $$Props['backdrop'] = true;
@prop export let backdropClass: $$Props['backdropClass'] = '';
@prop export let bgColor: $$Props['bgColor'] = 'bg-gray-900';
@prop export let bgOpacity: $$Props['bgOpacity'] = 'bg-black/75';
@prop export let placement: NonNullable<$$Props['placement']> = 'left';
@prop export let id: $$Props['id'] = 'drawer-example';
@prop export let divClass: $$Props['divClass'] = 'overflow-y-auto z-50 p-4 bg-white dark:bg-gray-800';
@prop export let transitionParams: $$Props['transitionParams'] = {};
@prop export let transitionType: $$Props['transitionType'] = 'fly';
-->
