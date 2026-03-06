<script>import { twMerge } from "tailwind-merge";
export let divClass = "p-5 mb-4 bg-gray-50 rounded-lg border border-gray-100 dark:bg-gray-800 dark:border-gray-700";
export let timeClass = "text-lg font-semibold text-gray-900 dark:text-white";
export let date = "";
export let olClass = "mt-3 divide-y divider-gray-200 dark:divide-gray-700";
export let classDiv = "";
export let classTime = "";
export let classOl = "";
let divCls = twMerge(divClass, classDiv);
let timeCls = twMerge(timeClass, classTime);
let olCls = twMerge(olClass, classOl);
</script>

<div class={divCls}>
  <time class={timeCls}>{date}</time>
  <ol {...$$restProps} class={olCls}>
    <slot />
  </ol>
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let divClass: $$Props['divClass'] = 'p-5 mb-4 bg-gray-50 rounded-lg border border-gray-100 dark:bg-gray-800 dark:border-gray-700';
@prop export let timeClass: $$Props['timeClass'] = 'text-lg font-semibold text-gray-900 dark:text-white';
@prop export let date: $$Props['date'] = '';
@prop export let olClass: $$Props['olClass'] = 'mt-3 divide-y divider-gray-200 dark:divide-gray-700';
@prop export let classDiv: $$Props['classDiv'] = '';
@prop export let classTime: $$Props['classTime'] = '';
@prop export let classOl: $$Props['classOl'] = '';
-->
