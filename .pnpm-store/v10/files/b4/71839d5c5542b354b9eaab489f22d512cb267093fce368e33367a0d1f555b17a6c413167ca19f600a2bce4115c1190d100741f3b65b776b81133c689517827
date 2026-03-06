import { SvelteComponentTyped } from "svelte";
import type { LinkType } from '../types';
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
        activeContent?: boolean;
        arrow?: boolean;
        offset?: number;
        placement?: import("@floating-ui/dom").Placement;
        trigger?: "hover" | "click" | "focus";
        triggeredBy?: string;
        reference?: string;
        strategy?: "absolute" | "fixed";
        open?: boolean;
        yOnly?: boolean;
    } & {
        items: (LinkType & {
            [propName: string]: any;
        })[];
        full?: boolean;
        open?: boolean;
        ulClass?: string;
    };
    events: {
        show: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {
            item: LinkType & {
                [propName: string]: any;
            };
            index: number;
        };
        extra: {};
    };
};
export type MegaMenuProps = typeof __propDef.props;
export type MegaMenuEvents = typeof __propDef.events;
export type MegaMenuSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let items: $$Props['items'] = [];
 * @prop export let full: $$Props['full'] = false;
 * @prop export let open: $$Props['open'] = false;
 * @prop export let ulClass: $$Props['ulClass'] = 'grid grid-flow-row gap-y-4 md:gap-x-0 auto-col-max auto-row-max';
 */
export default class MegaMenu extends SvelteComponentTyped<MegaMenuProps, MegaMenuEvents, MegaMenuSlots> {
}
export {};
