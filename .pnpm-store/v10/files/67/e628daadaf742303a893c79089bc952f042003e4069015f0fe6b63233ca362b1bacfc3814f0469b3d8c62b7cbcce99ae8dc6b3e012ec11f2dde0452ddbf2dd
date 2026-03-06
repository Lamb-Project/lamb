<script>import { getContext } from "svelte";
import { writable } from "svelte/store";
import { twMerge } from "tailwind-merge";
import ToolbarButton from "../toolbar/ToolbarButton.svelte";
import Menu from "./Menu.svelte";
export let menuClass = "h-6 w-6 shrink-0";
export let onClick = void 0;
export let classMenu = "";
export let title = "Open main menu";
let btnClass = "ms-3 md:hidden";
let hiddenStore = getContext("navHidden") ?? writable(true);
const toggle = (ev) => hiddenStore.update((h) => !h);
</script>

<ToolbarButton name={title} on:click={onClick || toggle} {...$$restProps} class={twMerge(btnClass, $$props.class)}>
  <Menu class={twMerge(menuClass, classMenu)} />
</ToolbarButton>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let menuClass: $$Props['menuClass'] = 'h-6 w-6 shrink-0';
@prop export let onClick: $$Props['onClick'] = undefined;
@prop export let classMenu: $$Props['classMenu'] = '';
@prop export let title: $$Props['title'] = 'Open main menu';
-->
