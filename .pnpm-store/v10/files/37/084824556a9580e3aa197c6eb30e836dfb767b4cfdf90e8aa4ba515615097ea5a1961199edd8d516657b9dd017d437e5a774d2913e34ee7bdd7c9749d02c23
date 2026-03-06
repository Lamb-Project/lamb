import { SvelteComponentTyped } from "svelte";
export type State = {
    images: HTMLImgAttributes[];
    index: number;
    lastSlideChange: Date;
    slideDuration: number;
    forward: boolean;
};
import type { HTMLImgAttributes } from 'svelte/elements';
import type { TransitionConfig } from 'svelte/transition';
import Controls from './Controls.svelte';
import Indicators from './Indicators.svelte';
import Slide from './Slide.svelte';
import type { ParamsType } from '../types';
declare const __propDef: {
    props: {
        [x: string]: any;
        images: HTMLImgAttributes[];
        index?: number | undefined;
        slideDuration?: number | undefined;
        transition?: (((node: HTMLElement, params: ParamsType) => TransitionConfig) | null) | undefined;
        duration?: number | undefined;
        ariaLabel?: string | undefined;
        disableSwipe?: boolean | undefined;
        imgClass?: string | undefined;
    };
    events: {
        change: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        slide: {
            Slide: typeof Slide;
            index: number;
        };
        default: {
            index: number;
            Controls: typeof Controls;
            Indicators: typeof Indicators;
        };
    };
};
export type CarouselProps = typeof __propDef.props;
export type CarouselEvents = typeof __propDef.events;
export type CarouselSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let images: HTMLImgAttributes[];
 * @prop export let index: number = 0;
 * @prop export let slideDuration: number = 1000;
 * @prop export let transition: TransitionFunc | null = null;
 * @prop export let duration: number = 0;
 * @prop export let ariaLabel: string = 'Draggable Carousel';
 * @prop export let disableSwipe: boolean = false;
 * @prop export let imgClass: string = '';
 */
export default class Carousel extends SvelteComponentTyped<CarouselProps, CarouselEvents, CarouselSlots> {
}
export {};
