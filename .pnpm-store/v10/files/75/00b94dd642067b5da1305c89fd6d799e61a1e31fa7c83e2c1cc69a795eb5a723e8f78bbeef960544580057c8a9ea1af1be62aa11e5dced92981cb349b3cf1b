<script>import { twMerge } from "tailwind-merge";
import Thumbnail from "./Thumbnail.svelte";
export let images = [];
export let index = 0;
export let ariaLabel = "Click to view image";
export let imgClass = "";
export let throttleDelay = 650;
let lastClickedAt = /* @__PURE__ */ new Date();
const btnClick = (idx) => {
  if ((/* @__PURE__ */ new Date()).getTime() - lastClickedAt.getTime() < throttleDelay) {
    console.warn("Thumbnail action throttled");
    return;
  }
  if (idx === index) {
    return;
  }
  index = idx;
  lastClickedAt = /* @__PURE__ */ new Date();
};
$: index = (index + images.length) % images.length;
</script>

<div class={twMerge('flex flex-row justify-center bg-gray-100 w-full', $$props.class)}>
  {#each images as image, idx}
    {@const selected = index === idx}
    <button on:click={() => btnClick(idx)} aria-label={ariaLabel}>
      <slot {Thumbnail} {image} {selected} {imgClass}>
        <Thumbnail {...image} {selected} class={imgClass} />
      </slot>
    </button>
  {/each}
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let images: HTMLImgAttributes[] = [];
@prop export let index: number = 0;
@prop export let ariaLabel: string = 'Click to view image';
@prop export let imgClass: string = '';
@prop export let throttleDelay: number = 650;
-->
