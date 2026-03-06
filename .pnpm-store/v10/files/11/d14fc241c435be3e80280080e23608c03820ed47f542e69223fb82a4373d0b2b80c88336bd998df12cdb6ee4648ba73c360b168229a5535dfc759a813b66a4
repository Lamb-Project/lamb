<script>import { getContext } from "svelte";
import { writable } from "svelte/store";
import { twMerge } from "tailwind-merge";
export let open = false;
export let title = "Tab title";
export let activeClasses = void 0;
export let inactiveClasses = void 0;
export let defaultClass = "inline-block text-sm font-medium text-center disabled:cursor-not-allowed";
export let divClass = "";
const ctx = getContext("ctx") ?? {};
const selected = ctx.selected ?? writable();
function init(node) {
  selected.set(node);
  const destroy = selected.subscribe((x) => {
    if (x !== node) {
      open = false;
    }
  });
  return { destroy };
}
let buttonClass;
$: buttonClass = twMerge(
  defaultClass,
  open ? activeClasses ?? ctx.activeClasses : inactiveClasses ?? ctx.inactiveClasses,
  open && "active"
  // $$restProps.disabled && 'cursor-not-allowed pointer-events-none'
);
</script>

<li class={twMerge('group', $$props.class)} role="presentation">
  <button type="button" on:click={() => (open = true)} on:blur on:click on:contextmenu on:focus on:keydown on:keypress on:keyup on:mouseenter on:mouseleave on:mouseover role="tab" {...$$restProps} class={buttonClass}>
    <slot name="title">{title}</slot>
  </button>

  {#if open}
    <div class="hidden tab_content_placeholder">
      <div use:init class={divClass}>
        <slot />
      </div>
    </div>
  {/if}
</li>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let open: $$Props['open'] = false;
@prop export let title: $$Props['title'] = 'Tab title';
@prop export let activeClasses: $$Props['activeClasses'] = undefined;
@prop export let inactiveClasses: $$Props['inactiveClasses'] = undefined;
@prop export let defaultClass: $$Props['defaultClass'] = 'inline-block text-sm font-medium text-center disabled:cursor-not-allowed';
@prop export let divClass: $$Props['divClass'] = '';
-->
