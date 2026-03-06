import { SvelteComponentTyped } from "svelte";
import type { ButtonColorType } from '../types';
import type { ComponentType } from 'svelte';
declare const __propDef: {
    props: {
        id?: string;
        endId?: string;
        value?: string;
        endValue?: string;
        min?: string;
        max?: string;
        required?: boolean;
        disabled?: boolean;
        color?: "base" | "red" | "green" | undefined;
        buttonColor?: ButtonColorType;
        icon: ComponentType;
        type?: "default" | "dropdown" | "select" | "range" | "timerange-dropdown" | "timerange-toggle" | "inline-buttons";
        optionLabel?: string;
        options?: {
            value: string;
            name: string;
        }[];
        selectedOption?: string;
        size?: "sm" | "md" | "lg";
        divClass?: string;
        inputClass?: string;
        selectClass?: string;
        timerangeLabel?: string;
        timerangeButtonLabel?: string;
        timeIntervals?: string[];
        columns?: 1 | 2 | 3 | 4;
    };
    events: {
        select: CustomEvent<{
            [key: string]: string;
            time: string;
            endTime?: string;
        }>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {};
};
export type TimepickerProps = typeof __propDef.props;
export type TimepickerEvents = typeof __propDef.events;
export type TimepickerSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let id = 'time';
 * @prop export let endId = 'end-time';
 * @prop export let value = '00:00';
 * @prop export let endValue = '00:00';
 * @prop export let min = '';
 * @prop export let max = '';
 * @prop export let required = true;
 * @prop export let disabled = false;
 * @prop export let color: 'base' | 'red' | 'green' | undefined = 'base';
 * @prop export let buttonColor: ButtonColorType = 'primary';
 * @prop export let icon: ComponentType;
 * @prop export let type: 'default' | 'dropdown' | 'select' | 'range' | 'timerange-dropdown' | 'timerange-toggle' | 'inline-buttons' = 'default';
 * @prop export let optionLabel = 'Options';
 * @prop export let options: { value: string;
 * @prop export let selectedOption = '';
 * @prop export let size: 'sm' | 'md' | 'lg' = 'md';
 * @prop export let divClass = 'inline-flex rounded-lg shadow-sm';
 * @prop export let inputClass = 'block disabled:cursor-not-allowed disabled:opacity-50 rtl:text-right focus:ring-0 focus:outline-none p-2.5 border-r-0';
 * @prop export let selectClass = 'text-gray-900 disabled:text-gray-400 bg-gray-50 border border-gray-300 rounded-r-lg focus:ring-0 focus:outline-none block w-full p-2.5 border-l-1 focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:disabled:text-gray-500 dark:focus:ring-primary-500 dark:focus:border-primary-500';
 * @prop export let timerangeLabel = 'Choose time range';
 * @prop export let timerangeButtonLabel = 'Save time';
 * @prop export let timeIntervals: string[] = [];
 * @prop export let columns: 1 | 2 | 3 | 4 = 2;
 */
export default class Timepicker extends SvelteComponentTyped<TimepickerProps, TimepickerEvents, TimepickerSlots> {
}
export {};
