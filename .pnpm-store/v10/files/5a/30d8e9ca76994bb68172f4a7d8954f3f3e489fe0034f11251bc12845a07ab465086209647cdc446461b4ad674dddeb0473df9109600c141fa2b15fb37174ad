<script>import { setContext } from "svelte";
import Frame from "../utils/Frame.svelte";
import { twMerge } from "tailwind-merge";
import NavContainer from "./NavContainer.svelte";
import { writable } from "svelte/store";
export let fluid = false;
export let navContainerClass = "";
let hidden = writable(true);
setContext("navHidden", hidden);
$: {
  $$restProps.color = $$restProps.color ?? "navbar";
}
let toggle = () => hidden.update((hidden2) => !hidden2);
</script>

<Frame tag="nav" {...$$restProps} class={twMerge('px-2 sm:px-4 py-2.5 w-full', $$props.class)}>
  <NavContainer {fluid} class={navContainerClass}>
    <slot hidden={$hidden} {toggle} {NavContainer} />
  </NavContainer>
</Frame>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let fluid: $$Props['fluid'] = false;
@prop export let navContainerClass: string= '';
-->
