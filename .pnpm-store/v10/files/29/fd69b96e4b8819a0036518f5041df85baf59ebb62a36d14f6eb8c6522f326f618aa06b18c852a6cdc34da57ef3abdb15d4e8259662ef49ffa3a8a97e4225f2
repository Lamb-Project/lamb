<script context="module"></script>

<script>import { createEventDispatcher, onMount, setContext } from "svelte";
import { writable } from "svelte/store";
import { twMerge } from "tailwind-merge";
import Controls from "./Controls.svelte";
import Indicators from "./Indicators.svelte";
import Slide from "./Slide.svelte";
import { canChangeSlide } from "./CarouselSlide";
const SLIDE_DURATION_RATIO = 0.25;
export let images;
export let index = 0;
export let slideDuration = 1e3;
export let transition = null;
export let duration = 0;
export let ariaLabel = "Draggable Carousel";
export let disableSwipe = false;
let divClass = "grid overflow-hidden relative rounded-lg h-56 sm:h-64 xl:h-80 2xl:h-96";
export let imgClass = "";
const dispatch = createEventDispatcher();
const { set, subscribe, update } = writable({ images, index, forward: true, slideDuration, lastSlideChange: /* @__PURE__ */ new Date() });
const state = { set: (_state) => set({ index: _state.index, images: _state.images, lastSlideChange: /* @__PURE__ */ new Date(), slideDuration, forward }), subscribe, update };
let forward = true;
setContext("state", state);
subscribe((_state) => {
  index = _state.index;
  forward = _state.forward;
  dispatch("change", images[index]);
});
onMount(() => {
  dispatch("change", images[index]);
});
const nextSlide = () => {
  update((_state) => {
    if (!canChangeSlide({ lastSlideChange: _state.lastSlideChange, slideDuration, slideDurationRatio: SLIDE_DURATION_RATIO })) return _state;
    _state.index = _state.index >= images.length - 1 ? 0 : _state.index + 1;
    _state.lastSlideChange = /* @__PURE__ */ new Date();
    return { ..._state };
  });
};
const prevSlide = () => {
  update((_state) => {
    if (!canChangeSlide({ lastSlideChange: _state.lastSlideChange, slideDuration, slideDurationRatio: SLIDE_DURATION_RATIO })) return _state;
    _state.index = _state.index <= 0 ? images.length - 1 : _state.index - 1;
    _state.lastSlideChange = /* @__PURE__ */ new Date();
    return { ..._state };
  });
};
const loop = (node, duration2) => {
  carouselDiv = node;
  let intervalId;
  if (duration2 > 0) intervalId = setInterval(nextSlide, duration2);
  return {
    update: (duration3) => {
      clearInterval(intervalId);
      if (duration3 > 0) intervalId = setInterval(nextSlide, duration3);
    },
    destroy: () => clearInterval(intervalId)
  };
};
let activeDragGesture;
let carouselDiv;
let percentOffset = 0;
let touchEvent = null;
const getPositionFromEvent = (evt) => {
  const mousePos = evt?.clientX;
  if (mousePos) return mousePos;
  let touchEvt = evt;
  if (/^touch/.test(touchEvt?.type)) {
    return touchEvt.touches[0].clientX;
  }
};
const onDragStart = (evt) => {
  if (disableSwipe) return;
  touchEvent = evt;
  evt.cancelable && evt.preventDefault();
  const start = getPositionFromEvent(evt);
  const width = carouselDiv.getBoundingClientRect().width;
  if (start === void 0 || width === void 0) return;
  activeDragGesture = {
    start,
    position: start,
    width,
    timestamp: Date.now()
  };
};
$: onDragMove = activeDragGesture === void 0 ? void 0 : (evt) => {
  const position = getPositionFromEvent(evt);
  if (!activeDragGesture || position === void 0) return;
  const { start, width } = activeDragGesture;
  percentOffset = Math.min(100, Math.max(-100, (position - start) / width * 100));
  activeDragGesture.position = position;
};
$: onDragStop = activeDragGesture === void 0 ? void 0 : (evt) => {
  const SWIPE_MAX_DURATION = 250;
  const SWIPE_MIN_DISTANCE = 30;
  const DRAG_MIN_PERCENT = 50;
  if (activeDragGesture) {
    const { timestamp, position, start } = activeDragGesture;
    const duration2 = Date.now() - timestamp;
    const distance = position - start;
    if (Math.abs(distance) >= SWIPE_MIN_DISTANCE && duration2 <= SWIPE_MAX_DURATION && duration2 > 0) {
      if (distance > 0) prevSlide();
      else nextSlide();
    } else if (percentOffset > DRAG_MIN_PERCENT) prevSlide();
    else if (percentOffset < -DRAG_MIN_PERCENT) nextSlide();
    else {
      if (touchEvent?.constructor.name === "TouchEvent") {
        touchEvent?.target?.dispatchEvent(
          new Event("click", {
            bubbles: true
          })
        );
      }
    }
  }
  percentOffset = 0;
  activeDragGesture = void 0;
  touchEvent = null;
};
</script>

<!-- Preload all Carousel images for improved responsivity -->
<svelte:head>
  {#if images.length > 0}
    {#each images as image}
      <link rel="preload" href={image.src} as="image" />
    {/each}
  {/if}
</svelte:head>

<!-- The move listeners go here, so things keep working if the touch strays out of the element. -->
<svelte:document on:mousemove={onDragMove} on:mouseup={onDragStop} on:touchmove={onDragMove} on:touchend={onDragStop} />
<div bind:this={carouselDiv} class="relative" on:mousedown|nonpassive={onDragStart} on:touchstart|nonpassive={onDragStart} on:mousemove={onDragMove} on:mouseup={onDragStop} on:touchmove={onDragMove} on:touchend={onDragStop} role="button" aria-label={ariaLabel} tabindex="0">
  <div {...$$restProps} class={twMerge(divClass, activeDragGesture === undefined ? 'transition-transform' : '', $$props.class)} use:loop={duration}>
    <slot name="slide" {Slide} {index}>
      <Slide image={images[index]} class={imgClass} {transition} />
    </slot>
  </div>
  <slot {index} {Controls} {Indicators} />
</div>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let images: HTMLImgAttributes[];
@prop export let index: number = 0;
@prop export let slideDuration: number = 1000;
@prop export let transition: TransitionFunc | null = null;
@prop export let duration: number = 0;
@prop export let ariaLabel: string = 'Draggable Carousel';
@prop export let disableSwipe: boolean = false;
@prop export let imgClass: string = '';
-->
