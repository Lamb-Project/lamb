export default ConfirmationModal;
type ConfirmationModal = {
    $on?(type: string, callback: (e: any) => void): () => void;
    $set?(props: Partial<$$ComponentProps>): void;
};
declare const ConfirmationModal: import("svelte").Component<{
    isOpen?: boolean;
    isLoading?: boolean;
    title?: string;
    message?: string;
    confirmText?: string;
    cancelText?: string;
    variant?: string;
    onconfirm?: Function;
    oncancel?: Function;
}, {}, "isOpen" | "isLoading">;
type $$ComponentProps = {
    isOpen?: boolean;
    isLoading?: boolean;
    title?: string;
    message?: string;
    confirmText?: string;
    cancelText?: string;
    variant?: string;
    onconfirm?: Function;
    oncancel?: Function;
};
