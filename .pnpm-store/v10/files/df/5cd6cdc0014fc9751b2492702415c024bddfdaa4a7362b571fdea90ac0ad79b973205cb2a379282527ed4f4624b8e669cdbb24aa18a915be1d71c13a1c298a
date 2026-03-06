<script>import { twMerge } from "tailwind-merge";
export let icon = false;
export let divClass = "inline-flex items-center justify-center w-full";
export let hrClass = "h-px my-8 bg-gray-200 border-0 dark:bg-gray-700";
export let iconDivClass = "absolute start-1/2 px-4 bg-white -translate-x-1/2 rtl:translate-x-1/2 ";
export let textSpanClass = "absolute px-3 font-medium text-gray-900 -translate-x-1/2 rtl:translate-x-1/2 bg-white start-1/2 dark:text-white dark:bg-gray-900 ";
export let innerDivClass = "absolute px-4 -translate-x-1/2 rtl:translate-x-1/2 bg-white start-1/2 dark:bg-gray-900";
export let classHr = "";
export let classDiv = "";
export let classInnerDiv = "";
let horizontalCls = twMerge(hrClass, classHr);
let divCls = twMerge(divClass, $$slots && "relative", classDiv);
let innerDivCls = twMerge(innerDivClass, icon ? iconDivClass : textSpanClass, classInnerDiv);
</script>

{#if $$slots.default}
  <div {...$$restProps} class={divCls}>
    <hr class={horizontalCls} />
    <div class={innerDivCls}>
      <slot />
    </div>
  </div>
{:else}
  <hr class={horizontalCls} />
{/if}

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let icon: $$Props['icon'] = false;
@prop export let divClass: $$Props['divClass'] = 'inline-flex items-center justify-center w-full';
@prop export let hrClass: $$Props['hrClass'] = 'h-px my-8 bg-gray-200 border-0 dark:bg-gray-700';
@prop export let iconDivClass: $$Props['iconDivClass'] = 'absolute start-1/2 px-4 bg-white -translate-x-1/2 rtl:translate-x-1/2 ';
@prop export let textSpanClass: $$Props['textSpanClass'] = 'absolute px-3 font-medium text-gray-900 -translate-x-1/2 rtl:translate-x-1/2 bg-white start-1/2 dark:text-white dark:bg-gray-900 ';
@prop export let innerDivClass: $$Props['innerDivClass'] = 'absolute px-4 -translate-x-1/2 rtl:translate-x-1/2 bg-white start-1/2 dark:bg-gray-900';
@prop export let classHr: $$Props['classHr'] = '';
@prop export let classDiv: $$Props['classDiv'] = '';
@prop export let classInnerDiv: $$Props['classInnerDiv'] = '';
-->
