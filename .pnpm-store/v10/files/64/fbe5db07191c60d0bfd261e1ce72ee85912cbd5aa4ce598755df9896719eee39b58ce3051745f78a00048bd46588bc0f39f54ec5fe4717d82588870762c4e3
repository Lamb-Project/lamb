<script>import { getContext } from "svelte";
import ControlButton from "./ControlButton.svelte";
import { twMerge } from "tailwind-merge";
import { canChangeSlide } from "./CarouselSlide";
const state = getContext("state");
const { update } = state;
function changeSlide(forward) {
  if (!canChangeSlide({
    lastSlideChange: $state.lastSlideChange,
    slideDuration: $state.slideDuration,
    slideDurationRatio: 0.75
  })) {
    return;
  }
  if (forward) {
    update((_state) => {
      _state.forward = true;
      _state.index = _state.index >= _state.images.length - 1 ? 0 : _state.index + 1;
      _state.lastSlideChange = /* @__PURE__ */ new Date();
      return { ..._state };
    });
  } else {
    update((_state) => {
      _state.forward = false;
      _state.index = _state.index <= 0 ? _state.images.length - 1 : _state.index - 1;
      _state.lastSlideChange = /* @__PURE__ */ new Date();
      return { ..._state };
    });
  }
}
</script>

<!-- Slider controls -->
<slot {ControlButton} {changeSlide}>
  <ControlButton name="Previous" forward={false} on:click={() => changeSlide(false)} class={twMerge($$props.class)} />
  <ControlButton name="Next" forward={true} on:click={() => changeSlide(true)} class={twMerge($$props.class)} />
</slot>
