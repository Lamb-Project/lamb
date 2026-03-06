import { SvelteComponentTyped } from "svelte";
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
    } & import("..").Dismissable & {
        dismissable?: boolean;
        defaultClass?: string;
    };
    events: {
        close: CustomEvent<any>;
        click: MouseEvent;
        change: CustomEvent<any>;
        keydown: CustomEvent<any>;
        keyup: CustomEvent<any>;
        focus: CustomEvent<any>;
        blur: CustomEvent<any>;
        mouseenter: CustomEvent<any>;
        mouseleave: CustomEvent<any>;
    } & {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        icon: {};
        default: {};
        'close-button': {
            close: (ev: MouseEvent | undefined) => void;
        };
    };
};
export type AlertProps = typeof __propDef.props;
export type AlertEvents = typeof __propDef.events;
export type AlertSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let dismissable: $$Props['dismissable'] = false;
 * @prop export let defaultClass: $$Props['defaultClass'] = 'p-4 gap-3 text-sm';
 */
export default class Alert extends SvelteComponentTyped<AlertProps, AlertEvents, AlertSlots> {
}
export {};
