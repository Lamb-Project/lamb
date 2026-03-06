<script>import Button from "../buttons/Button.svelte";
import { twMerge } from "tailwind-merge";
export let group = [];
export let value = "on";
export let checked = void 0;
export let inline = true;
export let pill = false;
export let outline = false;
export let size = void 0;
export let color = void 0;
export let shadow = false;
function init(node, _group) {
  function update(_group2) {
    if (_group2 && value !== void 0) {
      checked = _group2.includes(value);
    }
  }
  update(_group);
  return { update };
}
function onChange() {
  if (group && value !== void 0) {
    const index = group.indexOf(value);
    if (checked === void 0) checked = index >= 0;
    if (checked) {
      if (index < 0) {
        group.push(value);
        group = group;
      }
    } else {
      if (index >= 0) {
        group.splice(index, 1);
        group = group;
      }
    }
  }
}
let buttonClass;
$: buttonClass = twMerge(inline ? "inline-flex" : "flex", $$props.class);
</script>

<Button {checked} {pill} {outline} {size} {color} {shadow} class={buttonClass}>
  <input use:init={group} type="checkbox" bind:checked value={value !== undefined ? value : 'on'} {...$$restProps} class="sr-only" on:keyup on:keydown on:keypress on:focus on:blur on:click on:mouseover on:mouseenter on:mouseleave on:paste on:change={onChange} on:change />
  <slot />
</Button>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let group: $$Props['group'] = [];
@prop export let value: $$Props['value'] = 'on';
@prop export let checked: $$Props['checked'] = undefined;
@prop export let inline: $$Props['inline'] = true;
@prop export let pill: $$Props['pill'] = false;
@prop export let outline: $$Props['outline'] = false;
@prop export let size: $$Props['size'] = undefined;
@prop export let color: $$Props['color'] = undefined;
@prop export let shadow: $$Props['shadow'] = false;
-->
