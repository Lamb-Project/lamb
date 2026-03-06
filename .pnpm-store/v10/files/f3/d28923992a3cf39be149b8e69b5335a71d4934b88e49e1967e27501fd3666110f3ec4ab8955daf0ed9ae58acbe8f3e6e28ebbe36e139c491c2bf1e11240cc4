import { SvelteComponentTyped } from "svelte";
import type { HTMLAttributes } from 'svelte/elements';
import { type TransitionConfig } from 'svelte/transition';
import type { ColorVariant, ToastPositionType } from '../types';
declare const __propDef: {
    props: HTMLAttributes<HTMLDivElement> & {
        dismissable?: boolean;
        color?: ColorVariant;
        position?: ToastPositionType;
        divClass?: string;
        defaultIconClass?: string;
        contentClass?: string;
        align?: boolean;
        transition?: (node: HTMLElement, params: any) => TransitionConfig;
        params?: any;
        toastStatus?: boolean;
    };
    events: {
        close: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        icon: {};
        default: {};
    };
};
export type ToastProps = typeof __propDef.props;
export type ToastEvents = typeof __propDef.events;
export type ToastSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let dismissable: $$Props['dismissable'] = true;
 * @prop export let color: NonNullable<$$Props['color']> = 'primary';
 * @prop export let position: NonNullable<$$Props['position']> = 'none';
 * @prop export let divClass: $$Props['divClass'] = 'w-full max-w-xs p-4 text-gray-500 bg-white shadow-sm dark:text-gray-400 dark:bg-gray-800 gap-3';
 * @prop export let defaultIconClass: $$Props['defaultIconClass'] = 'w-8 h-8';
 * @prop export let contentClass: $$Props['contentClass'] = 'w-full text-sm font-normal';
 * @prop export let align: $$Props['align'] = true;
 * @prop export let transition: NonNullable<$$Props['transition']> = fade;
 * @prop export let params: $$Props['params'] = {};
 * @prop export let toastStatus: $$Props['toastStatus'] = true;
 */
export default class Toast extends SvelteComponentTyped<ToastProps, ToastEvents, ToastSlots> {
}
export {};
