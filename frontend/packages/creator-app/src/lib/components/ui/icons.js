/**
 * Canonical icon set for the design system.
 *
 * Re-exports the curated subset of `lucide-svelte` icons that the design
 * system is allowed to use. Importing icons from anywhere else (including
 * directly from `lucide-svelte`) is discouraged — go through this module so
 * the icon vocabulary stays consistent across the app.
 *
 * The `ICON_INTENT` frozen map maps semantic intents (e.g. `view`, `delete`)
 * to the icon name in this module. Use it from `statusBadgeProps`,
 * action menus, and anywhere else where intent → icon should be a single
 * source of truth.
 */

export {
	// Actions
	Eye,
	Pencil,
	Trash2,
	Share2,
	Users,
	Plus,
	Search,
	Filter,
	X,
	ChevronDown,
	ChevronUp,
	ChevronRight,
	ChevronLeft,
	FileText,
	Folder,
	FolderPlus,
	FolderInput,
	FolderTree,
	Image,
	Link,
	Youtube,
	Loader2,
	CheckCircle2,
	AlertTriangle,
	AlertCircle,
	Info,
	Copy,
	RefreshCw,
	Download,
	Upload,
	FilePlus,
	MoreHorizontal,
	Database,
	BookOpen,
	GripVertical,
	Inbox,
	Save,
	ExternalLink,
	Settings,
	Lock,
	ArrowRight,
	ArrowLeft
} from 'lucide-svelte';

/**
 * Frozen map of semantic intents → icon names. Keep in sync with the
 * "Canonical iconography" table in the Phase A plan.
 *
 * Consumers should resolve intent → component via this map and the named
 * exports above, e.g.:
 *
 * ```js
 * import * as Icons from '$lib/components/ui/icons.js';
 * const Cmp = Icons[Icons.ICON_INTENT.view];
 * ```
 */
export const ICON_INTENT = Object.freeze({
	view: 'Eye',
	edit: 'Pencil',
	delete: 'Trash2',
	share: 'Share2',
	shared: 'Users',
	add: 'Plus',
	search: 'Search',
	filter: 'Filter',
	close: 'X',
	expand: 'ChevronDown',
	collapse: 'ChevronUp',
	next: 'ChevronRight',
	back: 'ChevronLeft',
	file: 'FileText',
	folder: 'Folder',
	newFolder: 'FolderPlus',
	moveFolder: 'FolderInput',
	folderTree: 'FolderTree',
	image: 'Image',
	link: 'Link',
	youtube: 'Youtube',
	loading: 'Loader2',
	success: 'CheckCircle2',
	warning: 'AlertTriangle',
	danger: 'AlertCircle',
	error: 'AlertCircle',
	info: 'Info',
	copy: 'Copy',
	refresh: 'RefreshCw',
	retry: 'RefreshCw',
	download: 'Download',
	export: 'Download',
	upload: 'Upload',
	import: 'FilePlus',
	overflow: 'MoreHorizontal',
	knowledgeStore: 'Database',
	library: 'BookOpen',
	dragHandle: 'GripVertical',
	empty: 'Inbox',
	save: 'Save',
	openExternal: 'ExternalLink',
	settings: 'Settings',
	locked: 'Lock'
});
