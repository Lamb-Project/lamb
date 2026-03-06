import { SvelteComponentTyped } from "svelte";
export type FrameColor = keyof typeof bgColors;
declare const bgColors: {
    gray: string;
    red: string;
    yellow: string;
    green: string;
    indigo: string;
    purple: string;
    pink: string;
    blue: string;
    light: string;
    dark: string;
    default: string;
    dropdown: string;
    navbar: string;
    navbarUl: string;
    form: string;
    primary: string;
    orange: string;
    none: string;
};
import type { Action } from 'svelte/action';
import type { HTMLAttributes } from 'svelte/elements';
import { type TransitionConfig } from 'svelte/transition';
declare const __propDef: {
    props: HTMLAttributes<HTMLElement> & {
        tag?: string;
        color?: FrameColor;
        rounded?: boolean;
        border?: boolean;
        shadow?: boolean;
        node?: HTMLElement | undefined;
        use?: Action<HTMLElement, any>;
        options?: object;
        class?: string;
        role?: string;
        open?: boolean;
        transition?: (node: HTMLElement, params: any) => TransitionConfig;
        params?: any;
    };
    events: {
        click: MouseEvent;
        mouseenter: MouseEvent;
        mouseleave: MouseEvent;
        focusin: FocusEvent;
        focusout: FocusEvent;
        show: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
    };
};
export type FrameProps = typeof __propDef.props;
export type FrameEvents = typeof __propDef.events;
export type FrameSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let tag: string = $$restProps.href ? 'a' : 'div';
 * @prop export let color: FrameColor = 'default';
 * @prop export let rounded: boolean = false;
 * @prop export let border: boolean = false;
 * @prop export let shadow: boolean = false;
 * @prop export let node: HTMLElement | undefined = undefined;
 * @prop export let use: Action<HTMLElement, any> = noop;
 * @prop export let options = {};
 * @prop export let role: string | undefined = undefined;
 * @prop export let transition: TransitionFunc | undefined = undefined;
 * @prop export let params: object = {};
 * @prop export let open: boolean = true;
 */
export default class Frame extends SvelteComponentTyped<FrameProps, FrameEvents, FrameSlots> {
}
export {};
