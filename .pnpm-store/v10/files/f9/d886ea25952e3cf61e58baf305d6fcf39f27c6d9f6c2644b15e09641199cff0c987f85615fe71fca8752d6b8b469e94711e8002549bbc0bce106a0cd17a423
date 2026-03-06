<script>import { twMerge } from "tailwind-merge";
export let site;
export let aClass = "flex items-center ps-2.5 mb-5";
export let imgClass = "h-6 me-3 sm:h-7";
export let spanClass = "self-center text-xl font-semibold whitespace-nowrap dark:text-white";
</script>

<a {...$$restProps} href={site.href} class={twMerge(aClass, $$props.class)}>
  <img src={site.img} class={imgClass} alt={site.name} />
  <span class={spanClass}>{site.name}</span>
</a>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let site: $$Props['site'];
@prop export let aClass: $$Props['aClass'] = 'flex items-center ps-2.5 mb-5';
@prop export let imgClass: $$Props['imgClass'] = 'h-6 me-3 sm:h-7';
@prop export let spanClass: $$Props['spanClass'] = 'self-center text-xl font-semibold whitespace-nowrap dark:text-white';
-->
