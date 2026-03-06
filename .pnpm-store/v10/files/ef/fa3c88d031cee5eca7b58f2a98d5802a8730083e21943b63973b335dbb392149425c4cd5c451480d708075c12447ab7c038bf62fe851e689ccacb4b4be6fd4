import { SvelteComponentTyped } from "svelte";
import type { HTMLButtonAttributes, HTMLAnchorAttributes } from 'svelte/elements';
declare const __propDef: {
    props: ({
        btnName?: string;
        appBtnPosition?: "left" | "middle" | "right";
        activeClass?: string;
        exact?: boolean;
        spanClass?: string;
    } & Omit<HTMLAnchorAttributes, "type"> & {
        href?: string | undefined;
    }) | ({
        btnName?: string;
        appBtnPosition?: "left" | "middle" | "right";
        activeClass?: string;
        exact?: boolean;
        spanClass?: string;
    } & HTMLButtonAttributes & {
        disabled?: HTMLButtonAttributes["disabled"];
    });
    events: {
        click: MouseEvent;
        change: Event;
        keydown: KeyboardEvent;
        keyup: KeyboardEvent;
        focus: FocusEvent;
        blur: FocusEvent;
        mouseenter: MouseEvent;
        mouseleave: MouseEvent;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
    };
};
export type BottomNavItemProps = typeof __propDef.props;
export type BottomNavItemEvents = typeof __propDef.events;
export type BottomNavItemSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let btnName: $$Props['btnName'] = '';
 * @prop export let appBtnPosition: NonNullable<$$Props['appBtnPosition']> = 'middle';
 * @prop export let activeClass: $$Props['activeClass'] = undefined;
 * @prop export let href: string = '';
 * @prop export let exact: $$Props['exact'] = true;
 * @prop export let spanClass: $$Props['spanClass'] = '';
 */
export default class BottomNavItem extends SvelteComponentTyped<BottomNavItemProps, BottomNavItemEvents, BottomNavItemSlots> {
}
export {};
