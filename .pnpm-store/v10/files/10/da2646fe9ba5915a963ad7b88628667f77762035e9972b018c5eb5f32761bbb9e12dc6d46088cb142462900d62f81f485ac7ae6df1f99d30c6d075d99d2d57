import { SvelteComponentTyped } from "svelte";
import type { HTMLAttributes } from 'svelte/elements';
import { type TransitionConfig } from 'svelte/transition';
import type { ParamsType } from '../types';
declare const __propDef: {
    props: HTMLAttributes<HTMLDivElement> & {
        position?: "static" | "fixed" | "absolute" | "relative" | "sticky";
        dismissable?: boolean;
        bannerType?: "default" | "bottom" | "cta" | "signup" | "info";
        divClass?: string;
        innerClass?: string;
        bannerStatus?: boolean;
        transition?: (node: HTMLElement, params: ParamsType) => TransitionConfig;
        params?: object;
        classDiv?: string;
        classInner?: string;
    };
    events: {
        click: MouseEvent;
        change: CustomEvent<any>;
        keydown: CustomEvent<any>;
        keyup: CustomEvent<any>;
        focus: CustomEvent<any>;
        blur: CustomEvent<any>;
        mouseenter: CustomEvent<any>;
        mouseleave: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        header: {};
        default: {};
    };
};
export type BannerProps = typeof __propDef.props;
export type BannerEvents = typeof __propDef.events;
export type BannerSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let position: $$Props['position'] = 'sticky';
 * @prop export let dismissable: $$Props['dismissable'] = true;
 * @prop export let bannerType: NonNullable<$$Props['bannerType']> = 'default';
 * @prop export let divClass: $$Props['divClass'] = 'z-10 flex justify-between p-4 dark:bg-gray-700 dark:border-gray-600';
 * @prop export let innerClass: $$Props['innerClass'] = 'flex';
 * @prop export let bannerStatus: $$Props['bannerStatus'] = true;
 * @prop export let transition: NonNullable<$$Props['transition']> = fade;
 * @prop export let params: $$Props['params'] = {};
 * @prop export let classDiv: $$Props['classDiv'] = '';
 * @prop export let classInner: $$Props['classInner'] = '';
 */
export default class Banner extends SvelteComponentTyped<BannerProps, BannerEvents, BannerSlots> {
}
export {};
