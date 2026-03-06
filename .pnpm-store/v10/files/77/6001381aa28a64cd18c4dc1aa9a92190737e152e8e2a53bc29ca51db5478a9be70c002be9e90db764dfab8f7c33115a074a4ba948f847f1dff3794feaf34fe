<script>import { twMerge } from "tailwind-merge";
import Frame from "../utils/Frame.svelte";
export let href = void 0;
export let horizontal = false;
export let reverse = false;
export let img = void 0;
export let padding = "lg";
export let size = "sm";
export let imgClass = "";
const paddings = {
  none: "",
  xs: "p-2",
  sm: "p-4",
  md: "p-4 sm:p-5",
  lg: "p-4 sm:p-6",
  xl: "p-4 sm:p-8"
};
const sizes = {
  none: "",
  xs: "max-w-xs",
  sm: "max-w-sm",
  md: "max-w-xl",
  lg: "max-w-2xl",
  xl: "max-w-(--breakpoint-xl)"
};
let innerPadding;
$: innerPadding = paddings[padding];
let cardClass;
$: cardClass = twMerge("flex w-full", sizes[size], reverse ? "flex-col-reverse" : "flex-col", horizontal && (reverse ? "md:flex-row-reverse" : "md:flex-row"), href && "hover:bg-gray-100 dark:hover:bg-gray-700", !img && innerPadding, $$props.class);
let imgCls;
$: imgCls = twMerge(reverse ? "rounded-b-lg" : "rounded-t-lg", horizontal && "object-cover w-full h-96 md:h-auto md:w-48 md:rounded-none", horizontal && (reverse ? "md:rounded-e-lg" : "md:rounded-s-lg"), imgClass);
</script>

<Frame tag={href ? 'a' : 'div'} rounded shadow border on:click on:focusin on:focusout on:mouseenter on:mouseleave {href} {...$$restProps} class={cardClass}>
  {#if img}
    <img class={imgCls} src={img} alt="" />
    <div class={innerPadding}>
      <slot />
    </div>
  {:else}
    <slot />
  {/if}
</Frame>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let href: $$Props['href'] = undefined;
@prop export let horizontal: $$Props['horizontal'] = false;
@prop export let reverse: $$Props['reverse'] = false;
@prop export let img: $$Props['img'] = undefined;
@prop export let padding: NonNullable<$$Props['padding']> = 'lg';
@prop export let size: NonNullable<$$Props['size']> = 'sm';
@prop export let imgClass: $$Props['imgClass'] = '';
-->
