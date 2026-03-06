import { SvelteComponentTyped } from "svelte";
export declare const labelClass: (inline: boolean, extraClass: string) => string;
export declare const inputClass: (custom: boolean, color: FormColorType, rounded: boolean, tinted: boolean, spacing: string, extraClass: string) => string;
import type { HTMLInputAttributes } from 'svelte/elements';
import type { FormColorType } from '../types';
declare const __propDef: {
    props: HTMLInputAttributes & {
        color?: FormColorType;
        custom?: boolean;
        inline?: boolean;
        group?: number | string | undefined;
        value?: number | string;
        spacing?: string;
        checked?: boolean;
    };
    events: {
        blur: FocusEvent;
        change: Event;
        click: MouseEvent;
        focus: FocusEvent;
        keydown: KeyboardEvent;
        keypress: KeyboardEvent;
        keyup: KeyboardEvent;
        mouseenter: MouseEvent;
        mouseleave: MouseEvent;
        mouseover: MouseEvent;
        paste: ClipboardEvent;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
    };
};
export type RadioProps = typeof __propDef.props;
export type RadioEvents = typeof __propDef.events;
export type RadioSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let color: NonNullable<$$Props['color']> = 'primary';
 * @prop export let custom: NonNullable<$$Props['custom']> = false;
 * @prop export let inline: NonNullable<$$Props['inline']> = false;
 * @prop export let group: $$Props['group'] = undefined;
 * @prop export let value: $$Props['value'] = '';
 * @prop export let spacing: NonNullable<$$Props['spacing']> = $$slots.default ? 'me-2' : '';
 * @prop export let checked: $$Props['checked'] = false;
 */
export default class Radio extends SvelteComponentTyped<RadioProps, RadioEvents, RadioSlots> {
}
export {};
