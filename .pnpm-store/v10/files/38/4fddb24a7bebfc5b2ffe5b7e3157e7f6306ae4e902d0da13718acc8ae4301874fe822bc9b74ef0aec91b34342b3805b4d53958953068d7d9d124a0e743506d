<script>import TransitionFrame from "../utils/TransitionFrame.svelte";
import { twMerge } from "tailwind-merge";
import CloseButton from "../utils/CloseButton.svelte";
export let dismissable = false;
export let defaultClass = "p-4 gap-3 text-sm";
let divClass;
$: divClass = twMerge(defaultClass, ($$slots.icon || dismissable) && "flex items-center", $$props.class);
</script>

<TransitionFrame {dismissable} color="primary" role="alert" rounded {...$$restProps} class={divClass} on:close let:close>
  {#if $$slots.icon}
    <slot name="icon" />
  {/if}

  {#if $$slots.icon || dismissable}
    <div><slot /></div>
  {:else}
    <slot />
  {/if}

  {#if dismissable}
    <slot name="close-button" {close}>
      <CloseButton class="ms-auto -me-1.5 -my-1.5 dark:hover:bg-gray-700" color={$$restProps.color} on:click={close} on:click on:change on:keydown on:keyup on:focus on:blur on:mouseenter on:mouseleave />
    </slot>
  {/if}
</TransitionFrame>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let dismissable: $$Props['dismissable'] = false;
@prop export let defaultClass: $$Props['defaultClass'] = 'p-4 gap-3 text-sm';
-->
