import { SvelteComponentTyped } from "svelte";
import type { ColorVariant } from '../types';
import type { HTMLAttributes } from 'svelte/elements';
import { type TransitionConfig } from 'svelte/transition';
declare const __propDef: {
    props: HTMLAttributes<HTMLDivElement> & {
        color?: ColorVariant;
        large?: boolean;
        dismissable?: boolean;
        border?: boolean;
        href?: string;
        rounded?: boolean;
        transition?: (node: HTMLElement, params: any) => TransitionConfig;
        params?: object;
        tag?: string;
    };
    events: {
        close: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
        'close-button': {
            close: () => void;
        };
    };
};
export type BadgeProps = typeof __propDef.props;
export type BadgeEvents = typeof __propDef.events;
export type BadgeSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let color: NonNullable<$$Props['color']> = 'primary';
 * @prop export let large: $$Props['large'] = false;
 * @prop export let dismissable: $$Props['dismissable'] = false;
 * @prop export let border: $$Props['border'] = false;
 * @prop export let href: $$Props['href'] = '';
 * @prop export let rounded: $$Props['rounded'] = false;
 * @prop export let transition: NonNullable<$$Props['transition']> = fade;
 * @prop export let params: $$Props['params'] = {};
 * @prop export let tag: $$Props['tag'] = 'div';
 */
export default class Badge extends SvelteComponentTyped<BadgeProps, BadgeEvents, BadgeSlots> {
}
export {};
