<script context="module"></script>

<script>import { twMerge } from "tailwind-merge";
import Popper from "../utils/Popper.svelte";
import { setContext } from "svelte";
import { writable } from "svelte/store";
export let activeUrl = void 0;
export let open = false;
export let containerClass = "divide-y z-50";
export let classContainer = void 0;
export let headerClass = "py-1 overflow-hidden rounded-t-lg";
export let classHeader = void 0;
export let footerClass = "py-1 overflow-hidden rounded-b-lg";
export let classFooter = void 0;
export let activeClass = "text-primary-700 dark:text-primary-700 hover:text-primary-900 dark:hover:text-primary-900";
export let classActive = void 0;
export let arrow = false;
export let trigger = "click";
export let placement = "bottom";
export let color = "dropdown";
export let shadow = true;
export let rounded = true;
const activeUrlStore = writable("");
let activeCls = twMerge(activeClass, classActive);
setContext("DropdownType", { activeClass: activeCls });
$: activeUrlStore.set(activeUrl ?? "");
setContext("activeUrl", activeUrlStore);
$: containerCls = twMerge(containerClass, classContainer);
$: headerCls = twMerge(headerClass, classHeader);
$: ulCls = twMerge("py-1", $$props.class);
$: footerCls = twMerge(footerClass, classFooter);
</script>

<Popper activeContent {...$$restProps} {trigger} {arrow} {placement} {shadow} {rounded} {color} class={containerCls} on:show bind:open>
  {#if $$slots.header}
    <div class={headerCls}>
      <slot name="header" />
    </div>
  {/if}
  <ul class={ulCls}>
    <slot />
  </ul>
  {#if $$slots.footer}
    <div class={footerCls}>
      <slot name="footer" />
    </div>
  {/if}
</Popper>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let activeUrl: $$Props['activeUrl'] = undefined;
@prop export let open: $$Props['open'] = false;
@prop export let containerClass: $$Props['containerClass'] = 'divide-y z-50';
@prop export let classContainer: $$Props['classContainer'] = undefined;
@prop export let headerClass: $$Props['headerClass'] = 'py-1 overflow-hidden rounded-t-lg';
@prop export let classHeader: $$Props['classHeader'] = undefined;
@prop export let footerClass: $$Props['footerClass'] = 'py-1 overflow-hidden rounded-b-lg';
@prop export let classFooter: $$Props['classFooter'] = undefined;
@prop export let activeClass: $$Props['activeClass'] = 'text-primary-700 dark:text-primary-700 hover:text-primary-900 dark:hover:text-primary-900';
@prop export let classActive: $$Props['classActive'] = undefined;
@prop export let arrow: $$Props['arrow'] = false;
@prop export let trigger: $$Props['trigger'] = 'click';
@prop export let placement: $$Props['placement'] = 'bottom';
@prop export let color: $$Props['color'] = 'dropdown';
@prop export let shadow: $$Props['shadow'] = true;
@prop export let rounded: $$Props['rounded'] = true;
-->
