export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "app",
	appPath: "app",
	assets: new Set(["config.js","config.js.sample","favicon.png","img/lamb_1.png","img/lamb_icon.png","md/lamb-news.md"]),
	mimeTypes: {".js":"text/javascript",".png":"image/png",".md":"text/markdown"},
	_: {
		client: {start:"app/immutable/entry/start.Cp2iqpCX.js",app:"app/immutable/entry/app.DFR3p_uA.js",imports:["app/immutable/entry/start.Cp2iqpCX.js","app/immutable/chunks/Ceiogtv-.js","app/immutable/chunks/BGLSpct9.js","app/immutable/entry/app.DFR3p_uA.js","app/immutable/chunks/DhHERQ0H.js","app/immutable/chunks/BGLSpct9.js","app/immutable/chunks/Lv6X1L9C.js","app/immutable/chunks/BMBc-jDI.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js')),
			__memo(() => import('./nodes/4.js')),
			__memo(() => import('./nodes/5.js')),
			__memo(() => import('./nodes/6.js')),
			__memo(() => import('./nodes/7.js')),
			__memo(() => import('./nodes/8.js')),
			__memo(() => import('./nodes/9.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/admin",
				pattern: /^\/admin\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			},
			{
				id: "/api/chat",
				pattern: /^\/api\/chat\/?$/,
				params: [],
				page: null,
				endpoint: __memo(() => import('./entries/endpoints/api/chat/_server.js'))
			},
			{
				id: "/assistants",
				pattern: /^\/assistants\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 4 },
				endpoint: null
			},
			{
				id: "/evaluaitor",
				pattern: /^\/evaluaitor\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 5 },
				endpoint: null
			},
			{
				id: "/evaluaitor/[rubricId]",
				pattern: /^\/evaluaitor\/([^/]+?)\/?$/,
				params: [{"name":"rubricId","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 6 },
				endpoint: null
			},
			{
				id: "/knowledgebases",
				pattern: /^\/knowledgebases\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 7 },
				endpoint: null
			},
			{
				id: "/org-admin",
				pattern: /^\/org-admin\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 8 },
				endpoint: null
			},
			{
				id: "/prompt-templates",
				pattern: /^\/prompt-templates\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 9 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
