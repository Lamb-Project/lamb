import { SvelteComponentTyped } from "svelte";
import { type Writable } from 'svelte/store';
export interface TabCtxType {
    activeClasses: string;
    inactiveClasses: string;
    selected: Writable<HTMLElement>;
}
import type { HTMLAttributes } from 'svelte/elements';
declare const __propDef: {
    props: HTMLAttributes<HTMLUListElement> & {
        tabStyle?: "full" | "pill" | "underline" | "none";
        defaultClass?: string;
        contentClass?: string;
        divider?: boolean;
        activeClasses?: string;
        inactiveClasses?: string;
    };
    events: {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {
            tabStyle: NonNullable<"none" | "pill" | "underline" | "full" | undefined>;
        };
        divider: {};
    };
};
export type TabsProps = typeof __propDef.props;
export type TabsEvents = typeof __propDef.events;
export type TabsSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let tabStyle: NonNullable<$$Props['tabStyle']> = 'none';
 * @prop export let defaultClass: $$Props['defaultClass'] = 'flex flex-wrap space-x-2 rtl:space-x-reverse';
 * @prop export let contentClass: $$Props['contentClass'] = 'p-4 bg-gray-50 rounded-lg dark:bg-gray-800 mt-4';
 * @prop export let divider: $$Props['divider'] = true;
 * @prop export let activeClasses: NonNullable<$$Props['activeClasses']> = 'p-4 text-primary-600 bg-gray-100 rounded-t-lg dark:bg-gray-800 dark:text-primary-500';
 * @prop export let inactiveClasses: NonNullable<$$Props['inactiveClasses']> = 'p-4 text-gray-500 rounded-t-lg hover:text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-300';
 */
export default class Tabs extends SvelteComponentTyped<TabsProps, TabsEvents, TabsSlots> {
}
export {};
