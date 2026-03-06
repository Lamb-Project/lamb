export default Nav;
type Nav = {
    $on?(type: string, callback: (e: any) => void): () => void;
    $set?(props: Partial<Record<string, never>>): void;
};
declare const Nav: import("svelte").Component<Record<string, never>, {}, "">;
