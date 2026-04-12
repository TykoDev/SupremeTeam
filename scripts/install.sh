#!/usr/bin/env bash

set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
source_root="$repo_root/skills"
destination="${HOME}/.agents/skills"
claude_destination="${HOME}/.claude/skills"
install_claude=0
requested_teams=()

core_items=(admiral gatekeeper-admiral references save-protocol.md)
all_teams=(design build review azure)
managed_items=(admiral gatekeeper-admiral references save-protocol.md design build review azure)
selected_teams=()

usage() {
    cat <<'EOF'
Usage: bash ./scripts/install.sh [options]

Options:
  --team NAME               Install one team (design, build, review, azure). Repeatable.
  --destination PATH        Override the default agent skill path.
  --install-claude          Mirror the install into ~/.claude/skills.
  --claude-destination PATH Override the Claude Code skill path.
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
        [[ -d "$source_root/$item" ]] || die "Missing source team '$item' at '$source_root/$item'."
    done

    [[ -d "$source_root/design/tech-stacks" ]] || die "Missing design tech-stack directory at '$source_root/design/tech-stacks'."
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
            design|build|review|azure)
                if ! contains_value "$normalized" "${resolved[@]}"; then
                    resolved+=("$normalized")
                fi
                ;;
            *)
                die "Unknown team '$requested'. Use design, build, review, azure, or all."
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
        [[ -d "$target_root/$item" ]] || die "Missing installed team '$item' at '$target_root/$item'."
    done

    if contains_value "design" "${selected_teams[@]}"; then
        [[ -d "$target_root/design/tech-stacks" ]] || die "Missing installed design tech-stack directory at '$target_root/design/tech-stacks'."
    fi
}

install_supreme_team() {
    local target_root="$1"

    clear_destination "$target_root"

    local item
    for item in "${core_items[@]}"; do
        copy_source_item "$item" "$target_root"
    done

    for item in "${selected_teams[@]}"; do
        copy_source_item "$item" "$target_root"
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --team)
            [[ $# -ge 2 ]] || die "Missing value for --team."
            requested_teams+=("$2")
            shift 2
            ;;
        --destination)
            [[ $# -ge 2 ]] || die "Missing value for --destination."
            destination="$2"
            shift 2
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

printf 'Installing Supreme Team to %s\n' "$destination"
install_supreme_team "$destination"

if [[ $install_claude -eq 1 ]]; then
    printf 'Mirroring Supreme Team to %s\n' "$claude_destination"
    install_supreme_team "$claude_destination"
    claude_status="$claude_destination"
else
    claude_status="not requested"
fi

printf '\nSupreme Team installation complete.\n'
printf 'Target: %s\n' "$destination"
printf 'Teams: %s\n' "$(format_team_list)"
printf 'Claude mirror: %s\n' "$claude_status"
printf 'Restart your assistant session if it was already running.\n'