/** Display-only sizing. Never enters the agent's prompt. */
export function sidebarSize(viewport, ratio = .35) {
    const mobile = viewport < 920;
    const min = Math.max(360, viewport * .25);
    const max = Math.min(viewport - 560, viewport * .55);
    const preferred = Number.isFinite(ratio) ? ratio : .35;
    return { mobile, min, max, width: mobile ? viewport : Math.min(max, Math.max(min, viewport * preferred)) };
}
