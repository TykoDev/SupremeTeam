#!/usr/bin/env bash

set -euo pipefail

script_dir="$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd -P)"
repo_root="$(CDPATH= cd -P -- "$script_dir/.." && pwd -P)"
source_root="$repo_root/skills"
items_file="$script_dir/install-items.txt"
destination="${HOME:-}/.agents/skills"
codex_destination="${HOME:-}/.codex/skills"
claude_destination="${HOME:-}/.claude/skills"
cursor_destination="${HOME:-}/.cursor/skills"
opencode_destination="${HOME:-}/.config/opencode/skills"
install_claude=0
register_hooks=0
dry_run=0
codex_target_explicit=0
cursor_target_explicit=0
requested_teams=()
requested_targets=()
selected_teams=()
selected_targets=()

# The installer only replaces or removes what it can show it installed. Every
# install root gets a manifest listing the items the last run put there, and
# every directory it creates carries a marker file. A file is owned when the
# manifest lists it and a directory when it carries the marker. Anything else
# that shares a managed name is moved to a backup folder, never deleted.
manifest_name=".supremeteam-manifest"
manifest_header="supremeteam-manifest 1"
marker_name=".supremeteam-managed"
stage_marker_name=".supremeteam-stage"
# Trimming a CRLF line must not depend on how a given bash treats $'...' inside a
# quoted ${...}, so the carriage return lives in a variable.
carriage_return=$'\r'

# install-items.txt is the one item list; install.ps1 reads the same file.
core_items=()
seed_items=()
all_teams=()
team_pairs=()
legacy_dirs=()
legacy_pairs=()
managed_items=()
install_items=()
old_items=()
backup_dirs=()
manifest_foreign=0
stage=""
stage_root=""
stage_committed=0
backup_dir=""

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
  --dry-run                 Show what would change and write nothing.
  -h, --help                Show this help message.

If no --team options are provided, all teams are installed.

Only items this installer put in a folder are replaced or removed. Anything else
that shares a name with an installed item is moved to
<folder>.supremeteam-backup/<timestamp>/ and listed in the summary.
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

join_words() {
    local separator="$1" joined="" word
    shift

    for word in "$@"; do
        joined="$joined${joined:+$separator}$word"
    done

    printf '%s' "$joined"
}

# Names become path components, so they are checked before any path is built
# from them: no separators, no leading dot or dash, nothing a glob would expand.
valid_name() {
    case "$1" in
        ''|.*|-*|*[![:alnum:]._-]*)
            return 1
            ;;
    esac

    return 0
}

load_items() {
    [[ -f "$items_file" ]] || die "Missing item list at '$items_file'."

    local line kind name rest member pair item dir
    local members=()

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%"$carriage_return"}"
        case "$line" in
            ''|'#'*)
                continue
                ;;
        esac

        kind=""
        name=""
        rest=""
        read -r kind name rest <<< "$line"
        valid_name "$name" || die "Invalid name '$name' in $items_file."

        case "$kind" in
            core|seed)
                [[ -z "$rest" ]] || die "'$kind $name' takes exactly one name in $items_file."
                core_items+=("$name")
                if [[ "$kind" == seed ]]; then
                    seed_items+=("$name")
                fi
                ;;
            team|legacy)
                members=()
                read -r -a members <<< "$rest"
                [[ ${#members[@]} -gt 0 ]] || die "'$kind $name' lists no items in $items_file."
                for member in ${members[@]+"${members[@]}"}; do
                    valid_name "$member" || die "Invalid name '$member' in $items_file."
                    if [[ "$kind" == team ]]; then
                        team_pairs+=("$name:$member")
                    else
                        legacy_pairs+=("$name:$member")
                    fi
                done
                if [[ "$kind" == team ]]; then
                    if ! contains_value "$name" ${all_teams[@]+"${all_teams[@]}"}; then
                        all_teams+=("$name")
                    fi
                elif ! contains_value "$name" ${legacy_dirs[@]+"${legacy_dirs[@]}"}; then
                    legacy_dirs+=("$name")
                fi
                ;;
            *)
                die "Unknown record '$kind' in $items_file."
                ;;
        esac
    done < "$items_file"

    [[ ${#core_items[@]} -gt 0 && ${#team_pairs[@]} -gt 0 ]] || die "$items_file lists no core or team items."

    managed_items=()
    for item in ${core_items[@]+"${core_items[@]}"}; do
        managed_items+=("$item")
    done
    for pair in ${team_pairs[@]+"${team_pairs[@]}"}; do
        item="${pair#*:}"
        if ! contains_value "$item" ${managed_items[@]+"${managed_items[@]}"}; then
            managed_items+=("$item")
        fi
    done

    for dir in ${legacy_dirs[@]+"${legacy_dirs[@]}"}; do
        if contains_value "$dir" ${managed_items[@]+"${managed_items[@]}"}; then
            die "Legacy directory '$dir' is also an installed item in $items_file."
        fi
    done
}

team_items() {
    local pair

    for pair in ${team_pairs[@]+"${team_pairs[@]}"}; do
        if [[ "${pair%%:*}" == "$1" ]]; then
            printf '%s\n' "${pair#*:}"
        fi
    done
}

assert_source_layout() {
    [[ -d "$source_root" ]] || die "Missing skills source directory at '$source_root'."

    local item
    for item in ${managed_items[@]+"${managed_items[@]}"}; do
        [[ -e "$source_root/$item" ]] || die "Missing source item '$item' at '$source_root/$item'."
    done
}

resolve_teams() {
    if [[ ${#requested_teams[@]} -eq 0 ]]; then
        selected_teams=(${all_teams[@]+"${all_teams[@]}"})
        return
    fi

    local requested normalized
    local resolved=()

    for requested in "${requested_teams[@]}"; do
        normalized="$(printf '%s' "$requested" | tr '[:upper:]' '[:lower:]')"

        if [[ "$normalized" == all ]]; then
            selected_teams=(${all_teams[@]+"${all_teams[@]}"})
            return
        fi

        if ! contains_value "$normalized" ${all_teams[@]+"${all_teams[@]}"}; then
            die "Unknown team '$requested'. Use $(join_words ', ' ${all_teams[@]+"${all_teams[@]}"}), or all."
        fi

        if ! contains_value "$normalized" ${resolved[@]+"${resolved[@]}"}; then
            resolved+=("$normalized")
        fi
    done

    selected_teams=(${resolved[@]+"${resolved[@]}"})
}

# Core items and the selected teams' items, each once.
build_install_items() {
    local item team

    install_items=()
    for item in ${core_items[@]+"${core_items[@]}"}; do
        install_items+=("$item")
    done

    for team in ${selected_teams[@]+"${selected_teams[@]}"}; do
        while IFS= read -r item; do
            if ! contains_value "$item" ${install_items[@]+"${install_items[@]}"}; then
                install_items+=("$item")
            fi
        done < <(team_items "$team")
    done
}

# Absolute physical path of a directory. One that does not exist yet is resolved
# through its nearest existing parent.
resolve_path() {
    local path="$1" parent base

    while [[ ${#path} -gt 1 && "$path" == */ ]]; do
        path="${path%/}"
    done

    if [[ -d "$path" ]]; then
        (CDPATH= cd -P -- "$path" && pwd -P)
        return
    fi

    if [[ -e "$path" || -L "$path" ]]; then
        die "'$path' exists and is not a directory."
    fi

    case "/$path/" in
        */../*)
            die "'$path' does not exist yet and contains '..'; pass a normalized path."
            ;;
    esac

    parent="$(dirname -- "$path")"
    base="$(basename -- "$path")"
    parent="$(resolve_path "$parent")"

    if [[ "$parent" == / ]]; then
        printf '/%s' "$base"
    else
        printf '%s/%s' "$parent" "$base"
    fi
}

# An install root is a skills folder, so the filesystem root, the home directory
# and its parents, anything overlapping this checkout, and the current directory
# spelled as a relative path (unless it already holds an install) are refused
# before anything is written. A full path to the current directory is deliberate.
assert_safe_root() {
    local label="$1" path="$2" resolved home_path here

    [[ -n "$path" ]] || die "The $label destination is empty."
    resolved="$(resolve_path "$path")"
    home_path="$(resolve_path "$HOME")"
    here="$(pwd -P)"

    if [[ "$resolved" == / ]]; then
        die "Refusing to install into the filesystem root ($label destination)."
    fi

    case "$home_path/" in
        "$resolved/"*)
            die "Refusing to install into '$resolved' ($label destination): it is your home directory or one of its parents."
            ;;
    esac

    case "$repo_root/" in
        "$resolved/"*)
            die "Refusing to install into '$resolved' ($label destination): it contains the Supreme Team checkout."
            ;;
    esac

    case "$resolved/" in
        "$source_root/"*)
            die "Refusing to install into '$resolved' ($label destination): it is inside the skills source directory."
            ;;
    esac

    if [[ "$path" != /* && "$resolved" == "$here" ]] && ! supreme_team_install_present "$resolved"; then
        die "Refusing to install into '$resolved' ($label destination): it is the current directory and holds no Supreme Team install. Pass the skills folder's full path instead."
    fi
}

# Reads the record of the last run. Something at its path that is not a record
# (another file, a link, a directory) is not the installer's to overwrite.
read_manifest() {
    local file="$1/$manifest_name" line name

    old_items=()
    manifest_foreign=0
    [[ -e "$file" || -L "$file" ]] || return 0

    if [[ -L "$file" || ! -f "$file" ]]; then
        manifest_foreign=1
        return 0
    fi

    IFS= read -r line < "$file" || true
    line="${line%"$carriage_return"}"
    if [[ "$line" != "$manifest_header" ]]; then
        printf 'Warning: ignoring %s, which is not a Supreme Team install record.\n' "$file" >&2
        manifest_foreign=1
        return 0
    fi

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%"$carriage_return"}"
        case "$line" in
            'item '*)
                name="${line#item }"
                if valid_name "$name" && ! contains_value "$name" ${old_items[@]+"${old_items[@]}"}; then
                    old_items+=("$name")
                fi
                ;;
        esac
    done < "$file"
}

# Prints absent, owned or foreign for $root/$name. A symlink is never owned, so
# it is moved aside as a link and never followed.
item_state() {
    local path="$1/$2"

    if [[ -L "$path" ]]; then
        printf 'foreign'
    elif [[ ! -e "$path" ]]; then
        printf 'absent'
    elif [[ -d "$path" ]]; then
        if [[ -f "$path/$marker_name" && ! -L "$path/$marker_name" ]]; then
            printf 'owned'
        else
            printf 'foreign'
        fi
    elif [[ -f "$path" ]] && contains_value "$2" ${old_items[@]+"${old_items[@]}"}; then
        printf 'owned'
    else
        printf 'foreign'
    fi
}

# A directory from an older layout is recognised only while it holds nothing
# but the entries that layout put there.
legacy_dir_matches() {
    local path="$1/$2" entry pair found count=0

    [[ -d "$path" && ! -L "$path" ]] || return 1

    while IFS= read -r entry; do
        [[ -n "$entry" ]] || continue
        count=$((count + 1))
        found=0
        for pair in ${legacy_pairs[@]+"${legacy_pairs[@]}"}; do
            if [[ "$pair" == "$2:$entry" ]]; then
                found=1
                break
            fi
        done
        [[ $found -eq 1 ]] || return 1
    done < <(ls -A "$path")

    [[ $count -gt 0 ]]
}

supreme_team_install_present() {
    local root="$1" item

    [[ -d "$root" ]] || return 1
    [[ -f "$root/$manifest_name" ]] && return 0

    for item in ${managed_items[@]+"${managed_items[@]}"}; do
        if [[ -d "$root/$item" && -f "$root/$item/$marker_name" ]]; then
            return 0
        fi
    done

    # An install from before the ownership records existed.
    [[ -f "$root/admiral/SKILL.md" && -f "$root/gatekeeper-admiral/SKILL.md" ]]
}

# The only place anything is deleted: a staging directory this installer created,
# recognised by its name and by the marker written inside it. Items that are
# replaced or dropped are moved into it first, so what it holds is all the
# installer's own.
remove_stage() {
    local path="$1"

    case "$path" in
        */.supremeteam-stage.*)
            ;;
        *)
            return 0
            ;;
    esac

    [[ -f "$path/$stage_marker_name" ]] || return 0
    rm -rf -- "$path"
}

# An aborted run puts back an owned item it had moved aside whose replacement never
# landed, so the install is left as it was found. A committed run keeps its removals.
restore_retired() {
    local retired name

    for retired in "$stage"/old/*; do
        name="${retired##*/}"
        if [[ -e "$retired" && ! -e "$stage_root/$name" && ! -L "$stage_root/$name" ]]; then
            mv -- "$retired" "$stage_root/$name" || true
        fi
    done
}

discard_stage() {
    if [[ -n "$stage" ]]; then
        if [[ $stage_committed -eq 0 ]]; then
            restore_retired
        fi
        remove_stage "$stage" || true
        stage=""
    fi
}

# An interrupted run can leave its staging directory behind.
discard_old_stages() {
    local candidate

    for candidate in "$1"/.supremeteam-stage.*; do
        if [[ -d "$candidate" && ! -L "$candidate" ]]; then
            remove_stage "$candidate"
        fi
    done
}

stage_item() {
    local item="$1"

    cp -R -- "$source_root/$item" "$stage/new/"
    # A source item that is itself a link is copied as a link; writing the marker
    # through it would change the source tree.
    if [[ -d "$stage/new/$item" && ! -L "$stage/new/$item" ]]; then
        printf 'supremeteam-managed 1\n' > "$stage/new/$item/$marker_name"
    fi
}

# The backup folder sits next to the install root, not inside it, so a host that
# scans the root for skills never picks up the moved-aside copies.
make_backup_dir() {
    local base="$1.supremeteam-backup" stamp candidate n=0

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p -- "$base" || die "Cannot create the backup folder '$base'; nothing was changed."

    candidate="$base/$stamp"
    while ! mkdir -- "$candidate" 2>/dev/null; do
        n=$((n + 1))
        if [[ $n -ge 100 ]]; then
            die "Cannot create a backup folder under '$base'; nothing was changed."
        fi
        candidate="$base/$stamp-$n"
    done

    backup_dir="$candidate"
}

# Moves the staged copy of $item into place. What is there now is moved aside
# first: an owned copy into the staging directory, anything else into the backup
# folder. If the final move fails, the previous copy is put back.
swap_in() {
    local root="$1" item="$2" state="$3"
    local target="$root/$item"

    case "$state" in
        owned)
            mv -- "$target" "$stage/old/$item"
            ;;
        foreign)
            mv -- "$target" "$backup_dir/$item"
            ;;
    esac

    if ! mv -- "$stage/new/$item" "$target"; then
        case "$state" in
            owned)
                mv -- "$stage/old/$item" "$target"
                ;;
            foreign)
                mv -- "$backup_dir/$item" "$target"
                ;;
        esac
        die "Could not install '$item' into '$root'; the previous copy was put back."
    fi
}

write_manifest() {
    local root="$1" item

    {
        printf '%s\n' "$manifest_header"
        printf 'installed_at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'teams %s\n' "$(join_words ' ' ${selected_teams[@]+"${selected_teams[@]}"})"
        for item in ${install_items[@]+"${install_items[@]}"}; do
            printf 'item %s\n' "$item"
        done
    } > "$stage/manifest"

    mv -f -- "$stage/manifest" "$root/$manifest_name"
}

assert_installed_layout() {
    local root="$1" item

    for item in ${install_items[@]+"${install_items[@]}"}; do
        [[ -e "$root/$item" ]] || die "Missing installed item '$item' at '$root/$item'."
    done
}

report_list() {
    local label="$1"
    shift

    if [[ $# -gt 0 ]]; then
        printf '  %s: %s\n' "$label" "$(join_words ' ' "$@")"
    fi
}

install_supreme_team() {
    local root item state
    local add_items=() replace_items=() kept_items=() foreign_items=() stale_items=() aside_items=()

    root="$(resolve_path "$1")"
    read_manifest "$root"

    if [[ -d "$root/$manifest_name" ]]; then
        die "'$root/$manifest_name' is a directory; move it away and run the installer again."
    fi

    for item in ${install_items[@]+"${install_items[@]}"}; do
        state="$(item_state "$root" "$item")"
        if [[ "$state" != absent ]] && contains_value "$item" ${seed_items[@]+"${seed_items[@]}"}; then
            kept_items+=("$item")
            continue
        fi
        case "$state" in
            absent)
                add_items+=("$item")
                ;;
            owned)
                replace_items+=("$item")
                ;;
            *)
                foreign_items+=("$item")
                ;;
        esac
    done

    for item in ${old_items[@]+"${old_items[@]}"}; do
        if ! contains_value "$item" ${install_items[@]+"${install_items[@]}"} \
            && [[ "$(item_state "$root" "$item")" == owned ]]; then
            stale_items+=("$item")
        fi
    done

    # Moved aside without being replaced: a recognised old-layout directory, and
    # a file, link or directory sitting where the record belongs.
    for item in ${legacy_dirs[@]+"${legacy_dirs[@]}"}; do
        if legacy_dir_matches "$root" "$item"; then
            aside_items+=("$item")
        fi
    done
    if [[ $manifest_foreign -eq 1 ]]; then
        aside_items+=("$manifest_name")
    fi

    if [[ $dry_run -eq 1 ]]; then
        report_list "would add" ${add_items[@]+"${add_items[@]}"}
        report_list "would replace" ${replace_items[@]+"${replace_items[@]}"}
        report_list "would keep, yours" ${kept_items[@]+"${kept_items[@]}"}
        report_list "would remove, no longer shipped" ${stale_items[@]+"${stale_items[@]}"}
        report_list "would move aside to $root.supremeteam-backup, not installed by Supreme Team" \
            ${foreign_items[@]+"${foreign_items[@]}"} ${aside_items[@]+"${aside_items[@]}"}
        return
    fi

    mkdir -p -- "$root"
    discard_old_stages "$root"
    stage="$(mktemp -d "$root/.supremeteam-stage.XXXXXX")"
    stage_root="$root"
    stage_committed=0
    printf 'supremeteam-stage 1\n' > "$stage/$stage_marker_name"
    mkdir -- "$stage/new" "$stage/old"

    # Everything that can fail for lack of space or permission happens here,
    # before the first change to an item that is already in place.
    for item in ${add_items[@]+"${add_items[@]}"} ${replace_items[@]+"${replace_items[@]}"} ${foreign_items[@]+"${foreign_items[@]}"}; do
        stage_item "$item"
    done

    backup_dir=""
    if [[ $((${#foreign_items[@]} + ${#aside_items[@]})) -gt 0 ]]; then
        make_backup_dir "$root"
    fi

    for item in ${add_items[@]+"${add_items[@]}"}; do
        swap_in "$root" "$item" absent
    done
    for item in ${replace_items[@]+"${replace_items[@]}"}; do
        swap_in "$root" "$item" owned
    done
    for item in ${foreign_items[@]+"${foreign_items[@]}"}; do
        swap_in "$root" "$item" foreign
    done
    for item in ${stale_items[@]+"${stale_items[@]}"}; do
        mv -- "$root/$item" "$stage/old/$item"
    done
    for item in ${aside_items[@]+"${aside_items[@]}"}; do
        mv -- "$root/$item" "$backup_dir/$item"
    done

    write_manifest "$root"
    stage_committed=1
    assert_installed_layout "$root"
    discard_stage

    printf '  installed %d items (%d new, %d replaced)\n' \
        "$((${#add_items[@]} + ${#replace_items[@]} + ${#foreign_items[@]}))" \
        "$((${#add_items[@]} + ${#foreign_items[@]}))" \
        "${#replace_items[@]}"
    printf '  recorded in %s\n' "$root/$manifest_name"
    report_list "kept, yours" ${kept_items[@]+"${kept_items[@]}"}
    report_list "removed, no longer shipped" ${stale_items[@]+"${stale_items[@]}"}
    if [[ -n "$backup_dir" ]]; then
        printf '  moved aside, not installed by Supreme Team and unchanged, to %s:\n' "$backup_dir"
        printf '    %s\n' ${foreign_items[@]+"${foreign_items[@]}"} ${aside_items[@]+"${aside_items[@]}"}
        backup_dirs+=("$backup_dir")
    fi
}

format_team_list() {
    join_words ', ' ${selected_teams[@]+"${selected_teams[@]}"}
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

    if ! contains_value "$target" ${selected_targets[@]+"${selected_targets[@]}"}; then
        selected_targets+=("$target")
    fi
}

has_target() {
    contains_value "$1" ${selected_targets[@]+"${selected_targets[@]}"}
}

resolve_targets() {
    local target normalized

    selected_targets=()

    if [[ ${#requested_targets[@]} -eq 0 ]]; then
        requested_targets=(auto)
    fi

    for target in ${requested_targets[@]+"${requested_targets[@]}"}; do
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
                if [[ "$normalized" == cursor ]]; then
                    cursor_target_explicit=1
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

minimum_python_version() {
    # skills/runtime-manifest.yaml is the runtime contract and is plain JSON.
    # Reading it here keeps the installer from refusing an interpreter the
    # project declares supported. The fallback covers an unreadable manifest.
    local manifest="$source_root/runtime-manifest.yaml" value
    if [[ -f "$manifest" ]]; then
        value="$(sed -n 's/.*"minimum"[[:space:]]*:[[:space:]]*"\([0-9][0-9]*\.[0-9][0-9]*\)".*/\1/p' "$manifest" | head -n 1)"
        if [[ -n "$value" ]]; then
            printf '%s' "$value"
            return 0
        fi
    fi
    printf '3.13'
}

python_satisfies_minimum() {
    local candidate="$1" minimum major minor
    minimum="$(minimum_python_version)"
    major="${minimum%%.*}"
    minor="${minimum##*.}"
    "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= ($major, $minor) else 1)" >/dev/null 2>&1
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
        printf 'Warning: no Python %s+ interpreter was found. Skill files will still be copied, but hook verification and registration require Python %s or newer.\n' "$(minimum_python_version)" "$(minimum_python_version)" >&2
    fi
}

find_python() {
    local python
    if python="$(find_compatible_python)"; then
        printf '%s' "$python"
        return 0
    fi

    die "Python $(minimum_python_version) or newer is required to register runtime harness hooks."
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

# An interrupted run still clears its staging directory; the exit codes are the
# conventional 128 plus the signal number.
trap discard_stage EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

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
        --dry-run)
            dry_run=1
            shift
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

# An empty HOME would turn every default location into a path at the filesystem root.
[[ -n "${HOME:-}" ]] || die "HOME is not set, so the default install locations are undefined. Set it and run the installer again."

load_items
assert_source_layout
resolve_teams
build_install_items
resolve_targets
warn_python_readiness

install_roots=("$destination")
install_labels=(common)
mirror_status=()

if has_target codex && { [[ $codex_target_explicit -eq 1 ]] || supreme_team_install_present "$codex_destination"; }; then
    install_roots+=("$codex_destination")
    install_labels+=(codex)
fi

if has_target claude; then
    install_roots+=("$claude_destination")
    install_labels+=(claude)
fi

if has_target cursor && { [[ $cursor_target_explicit -eq 1 ]] || supreme_team_install_present "$cursor_destination"; }; then
    install_roots+=("$cursor_destination")
    install_labels+=(cursor)
fi

if has_target opencode; then
    install_roots+=("$opencode_destination")
    install_labels+=(opencode)
fi

for ((i = 0; i < ${#install_roots[@]}; i++)); do
    assert_safe_root "${install_labels[$i]}" "${install_roots[$i]}"
done

if [[ $dry_run -eq 1 ]]; then
    printf 'Dry run: nothing will be written.\n'
fi

for ((i = 0; i < ${#install_roots[@]}; i++)); do
    if [[ "${install_labels[$i]}" == common ]]; then
        printf 'Installing Supreme Team to %s\n' "${install_roots[$i]}"
    else
        printf 'Mirroring Supreme Team to %s\n' "${install_roots[$i]}"
        mirror_status+=("${install_labels[$i]}=${install_roots[$i]}")
    fi
    install_supreme_team "${install_roots[$i]}"
done

if [[ $dry_run -eq 1 ]]; then
    printf '\nDry run complete: nothing was written.\n'
    exit 0
fi

if [[ $register_hooks -eq 1 ]]; then
    register_harness_hooks
fi

printf '\nSupreme Team installation complete.\n'
printf 'Target: %s\n' "$destination"
if [[ ${#selected_targets[@]} -gt 0 ]]; then
    printf 'Host targets: %s\n' "$(join_words ' ' ${selected_targets[@]+"${selected_targets[@]}"})"
else
    printf 'Host targets: none detected\n'
fi
if [[ ${#mirror_status[@]} -gt 0 ]]; then
    printf 'Host mirrors: %s\n' "$(join_words ' ' ${mirror_status[@]+"${mirror_status[@]}"})"
else
    printf 'Host mirrors: none\n'
fi
printf 'Teams: %s\n' "$(format_team_list)"
printf 'Installed items: %d in %d location(s)\n' "${#install_items[@]}" "${#install_roots[@]}"
if [[ ${#backup_dirs[@]} -gt 0 ]]; then
    printf 'Moved aside, kept unchanged: %s\n' "$(join_words ' ' ${backup_dirs[@]+"${backup_dirs[@]}"})"
else
    printf 'Moved aside: nothing\n'
fi
if [[ $register_hooks -ne 1 ]]; then
    printf 'Hook registration: not requested\n'
elif [[ ${#selected_targets[@]} -eq 0 ]]; then
    printf 'Hook registration: skipped (no host detected)\n'
else
    printf 'Hook registration: completed\n'
fi
printf 'Restart your assistant session if it was already running.\n'
if [[ $register_hooks -ne 1 ]]; then
    printf 'To register runtime harness hooks for the selected hosts, run this installer again from a checkout with --register-hooks, or preview the registration with: python "%s/harness/hooks/repair_registration.py" --host <host> --scope project\n' "$destination"
fi
