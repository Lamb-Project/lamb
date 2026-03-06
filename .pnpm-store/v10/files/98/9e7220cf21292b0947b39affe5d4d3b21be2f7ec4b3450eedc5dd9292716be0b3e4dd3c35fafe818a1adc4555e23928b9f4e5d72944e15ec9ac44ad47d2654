import { SvelteComponentTyped } from "svelte";
import type { Dismissable } from '../types';
import { type TransitionConfig } from 'svelte/transition';
declare const __propDef: {
    props: import("svelte/elements").HTMLAttributes<HTMLElement> & {
        tag?: string;
        color?: import("./Frame.svelte").FrameColor;
        rounded?: boolean;
        border?: boolean;
        shadow?: boolean;
        node?: HTMLElement | undefined;
        use?: import("svelte/action").Action<HTMLElement, any>;
        options?: object;
        class?: string;
        role?: string;
        open?: boolean;
        transition?: (node: HTMLElement, params: any) => TransitionConfig;
        params?: any;
    } & Dismissable;
    events: {
        show: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {
            close: (ev: MouseEvent | undefined) => void;
        };
    };
};
export type TransitionFrameProps = typeof __propDef.props;
export type TransitionFrameEvents = typeof __propDef.events;
export type TransitionFrameSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let transition: TransitionFunc = fade;
 * @prop export let params: object = {};
 * @prop export let open: boolean = true;
 */
export default class TransitionFrame extends SvelteComponentTyped<TransitionFrameProps, TransitionFrameEvents, TransitionFrameSlots> {
}
export {};
