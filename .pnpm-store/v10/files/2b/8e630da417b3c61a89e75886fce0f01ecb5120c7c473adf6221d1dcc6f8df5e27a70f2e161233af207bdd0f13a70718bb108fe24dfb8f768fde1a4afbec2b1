import { SvelteComponentTyped } from "svelte";
import { type Writable } from 'svelte/store';
export interface AccordionCtxType {
    flush: boolean | undefined;
    activeClass: string;
    inactiveClass: string;
    selected?: Writable<object>;
    classActive?: string;
    classInactive?: string;
}
declare const __propDef: {
    props: import("svelte/elements").HTMLAttributes<HTMLElement> & {
        tag?: string;
        color?: import("../utils/Frame.svelte").FrameColor;
        rounded?: boolean;
        border?: boolean;
        shadow?: boolean;
        node?: HTMLElement | undefined;
        use?: import("svelte/action").Action<HTMLElement, any>;
        options?: object;
        class?: string;
        role?: string;
        open?: boolean;
        transition?: (node: HTMLElement, params: any) => import("svelte/transition").TransitionConfig;
        params?: any;
    } & {
        multiple?: boolean;
        flush?: boolean;
        activeClass?: string;
        inactiveClass?: string;
        defaultClass?: string;
        classActive?: string;
        classInactive?: string;
    };
    events: {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {};
    };
};
export type AccordionProps = typeof __propDef.props;
export type AccordionEvents = typeof __propDef.events;
export type AccordionSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let multiple: $$Props['multiple'] = false;
 * @prop export let flush: $$Props['flush'] = false;
 * @prop export let activeClass: $$Props['activeClass'] = 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-800';
 * @prop export let inactiveClass: $$Props['inactiveClass'] = 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800';
 * @prop export let defaultClass: $$Props['defaultClass'] = 'text-gray-500 dark:text-gray-400';
 * @prop export let classActive: $$Props['classActive'] = '';
 * @prop export let classInactive: $$Props['classInactive'] = '';
 */
export default class Accordion extends SvelteComponentTyped<AccordionProps, AccordionEvents, AccordionSlots> {
}
export {};
