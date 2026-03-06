export * from "@testing-library/dom";
export { UnknownSvelteOptionsError } from "@testing-library/svelte-core";
/**
 * Customize how Svelte renders the component.
 */
export type SvelteComponentOptions<C extends import("@testing-library/svelte-core/types").Component> = import("@testing-library/svelte-core/types").ComponentOptions<C>;
/**
 * Customize how Testing Library sets up the document and binds queries.
 */
export type RenderOptions<Q extends DomTestingLibrary.Queries = typeof DomTestingLibrary.queries> = import("@testing-library/svelte-core/types").SetupOptions & {
    queries?: Q;
};
/**
 * The rendered component and bound testing functions.
 */
export type RenderResult<C extends import("@testing-library/svelte-core/types").Component, Q extends DomTestingLibrary.Queries = typeof DomTestingLibrary.queries> = {
    container: HTMLElement;
    baseElement: HTMLElement;
    component: import("@testing-library/svelte-core/types").Exports<C>;
    debug: (el?: HTMLElement | DocumentFragment) => void;
    rerender: import("@testing-library/svelte-core/types").Rerender<C>;
    unmount: () => void;
} & { [P in keyof Q]: DomTestingLibrary.BoundFunction<Q[P]>; };
export type FireFunction = (...args: Parameters<DomTestingLibrary.FireFunction>) => Promise<ReturnType<DomTestingLibrary.FireFunction>>;
export type FireObject = { [K in DomTestingLibrary.EventType]: (...args: Parameters<DomTestingLibrary.FireObject[K]>) => Promise<ReturnType<DomTestingLibrary.FireObject[K]>>; };
/**
 * Call a function and wait for Svelte to flush pending changes.
 *
 * @template T
 * @param {() => Promise<T> | T} [fn] - A function, which may be `async`, to call before flushing updates.
 * @returns {Promise<T>}
 */
export function act<T>(fn?: () => Promise<T> | T): Promise<T>;
/** Unmount components, remove elements added to `<body>`, and reset `@testing-library/dom`. */
export function cleanup(): void;
/**
 * @typedef {(...args: Parameters<DomTestingLibrary.FireFunction>) => Promise<ReturnType<DomTestingLibrary.FireFunction>>} FireFunction
 */
/**
 * @typedef {{
 *   [K in DomTestingLibrary.EventType]: (...args: Parameters<DomTestingLibrary.FireObject[K]>) => Promise<ReturnType<DomTestingLibrary.FireObject[K]>>
 * }} FireObject
 */
/**
 * Fire an event on an element.
 *
 * Consider using `@testing-library/user-event` instead, if possible.
 * @see https://testing-library.com/docs/user-event/intro/
 *
 * @type {FireFunction & FireObject}
 */
export const fireEvent: FireFunction & FireObject;
/**
 * Customize how Svelte renders the component.
 *
 * @template {import('@testing-library/svelte-core/types').Component} C
 * @typedef {import('@testing-library/svelte-core/types').ComponentOptions<C>} SvelteComponentOptions
 */
/**
 * Customize how Testing Library sets up the document and binds queries.
 *
 * @template {DomTestingLibrary.Queries} [Q=typeof DomTestingLibrary.queries]
 * @typedef {import('@testing-library/svelte-core/types').SetupOptions & { queries?: Q }} RenderOptions
 */
/**
 * The rendered component and bound testing functions.
 *
 * @template {import('@testing-library/svelte-core/types').Component} C
 * @template {DomTestingLibrary.Queries} [Q=typeof DomTestingLibrary.queries]
 *
 * @typedef {{
 *   container: HTMLElement
 *   baseElement: HTMLElement
 *   component: import('@testing-library/svelte-core/types').Exports<C>
 *   debug: (el?: HTMLElement | DocumentFragment) => void
 *   rerender: import('@testing-library/svelte-core/types').Rerender<C>
 *   unmount: () => void
 * } & {
 *   [P in keyof Q]: DomTestingLibrary.BoundFunction<Q[P]>
 * }} RenderResult
 */
/**
 * Render a component into the document.
 *
 * @template {import('@testing-library/svelte-core/types').Component} C
 * @template {DomTestingLibrary.Queries} [Q=typeof DomTestingLibrary.queries]
 *
 * @param {import('@testing-library/svelte-core/types').ComponentImport<C>} Component - The component to render.
 * @param {import('@testing-library/svelte-core/types').ComponentOptions<C>} options - Customize how Svelte renders the component.
 * @param {RenderOptions<Q>} renderOptions - Customize how Testing Library sets up the document and binds queries.
 * @returns {RenderResult<C, Q>} The rendered component and bound testing functions.
 */
export function render<C extends import("@testing-library/svelte-core/types").Component, Q extends DomTestingLibrary.Queries = typeof DomTestingLibrary.queries>(Component: import("@testing-library/svelte-core/types").ComponentImport<C>, options?: import("@testing-library/svelte-core/types").ComponentOptions<C>, renderOptions?: RenderOptions<Q>): RenderResult<C, Q>;
/**
 * Configure `@testing-library/dom` for usage with Svelte.
 *
 * Ensures events fired from `@testing-library/dom`
 * and `@testing-library/user-event` wait for Svelte
 * to flush changes to the DOM before proceeding.
 */
export function setup(): void;
import * as DomTestingLibrary from '@testing-library/dom';
//# sourceMappingURL=pure.d.ts.map