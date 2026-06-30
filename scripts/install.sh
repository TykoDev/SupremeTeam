#!/usr/bin/env bash

set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
source_root="$repo_root/skills"
destination="${HOME}/.agents/skills"
codex_destination="${HOME}/.codex/skills"
claude_destination="${HOME}/.claude/skills"
cursor_destination="${HOME}/.cursor/skills"
opencode_destination="${HOME}/.config/opencode/skills"
install_claude=0
register_hooks=0
codex_target_explicit=0
requested_teams=()
requested_targets=()

# Core components are always installed: the Admiral pipeline spine, the runtime
# harness (hooks + deterministic gate engine), and the root doctrine/protocol files.
core_items=(
    admiral
    gatekeeper-admiral
    session-memory
    investigate
    skill-maker
    harness
    design-doctrine.md
    grill-me-doctrine.md
    harness-doctrine.md
    mcp-tools.md
    routing-doctrine.md
    save-protocol.md
)

# Friendly team name -> source directory under skills/.
all_teams=(design build review browser release safety testing)

team_dir() {
    case "$1" in
        design)  printf 'design' ;;
        build)   printf 'build' ;;
        review)  printf 'review' ;;
        browser) printf 'browser-automation' ;;
        release) printf 'release-and-deployment' ;;
        safety)  printf 'safety-guardrails' ;;
        testing) printf 'testing-and-qa' ;;
        *)       return 1 ;;
    esac
}

managed_items=("${core_items[@]}")
for team in "${all_teams[@]}"; do
    managed_items+=("$(team_dir "$team")")
done

# Paths from older Supreme Team layouts that are no longer shipped. Removed from
# the destination on each run so an in-place update over an old install does not
# leave stale directories behind. Not part of the source-layout assertion.
legacy_items=(azure references design/tech-stacks)

selected_teams=()

usage() {
    cat <<'EOF'
Usage: bash ./scripts/install.sh [options]

Options:
  --team NAME               Install one team. Repeatable. One of:
                              design, build, review,
                              browser, release, safety, testing
  --target NAME             Install host-native support for one host. Repeatable.
                              One of: auto, codex, claude, cursor, opencode.
                              Default: auto.
  --destination PATH        Override the default agent skill path.
  --codex-destination PATH  Override the Codex skill path.
  --register-hooks          Register runtime harness hooks for selected hosts.
  --install-claude          Mirror the install into ~/.claude/skills.
  --claude-destination PATH Override the Claude Code skill path.
  --cursor-destination PATH Override the Cursor skill path.
  --opencode-destination PATH Override the OpenCode skill path.
  -h, --help                Show this help message.

If no --team options are provided, all teams are installed.
EOF
}

die() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

contains_value() {
    local needle="$1"
    shift || true

    local value
    for value in "$@"; do
        if [[ "$value" == "$needle" ]]; then
            return 0
        fi
    done

    return 1
}

assert_source_layout() {
    [[ -d "$source_root" ]] || die "Missing skills source directory at '$source_root'."

    local item
    for item in "${core_items[@]}"; do
        [[ -e "$source_root/$item" ]] || die "Missing source item '$item' at '$source_root/$item'."
    done

    for item in "${all_teams[@]}"; do
        [[ -d "$source_root/$(team_dir "$item")" ]] || die "Missing source team '$item' at '$source_root/$(team_dir "$item")'."
    done
}

resolve_teams() {
    if [[ ${#requested_teams[@]} -eq 0 ]]; then
        selected_teams=("${all_teams[@]}")
        return
    fi

    local requested normalized
    local resolved=()

    for requested in "${requested_teams[@]}"; do
        normalized="$(printf '%s' "$requested" | tr '[:upper:]' '[:lower:]')"

        case "$normalized" in
            all)
                selected_teams=("${all_teams[@]}")
                return
                ;;
            design|build|review|browser|release|safety|testing)
                if ! contains_value "$normalized" "${resolved[@]}"; then
                    resolved+=("$normalized")
                fi
                ;;
            *)
                die "Unknown team '$requested'. Use design, build, review, browser, release, safety, testing, or all."
                ;;
        esac
    done

    selected_teams=("${resolved[@]}")
}

clear_destination() {
    local target_root="$1"

    mkdir -p "$target_root"

    local item
    for item in "${managed_items[@]}"; do
        rm -rf "$target_root/$item"
    done

    for item in "${legacy_items[@]}"; do
        rm -rf "$target_root/$item"
    done
}

copy_source_item() {
    local item_name="$1"
    local target_root="$2"

    cp -R "$source_root/$item_name" "$target_root/"
}

assert_destination_layout() {
    local target_root="$1"

    local item
    for item in "${core_items[@]}"; do
        [[ -e "$target_root/$item" ]] || die "Missing installed item '$item' at '$target_root/$item'."
    done

    for item in "${selected_teams[@]}"; do
        [[ -d "$target_root/$(team_dir "$item")" ]] || die "Missing installed team '$item' at '$target_root/$(team_dir "$item")'."
    done
}

install_supreme_team() {
    local target_root="$1"

    clear_destination "$target_root"

    local item
    for item in "${core_items[@]}"; do
        copy_source_item "$item" "$target_root"
    done

    for item in "${selected_teams[@]}"; do
        copy_source_item "$(team_dir "$item")" "$target_root"
    done

    assert_destination_layout "$target_root"
}

format_team_list() {
    local separator=""
    local team

    for team in "${selected_teams[@]}"; do
        printf '%s%s' "$separator" "$team"
        separator=", "
    done
}

host_detected() {
    case "$1" in
        codex)
            command -v codex >/dev/null 2>&1 || [[ -d "$HOME/.codex" ]]
            ;;
        claude)
            command -v claude >/dev/null 2>&1 || [[ -d "$HOME/.claude" ]]
            ;;
        cursor)
            command -v cursor >/dev/null 2>&1 || [[ -d "$HOME/.cursor" ]]
            ;;
        opencode)
            command -v opencode >/dev/null 2>&1 || [[ -d "$HOME/.config/opencode" ]]
            ;;
        *)
            return 1
            ;;
    esac
}

add_selected_target() {
    local target="$1"

    if ! contains_value "$target" "${selected_targets[@]}"; then
        selected_targets+=("$target")
    fi
}

resolve_targets() {
    local target normalized

    selected_targets=()

    if [[ ${#requested_targets[@]} -eq 0 ]]; then
        requested_targets=(auto)
    fi

    for target in "${requested_targets[@]}"; do
        normalized="$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]')"
        case "$normalized" in
            auto)
                for detected in codex claude cursor opencode; do
                    if host_detected "$detected"; then
                        add_selected_target "$detected"
                    fi
                done
                ;;
            codex|claude|cursor|opencode)
                if [[ "$normalized" == codex ]]; then
                    codex_target_explicit=1
                fi
                add_selected_target "$normalized"
                ;;
            *)
                die "Unknown target '$target'. Use auto, codex, claude, cursor, or opencode."
                ;;
        esac
    done

    if [[ $install_claude -eq 1 ]]; then
        add_selected_target claude
    fi
}

python_satisfies_minimum() {
    local candidate="$1"
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)' >/dev/null 2>&1
}

find_compatible_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && python_satisfies_minimum "$candidate"; then
            printf '%s' "$candidate"
            return 0
        fi
    done

    return 1
}

warn_python_readiness() {
    if ! find_compatible_python >/dev/null 2>&1; then
        printf 'Warning: Python 3.13+ was not found. Skill files will still be copied, but hook verification and registration require Python 3.13 or newer.\n' >&2
    fi
}

find_python() {
    local python
    if python="$(find_compatible_python)"; then
        printf '%s' "$python"
        return 0
    fi

    die "Python 3.13 or newer is required to register runtime harness hooks."
}

register_harness_hooks() {
    if [[ ${#selected_targets[@]} -eq 0 ]]; then
        printf 'Hook registration skipped: no host targets were detected. Pass --target codex, --target claude, --target cursor, or --target opencode to choose explicitly.\n'
        return
    fi

    local python hook_args target
    python="$(find_python)"
    hook_args=("$repo_root/scripts/install_hooks.py" --hook-root "$destination/harness/hooks")

    for target in "${selected_targets[@]}"; do
        hook_args+=(--target "$target")
    done

    "$python" "${hook_args[@]}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --team)
            [[ $# -ge 2 ]] || die "Missing value for --team."
            requested_teams+=("$2")
            shift 2
            ;;
        --target)
            [[ $# -ge 2 ]] || die "Missing value for --target."
            requested_targets+=("$2")
            shift 2
            ;;
        --destination)
            [[ $# -ge 2 ]] || die "Missing value for --destination."
            destination="$2"
            shift 2
            ;;
        --codex-destination)
            [[ $# -ge 2 ]] || die "Missing value for --codex-destination."
            codex_destination="$2"
            shift 2
            ;;
        --register-hooks)
            register_hooks=1
            shift
            ;;
        --install-claude)
            install_claude=1
            shift
            ;;
        --claude-destination)
            [[ $# -ge 2 ]] || die "Missing value for --claude-destination."
            claude_destination="$2"
            shift 2
            ;;
        --cursor-destination)
            [[ $# -ge 2 ]] || die "Missing value for --cursor-destination."
            cursor_destination="$2"
            shift 2
            ;;
        --opencode-destination)
            [[ $# -ge 2 ]] || die "Missing value for --opencode-destination."
            opencode_destination="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown argument '$1'. Use --help for usage."
            ;;
    esac
done

assert_source_layout
resolve_teams
resolve_targets
warn_python_readiness

printf 'Installing Supreme Team to %s\n' "$destination"
install_supreme_team "$destination"

mirror_status=()

if contains_value codex "${selected_targets[@]}" && { [[ $codex_target_explicit -eq 1 ]] || [[ -d "$codex_destination" ]]; }; then
    printf 'Mirroring Supreme Team to %s\n' "$codex_destination"
    install_supreme_team "$codex_destination"
    mirror_status+=("codex=$codex_destination")
fi

if contains_value claude "${selected_targets[@]}"; then
    printf 'Mirroring Supreme Team to %s\n' "$claude_destination"
    install_supreme_team "$claude_destination"
    mirror_status+=("claude=$claude_destination")
fi

if contains_value cursor "${selected_targets[@]}"; then
    printf 'Mirroring Supreme Team to %s\n' "$cursor_destination"
    install_supreme_team "$cursor_destination"
    mirror_status+=("cursor=$cursor_destination")
fi

if contains_value opencode "${selected_targets[@]}"; then
    printf 'Mirroring Supreme Team to %s\n' "$opencode_destination"
    install_supreme_team "$opencode_destination"
    mirror_status+=("opencode=$opencode_destination")
fi

if [[ $register_hooks -eq 1 ]]; then
    register_harness_hooks
fi

printf '\nSupreme Team installation complete.\n'
printf 'Target: %s\n' "$destination"
if [[ ${#selected_targets[@]} -gt 0 ]]; then
    printf 'Host targets: %s\n' "${selected_targets[*]}"
else
    printf 'Host targets: none detected\n'
fi
if [[ ${#mirror_status[@]} -gt 0 ]]; then
    printf 'Host mirrors: %s\n' "${mirror_status[*]}"
else
    printf 'Host mirrors: none\n'
fi
printf 'Teams: %s\n' "$(format_team_list)"
if [[ $register_hooks -eq 1 ]]; then
    printf 'Hook registration: requested\n'
else
    printf 'Hook registration: not requested\n'
fi
printf 'Restart your assistant session if it was already running.\n'
if [[ $register_hooks -ne 1 ]]; then
    printf 'Run again with --register-hooks to register runtime harness hooks for the selected hosts.\n'
fi
