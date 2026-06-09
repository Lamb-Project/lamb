---
topic: moodle-cli
covers: [moodle, courses, users, grades, enrolments, assignments, forums, quizzes, calendar, messages, completion, files, cohorts, roles, site]
answers:
  - "how do I list my Moodle courses"
  - "show me users enrolled in a course"
  - "what grades do my students have"
  - "list assignments in a course"
  - "show forum discussions"
  - "list quizzes in a course"
  - "how do I enrol a user"
  - "show calendar events"
  - "send a message to a user"
  - "check activity completion"
  - "list cohorts"
  - "assign a role to a user"
  - "show site information"
  - "upload a file to Moodle"
---

# moodle-cli: Moodle CLI Integration

The AAC agent can run `moodle ...` commands to interact with a Moodle LMS instance. These commands require the user to have set up a Moodle integration first (use the `setup-moodle` skill).

## Authentication

Before using any moodle command, the user must configure their Moodle credentials:
1. Run the `setup-moodle` skill: `lamb skill load setup-moodle`
2. Follow the steps to provide Moodle URL + Web Services token
3. Verify with `integration test moodle`

## Available Commands

### Site information

| Command | Description |
|---------|-------------|
| `moodle site info` | Show site name, URL, release, version, current user |
| `moodle site functions [--search <term>] [--component <prefix>]` | List available web service functions |

### Course management

| Command | Description |
|---------|-------------|
| `moodle course list` | List all courses (ID, short name, full name, visibility) |
| `moodle course get <course_id>` | Get details of a specific course |
| `moodle course search <query>` | Search courses by name |
| `moodle course contents <course_id>` | Show course sections and modules |
| `moodle course create --fullname <name> --shortname <code> --categoryid <id>` | Create a new course |
| `moodle course update <id> [--fullname <name>] [--shortname <code>] [--visible 0\|1]` | Update a course |
| `moodle course delete <id> [id2 ...]` | Delete courses (requires confirmation) |

### User management

| Command | Description |
|---------|-------------|
| `moodle user me` | Show current authenticated user info |
| `moodle user list [--key email] [--value %%]` | List/search users (use %% as wildcard) |
| `moodle user get <user_id>` | Get user details by ID |
| `moodle user create --username <name> --firstname <fn> --lastname <ln> --email <email> --password <pw>` | Create a new user |
| `moodle user update <id> [--firstname <fn>] [--lastname <ln>] [--email <email>]` | Update a user |
| `moodle user delete <id> [id2 ...]` | Delete users (requires confirmation) |

### Enrolment management

| Command | Description |
|---------|-------------|
| `moodle enrol my-courses` | List courses the current user is enrolled in |
| `moodle enrol list-users <course_id>` | List enrolled users in a course |

### Grade management

| Command | Description |
|---------|-------------|
| `moodle grade get <course_id> [--user-id <id>]` | Get grade items for a course |
| `moodle grade report <course_id> [--user-id <id>]` | Get full grade report for a course |

### Assignment management

| Command | Description |
|---------|-------------|
| `moodle assign list [--course-id <id>]` | List assignments (optionally filtered by course) |
| `moodle assign submissions <assignment_id> [id2 ...]` | Get submissions for assignment(s) |
| `moodle assign grade --assignment-id <id> --user-id <id> --grade <score> [--feedback <text>]` | Grade a submission |

### Forum management

| Command | Description |
|---------|-------------|
| `moodle forum list <course_id>` | List forums in a course |
| `moodle forum discussions <forum_id>` | List discussions in a forum |
| `moodle forum post --forum-id <id> --subject <text> --message <text>` | Post a new discussion to a forum |

### Quiz management

| Command | Description |
|---------|-------------|
| `moodle quiz list <course_id>` | List quizzes in a course |
| `moodle quiz attempts <quiz_id> [--user-id <id>]` | List quiz attempts |

### Calendar management

| Command | Description |
|---------|-------------|
| `moodle calendar events [--course-id <id>]` | List calendar events (optionally filtered by course) |
| `moodle calendar create --name <name> --timestart <unix_ts> [--duration <secs>] [--description <text>] [--course-id <id>] [--type user\|course\|site]` | Create a calendar event |

### Messaging

| Command | Description |
|---------|-------------|
| `moodle message send <user_id> <text>` | Send a message to a user |
| `moodle message list [--from-user <id>]` | List recent messages |
| `moodle message conversations` | List conversations |

### Activity completion

| Command | Description |
|---------|-------------|
| `moodle completion status <course_id> [--user-id <id>]` | Show activity completion status for a course |
| `moodle completion update <cmid> <true\|false>` | Manually mark an activity as complete or incomplete |

### File management

| Command | Description |
|---------|-------------|
| `moodle file list <contextid> [--component user] [--filearea private] [--itemid 0] [--filepath /]` | List files in a Moodle file area |
| `moodle file upload <local_path> [--component user] [--filearea draft] [--itemid 0]` | Upload a file to Moodle |

### Cohort management

| Command | Description |
|---------|-------------|
| `moodle cohort list` | List all cohorts |
| `moodle cohort create --name <name> [--idnumber <code>] [--description <text>]` | Create a cohort |
| `moodle cohort delete <id> [id2 ...]` | Delete cohorts (requires confirmation) |
| `moodle cohort add-members <cohort_id> <user_id> [user_id ...]` | Add users to a cohort |
| `moodle cohort remove-members <cohort_id> <user_id> [user_id ...]` | Remove users from a cohort |

### Role management

| Command | Description |
|---------|-------------|
| `moodle role assign --role-id <id> --user-id <id> --context-id <id>` | Assign a role to a user in a context |
| `moodle role unassign --role-id <id> --user-id <id> --context-id <id>` | Unassign a role from a user in a context |

### Generic API call

| Command | Description |
|---------|-------------|
| `moodle call <function_name> [-P key=value ...]` | Call any Moodle web service function directly |

## Usage Tips

- All commands return structured data. The agent will present it in a readable format.
- **Timestamps**: Moodle returns Unix timestamps (e.g. `duedate: 1744320000`). The agent will always convert these to readable dates automatically — no need to ask.
- For destructive operations (delete, update), the agent will ask for confirmation.
- Use `moodle course list` first to discover course IDs, then drill into specific courses.
- Use `moodle enrol list-users <course_id>` to see who is enrolled in a course.
- Use `moodle grade report <course_id>` to get a full picture of student performance.
- The `moodle call` command is an escape hatch for any Moodle WS function not covered by the other commands.

## Privacy & Data Access Rules

**CRITICAL: The moodle-cli runs with the credentials of the LAMB user who configured the Moodle integration. The agent MUST enforce these rules:**

### Rule 1: Only the authenticated user's data

All moodle commands execute using **the Moodle token of the user who set up the integration**. The agent may ONLY query data that belongs to or is accessible to this authenticated user. Never query data about a specific different user unless it's in the context of the authenticated user's own courses (e.g. seeing who is enrolled in a course the authenticated user teaches).

### Rule 2: Never query another user by ID

Commands that accept a `--user-id` or `<user_id>` parameter (`moodle user get <id>`, `moodle grade get --user-id <id>`, `moodle grade report --user-id <id>`, `moodle completion status --user-id <id>`, `moodle message send <user_id>`) MUST only be used with the authenticated user's own ID. If the user asks about another person's data, explain that you can only show data for the authenticated user.

Exception: `moodle enrol list-users <course_id>` is allowed because it shows enrolment in a course context (the authenticated user likely has permission to see this as a teacher).

### Rule 3: Never expose other users' personal data

If a command returns data about other users (e.g. `moodle user list` shows all users), do NOT display personal details (email, full name) of users other than the authenticated user. Summarize counts instead.

### Rule 4: Scope queries to the authenticated user

When the user asks "show me my courses", "what are my grades", etc., use `moodle enrol my-courses` (not `moodle course list`). Use `moodle user me` (not `moodle user get <id>`). Prefer self-scoped commands over general ones.

### Rule 5: Refuse unauthorized queries

If the user asks you to look up another specific user's data (grades, profile details, messages, completion status), politely refuse: "I can only access Moodle data for your account. I cannot look up other users' private information."