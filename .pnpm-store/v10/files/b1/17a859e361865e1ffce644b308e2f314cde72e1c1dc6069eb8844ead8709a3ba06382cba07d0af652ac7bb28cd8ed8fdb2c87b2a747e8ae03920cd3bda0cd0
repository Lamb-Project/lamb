import { SvelteComponentTyped } from "svelte";
import type { HTMLButtonAttributes, HTMLAnchorAttributes } from 'svelte/elements';
declare const __propDef: {
    props: ({
        pill?: boolean;
        outline?: boolean;
        size?: "xs" | "sm" | "md" | "lg" | "xl";
        color?: "red" | "yellow" | "green" | "purple" | "blue" | "light" | "dark" | "primary" | "none" | "alternative";
        shadow?: boolean;
        tag?: "a" | "button" | "label";
        checked?: boolean;
    } & Omit<HTMLAnchorAttributes, "type"> & {
        href?: string | undefined;
    }) | ({
        pill?: boolean;
        outline?: boolean;
        size?: "xs" | "sm" | "md" | "lg" | "xl";
        color?: "red" | "yellow" | "green" | "purple" | "blue" | "light" | "dark" | "primary" | "none" | "alternative";
        shadow?: boolean;
        tag?: "a" | "button" | "label";
        checked?: boolean;
    } & HTMLButtonAttributes & {
        disabled?: HTMLButtonAttributes["disabled"];
        type?: HTMLButtonAttributes["type"];
    });
    events: {
        click: MouseEvent;
        change: Event;
        keydown: KeyboardEvent;
        keyup: KeyboardEvent;
        touchstart: TouchEvent;
        touchend: TouchEvent;
        touchcancel: TouchEvent;
        mouseenter: MouseEvent;
        mouseleave: MouseEvent;
        mouseup: MouseEvent;
        mousedown: MouseEvent;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
    };
};
type ButtonProps_ = typeof __propDef.props;
export { ButtonProps_ as ButtonProps };
export type ButtonEvents = typeof __propDef.events;
export type ButtonSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let pill: $$Props['pill'] = false;
 * @prop export let outline: $$Props['outline'] = false;
 * @prop export let size: NonNullable<$$Props['size']> = group ? 'sm' : 'md';
 * @prop export let href: string | undefined = undefined;
 * @prop export let type: HTMLButtonAttributes['type'] = 'button';
 * @prop export let color: NonNullable<$$Props['color']> = group ? (outline ? 'dark' : 'alternative') : 'primary';
 * @prop export let shadow: $$Props['shadow'] = false;
 * @prop export let tag: $$Props['tag'] = 'button';
 * @prop export let checked: $$Props['checked'] = undefined;
 * @prop export let disabled: HTMLButtonAttributes['disabled'] = false;
 */
export default class Button extends SvelteComponentTyped<ButtonProps_, ButtonEvents, ButtonSlots> {
}
