<script generics="T">import { getContext } from "svelte";
export let tableBodyClass = void 0;
$: items = getContext("items") || [];
let filter = getContext("filter");
let searchTerm = getContext("searchTerm");
$: filtered = $filter ? items.filter((item) => $filter(item, $searchTerm)) : items;
let sorter = getContext("sorter");
$: sorted = $sorter ? filtered.toSorted((a, b) => $sorter.sortDirection * $sorter.sort(a, b)) : filtered;
</script>

<tbody {...$$restProps} class={tableBodyClass}>
  <slot />
  {#each sorted as item}
    <slot name="row" {item} />
  {/each}
</tbody>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let tableBodyClass: $$Props['tableBodyClass'] = undefined;
-->
