import { SvelteComponentTyped } from "svelte";
import type { HTMLSelectAttributes } from 'svelte/elements';
import type { FormSizeType, SelectOptionType } from '../types';
declare const __propDef: {
    props: Omit<HTMLSelectAttributes, "size"> & {
        items?: SelectOptionType<any>[];
        value?: (string | number)[];
        size?: FormSizeType;
        dropdownClass?: string;
        placeholder?: string;
        disabled?: boolean;
    };
    events: {
        input: Event;
        click: MouseEvent;
        change: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {
            item: SelectOptionType<any>;
            clear: () => void;
        };
    };
};
export type MultiSelectProps = typeof __propDef.props;
export type MultiSelectEvents = typeof __propDef.events;
export type MultiSelectSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let items: NonNullable<$$Props['items']> = [];
 * @prop export let value: NonNullable<$$Props['value']> = [];
 * @prop export let size: NonNullable<$$Props['size']> = 'md';
 * @prop export let dropdownClass: $$Props['dropdownClass'] = '';
 * @prop export let placeholder: $$Props['placeholder'] = '';
 * @prop export let disabled: $$Props['disabled'] = false;
 */
export default class MultiSelect extends SvelteComponentTyped<MultiSelectProps, MultiSelectEvents, MultiSelectSlots> {
}
export {};
