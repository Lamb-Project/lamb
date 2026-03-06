<script>import { twMerge } from "tailwind-merge";
export let tag = "ul";
export let list = void 0;
export let position = "inside";
let lists = {
  disc: "list-disc",
  none: "list-none",
  decimal: "list-decimal"
};
let positions = {
  inside: "list-inside",
  outside: "list-outside"
};
let classList = twMerge(lists[list ?? (tag === "ul" ? "disc" : tag === "ol" ? "decimal" : "none")], positions[position], $$props.class);
</script>

<svelte:element this={tag} {...$$restProps} class={classList}>
  <slot />
</svelte:element>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let tag: $$Props['tag'] = 'ul';
@prop export let list: $$Props['list'] = undefined;
@prop export let position: NonNullable<$$Props['position']> = 'inside';
-->
