<script>import { getContext, onMount } from "svelte";
import { writable } from "svelte/store";
import { blur, fade, fly, slide } from "svelte/transition";
import { twMerge } from "tailwind-merge";
export let tag = "h2";
export let open = false;
export let activeClass = void 0;
export let inactiveClass = void 0;
export let defaultClass = "flex items-center justify-between w-full font-medium text-left group-first:rounded-t-xl border-gray-200 dark:border-gray-700";
export let transitionType = "slide";
export let transitionParams = {};
export let paddingFlush = "py-5";
export let paddingDefault = "p-5";
export let textFlushOpen = "text-gray-900 dark:text-white";
export let textFlushDefault = "text-gray-500 dark:text-gray-400";
export let borderClass = "border-s border-e group-first:border-t";
export let borderOpenClass = "border-s border-e";
export let borderBottomClass = "border-b";
export let borderSharedClass = "border-gray-200 dark:border-gray-700";
export let classActive = void 0;
export let classInactive = void 0;
let activeCls = twMerge(activeClass, classActive);
let inactiveCls = twMerge(inactiveClass, classInactive);
const multiple = (node, params) => {
  switch (transitionType) {
    case "blur-sm":
      return blur(node, params);
    case "fly":
      return fly(node, params);
    case "fade":
      return fade(node, params);
    default:
      return slide(node, params);
  }
};
const ctx = getContext("ctx") ?? {};
const self = {};
const selected = ctx.selected ?? writable();
let _open = open;
open = false;
onMount(() => {
  if (_open) $selected = self;
  return selected.subscribe((x) => open = x === self);
});
const handleToggle = (_) => selected.set(open ? {} : self);
let buttonClass;
$: buttonClass = twMerge([defaultClass, ctx.flush || borderClass, borderBottomClass, borderSharedClass, ctx.flush ? paddingFlush : paddingDefault, open && (ctx.flush ? textFlushOpen : activeCls || ctx.activeClass), !open && (ctx.flush ? textFlushDefault : inactiveCls || ctx.inactiveClass), $$props.class]);
$: contentClass = twMerge([ctx.flush ? paddingFlush : paddingDefault, ctx.flush ? "" : borderOpenClass, borderBottomClass, borderSharedClass]);
</script>

<svelte:element this={tag} class="group">
  <button on:click={handleToggle} type="button" class={buttonClass} aria-expanded={open}>
    <slot name="header" />
    {#if open}
      <slot name="arrowup">
        <svg class="w-3 h-3 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
          <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5 5 1 1 5" />
        </svg>
      </slot>
    {:else}
      <slot name="arrowdown">
        <svg class="w-3 h-3 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
          <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4" />
        </svg>
      </slot>
    {/if}
  </button>
</svelte:element>
{#if open}
  <div transition:multiple={transitionParams}>
    <div class={contentClass}>
      <slot />
    </div>
  </div>
{/if}

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let tag: $$Props['tag'] = 'h2';
@prop export let open: NonNullable<$$Props['open']> = false;
@prop export let activeClass: $$Props['activeClass'] = undefined;
@prop export let inactiveClass: $$Props['inactiveClass'] = undefined;
@prop export let defaultClass: $$Props['defaultClass'] = 'flex items-center justify-between w-full font-medium text-left group-first:rounded-t-xl border-gray-200 dark:border-gray-700';
@prop export let transitionType: $$Props['transitionType'] = 'slide';
@prop export let transitionParams: $$Props['transitionParams'] = {};
@prop export let paddingFlush: $$Props['paddingFlush'] = 'py-5';
@prop export let paddingDefault: $$Props['paddingDefault'] = 'p-5';
@prop export let textFlushOpen: $$Props['textFlushOpen'] = 'text-gray-900 dark:text-white';
@prop export let textFlushDefault: $$Props['textFlushDefault'] = 'text-gray-500 dark:text-gray-400';
@prop export let borderClass: $$Props['borderClass'] = 'border-s border-e group-first:border-t';
@prop export let borderOpenClass: $$Props['borderOpenClass'] = 'border-s border-e';
@prop export let borderBottomClass: $$Props['borderBottomClass'] = 'border-b';
@prop export let borderSharedClass: $$Props['borderSharedClass'] = 'border-gray-200 dark:border-gray-700';
@prop export let classActive: $$Props['classActive'] = undefined;
@prop export let classInactive: $$Props['classInactive'] = undefined;
-->
