export default LanguageSelector;
type LanguageSelector = {
    $on?(type: string, callback: (e: any) => void): () => void;
    $set?(props: Partial<$$ComponentProps>): void;
};
declare const LanguageSelector: import("svelte").Component<{
    size?: "normal" | "small";
}, {}, "">;
type $$ComponentProps = {
    size?: "normal" | "small";
};
