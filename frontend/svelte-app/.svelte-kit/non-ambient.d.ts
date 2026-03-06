
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	export interface AppTypes {
		RouteId(): "/" | "/admin" | "/api" | "/api/chat" | "/assistants" | "/evaluaitor" | "/evaluaitor/[rubricId]" | "/knowledgebases" | "/org-admin" | "/prompt-templates";
		RouteParams(): {
			"/evaluaitor/[rubricId]": { rubricId: string }
		};
		LayoutParams(): {
			"/": { rubricId?: string };
			"/admin": Record<string, never>;
			"/api": Record<string, never>;
			"/api/chat": Record<string, never>;
			"/assistants": Record<string, never>;
			"/evaluaitor": { rubricId?: string };
			"/evaluaitor/[rubricId]": { rubricId: string };
			"/knowledgebases": Record<string, never>;
			"/org-admin": Record<string, never>;
			"/prompt-templates": Record<string, never>
		};
		Pathname(): "/" | "/admin" | "/admin/" | "/api" | "/api/" | "/api/chat" | "/api/chat/" | "/assistants" | "/assistants/" | "/evaluaitor" | "/evaluaitor/" | `/evaluaitor/${string}` & {} | `/evaluaitor/${string}/` & {} | "/knowledgebases" | "/knowledgebases/" | "/org-admin" | "/org-admin/" | "/prompt-templates" | "/prompt-templates/";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): "/config.js" | "/config.js.sample" | "/favicon.png" | "/img/lamb_1.png" | "/img/lamb_icon.png" | "/md/lamb-news.md" | string & {};
	}
}