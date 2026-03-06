import { SvelteComponentTyped } from "svelte";
import type { HTMLThAttributes } from 'svelte/elements';
declare class __sveltets_Render<T> {
    props(): HTMLThAttributes & {
        padding?: string;
        sort?: ((a: T, b: T) => number) | null | undefined;
        defaultDirection?: "asc" | "desc";
        defaultSort?: boolean;
        direction?: "asc" | "desc" | null;
    };
    events(): {
        click: MouseEvent;
        focus: FocusEvent;
        keydown: KeyboardEvent;
        keypress: KeyboardEvent;
        keyup: KeyboardEvent;
        mouseenter: MouseEvent;
        mouseleave: MouseEvent;
        mouseover: MouseEvent;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots(): {
        default: {};
    };
}
export type TableHeadCellProps<T> = ReturnType<__sveltets_Render<T>['props']>;
export type TableHeadCellEvents<T> = ReturnType<__sveltets_Render<T>['events']>;
export type TableHeadCellSlots<T> = ReturnType<__sveltets_Render<T>['slots']>;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let padding: $$Props['padding'] = 'px-6 py-3';
 * @prop export let sort: $$Props['sort'] = null;
 * @prop export let defaultDirection: $$Props['defaultDirection'] = 'asc';
 * @prop export let defaultSort: $$Props['defaultSort'] = false;
 * @prop export let direction: $$Props['direction'] = defaultSort ? defaultDirection : null;
 */
export default class TableHeadCell<T> extends SvelteComponentTyped<TableHeadCellProps<T>, TableHeadCellEvents<T>, TableHeadCellSlots<T>> {
}
export {};
