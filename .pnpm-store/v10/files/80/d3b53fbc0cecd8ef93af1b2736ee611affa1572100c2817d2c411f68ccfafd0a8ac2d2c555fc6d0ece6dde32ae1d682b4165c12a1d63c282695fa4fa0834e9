import { SvelteComponentTyped } from "svelte";
import type { ListGroupItemType } from '../types';
declare class __sveltets_Render<T extends ListGroupItemType | string> {
    props(): import("svelte/elements").HTMLAttributes<HTMLElement> & {
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
        items?: T[] | undefined;
        active?: boolean;
        defaultClass?: string;
    };
    events(): {
        click: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots(): {
        default: {
            item: T;
            index: number;
        };
    };
}
export type ListgroupProps<T extends ListGroupItemType | string> = ReturnType<__sveltets_Render<T>['props']>;
export type ListgroupEvents<T extends ListGroupItemType | string> = ReturnType<__sveltets_Render<T>['events']>;
export type ListgroupSlots<T extends ListGroupItemType | string> = ReturnType<__sveltets_Render<T>['slots']>;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let items: NonNullable<$$Props['items']> = [];
 * @prop export let active: $$Props['active'] = false;
 * @prop export let defaultClass: $$Props['defaultClass'] = 'divide-y divide-gray-200 dark:divide-gray-600';
 */
export default class Listgroup<T extends ListGroupItemType | string> extends SvelteComponentTyped<ListgroupProps<T>, ListgroupEvents<T>, ListgroupSlots<T>> {
}
export {};
