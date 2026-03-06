import { SvelteComponentTyped } from "svelte";
import NavContainer from './NavContainer.svelte';
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
        fluid?: boolean;
        navContainerClass?: string;
    };
    events: {
        [evt: string]: CustomEvent<any>;
    };
    slots: {
        default: {
            hidden: boolean;
            toggle: () => void;
            NavContainer: typeof NavContainer;
        };
    };
};
export type NavbarProps = typeof __propDef.props;
export type NavbarEvents = typeof __propDef.events;
export type NavbarSlots = typeof __propDef.slots;
/**
 * [Go to docs](https://flowbite-svelte.com/)
 * ## Props
 * @prop export let fluid: $$Props['fluid'] = false;
 * @prop export let navContainerClass: string= '';
 */
export default class Navbar extends SvelteComponentTyped<NavbarProps, NavbarEvents, NavbarSlots> {
}
export {};
