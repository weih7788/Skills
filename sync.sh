#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  sync.sh --ai <name> (--project <project_dir> | --global | --target <skills_dir>) [options]

Description:
  AI-aware skill sync by symlink. It links first-level directories from source to
  one or more resolved target skill directories, hiding vendor-specific paths.

Options:
  -a, --ai <name>       AI tool: codex | claude | cursor | antigravity
      --project <dir>   Project root. The script resolves the skills directory from --ai.
  -g, --global          Use the global skills directory for the selected AI.
  -t, --target <dir>    Use an explicit skills directory and skip AI path resolution.
  -s, --source <dir>    Source skills directory (default: current directory)
      --only <path>     Sync only this first-level subdirectory (repeatable).
                        Supports name or relative path under --source, e.g.
                        project-knowledge-wiki or ./project-knowledge-wiki
                        If --source is omitted, paths are resolved from current
                        working directory where the command is executed.
  -f, --force           Replace existing files/directories/symlinks at target
  -p, --prune           Remove stale links in target not present in source
  -n, --dry-run         Print actions without making changes
  -h, --help            Show this help

Resolved target directories:
  codex
    project -> <project>/.agents/skills
    global  -> ~/.agents/skills

  claude
    project -> <project>/.claude/skills
    global  -> ~/.claude/skills

  cursor
    project -> <project>/.cursor/skills and <project>/.agents/skills
    global  -> ~/.cursor/skills

  antigravity
    project -> <project>/.agents/skills
               If legacy <project>/.agent/skills exists and .agents/skills does not,
               sync to the legacy path instead.
    global  -> ~/.gemini/antigravity/skills

Examples:
  ./sync.sh --ai codex --project /path/to/repo
  ./sync.sh --ai claude --global
  ./sync.sh --ai cursor --project /path/to/repo -f
  ./sync.sh --ai antigravity --target /custom/skills/dir -p -n
  ./sync.sh --ai codex --global --only ./project-knowledge-wiki
  ./sync.sh --ai codex --global --source /Users/xx/work/skills --only project-knowledge-wiki
USAGE
}

AI=""
SOURCE_DIR="$(pwd)"
PROJECT_DIR=""
TARGET_DIR=""
USE_GLOBAL=0
FORCE=0
PRUNE=0
DRY_RUN=0

declare -a ONLY_RAW_ENTRIES=()
declare -a ONLY_NAMES=()

declare -a RESOLVED_TARGETS=()
declare -a TARGET_NOTICES=()

fail() {
  echo "Error: $*" >&2
  exit 1
}

expand_path() {
  local path="$1"
  if [[ "$path" == "~" ]]; then
    printf '%s\n' "$HOME"
  elif [[ "$path" == "~/"* ]]; then
    printf '%s/%s\n' "$HOME" "${path:2}"
  else
    printf '%s\n' "$path"
  fi
}

abs_existing_dir() {
  local dir
  dir="$(expand_path "$1")"
  [[ -d "$dir" ]] || fail "directory not found: $1"
  (
    cd "$dir"
    pwd -P
  )
}

abs_dir_allow_missing() {
  local input
  input="$(expand_path "$1")"
  if [[ "$input" != /* ]]; then
    input="$(pwd)/$input"
  fi
  printf '%s\n' "$input"
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
  else
    "$@"
  fi
}

ensure_target_dir() {
  local dir="$1"
  local abs_dir
  local expanded_dir
  if [[ "$DRY_RUN" -eq 1 ]]; then
    abs_dir="$(abs_dir_allow_missing "$dir")"
    printf '[dry-run] mkdir -p %q\n' "$abs_dir" >&2
    printf '%s\n' "$abs_dir"
  else
    expanded_dir="$(expand_path "$dir")"
    mkdir -p "$expanded_dir"
    abs_existing_dir "$expanded_dir"
  fi
}

is_same_or_nested() {
  local left="$1"
  local right="$2"
  [[ "$left" == "$right" || "$left" == "$right"/* ]]
}

assert_target_safe() {
  local target="$1"
  if is_same_or_nested "$target" "$SOURCE_DIR" || is_same_or_nested "$SOURCE_DIR" "$target"; then
    fail "source and target must not contain each other: source=$SOURCE_DIR target=$target"
  fi
}

normalize_only_entry_to_name() {
  local entry="$1"
  local candidate resolved rel

  [[ -n "$entry" ]] || fail "--only requires a non-empty value"

  candidate="$(expand_path "$entry")"
  if [[ "$candidate" != /* ]]; then
    candidate="$SOURCE_DIR/$candidate"
  fi
  [[ -d "$candidate" ]] || fail "--only: directory not found: $entry"

  resolved="$(
    cd "$candidate"
    pwd -P
  )"

  [[ "$resolved" == "$SOURCE_DIR"/* ]] || fail "--only must point under source: $entry (source=$SOURCE_DIR)"
  rel="${resolved#"$SOURCE_DIR"/}"
  [[ -n "$rel" ]] || fail "--only must not point to source root: $entry"
  [[ "$rel" != *"/"* ]] || fail "--only must resolve to a first-level child under source: $entry"
  printf '%s\n' "$rel"
}

normalize_and_validate_only_entries() {
  local raw n normalized
  if [[ "${#ONLY_RAW_ENTRIES[@]}" -eq 0 ]]; then
    return 0
  fi

  for raw in "${ONLY_RAW_ENTRIES[@]}"; do
    normalized="$(normalize_only_entry_to_name "$raw")"
    ONLY_NAMES+=("$normalized")
  done

  for n in "${ONLY_NAMES[@]}"; do
    [[ -d "$SOURCE_DIR/$n" ]] || fail "--only: not a directory under source: $n (source=$SOURCE_DIR)"
    [[ -f "$SOURCE_DIR/$n/SKILL.md" ]] || fail "--only: missing SKILL.md: $SOURCE_DIR/$n/SKILL.md"
  done
}

name_is_only_selected() {
  local name="$1"
  local n
  if [[ "${#ONLY_NAMES[@]}" -eq 0 ]]; then
    return 0
  fi
  for n in "${ONLY_NAMES[@]}"; do
    if [[ "$n" == "$name" ]]; then
      return 0
    fi
  done
  return 1
}

add_resolved_target() {
  local target="$1"
  RESOLVED_TARGETS+=("$target")
}

resolve_targets() {
  local project_root legacy_path modern_path

  if [[ -n "$TARGET_DIR" ]]; then
    add_resolved_target "$TARGET_DIR"
    return
  fi

  if [[ "$USE_GLOBAL" -eq 1 ]]; then
    case "$AI" in
      codex)
        add_resolved_target "~/.agents/skills"
        ;;
      claude)
        add_resolved_target "~/.claude/skills"
        ;;
      cursor)
        add_resolved_target "~/.cursor/skills"
        ;;
      antigravity)
        add_resolved_target "~/.gemini/antigravity/skills"
        ;;
      *)
        fail "unsupported ai: $AI"
        ;;
    esac
    return
  fi

  project_root="$PROJECT_DIR"
  case "$AI" in
    codex)
      add_resolved_target "$project_root/.agents/skills"
      ;;
    claude)
      add_resolved_target "$project_root/.claude/skills"
      ;;
    cursor)
      add_resolved_target "$project_root/.cursor/skills"
      add_resolved_target "$project_root/.agents/skills"
      ;;
    antigravity)
      legacy_path="$project_root/.agent/skills"
      modern_path="$project_root/.agents/skills"
      if [[ -d "$legacy_path" && ! -e "$modern_path" ]]; then
        add_resolved_target "$legacy_path"
        TARGET_NOTICES+=("notice: detected Antigravity legacy path $legacy_path; syncing there")
      else
        add_resolved_target "$modern_path"
        if [[ -d "$legacy_path" ]]; then
          TARGET_NOTICES+=("notice: legacy Antigravity path also exists at $legacy_path but is not synced")
        fi
      fi
      ;;
    *)
      fail "unsupported ai: $AI"
      ;;
  esac
}

sync_one_target() {
  local target_dir="$1"
  local linked=0
  local skipped=0
  local removed=0
  local path name src dst current_target should_prune expected_src pruned_in_pass pruned_path
  local -a pruned_paths=()

  echo "target: $target_dir"

  if [[ "$PRUNE" -eq 1 ]]; then
    for path in "$target_dir"/* "$target_dir"/.[!.]* "$target_dir"/..?*; do
      [[ -e "$path" || -L "$path" ]] || continue
      [[ -L "$path" ]] || continue

      name="$(basename "$path")"
      should_prune=0

      case "$name" in
        .git|.DS_Store)
          continue
          ;;
        .system)
          should_prune=1
          ;;
        *)
          if [[ "${#ONLY_NAMES[@]}" -gt 0 ]] && ! name_is_only_selected "$name"; then
            continue
          fi
          expected_src="$SOURCE_DIR/$name"
          if [[ ! -f "$expected_src/SKILL.md" ]]; then
            should_prune=1
          elif [[ ! "$path" -ef "$expected_src" ]]; then
            should_prune=1
          fi
          ;;
      esac

      if [[ "$should_prune" -eq 1 ]]; then
        run_cmd rm -f "$path"
        pruned_paths+=("$path")
        echo "prune: removed stale link $path"
        removed=$((removed + 1))
      fi
    done
  fi

  for path in "$SOURCE_DIR"/* "$SOURCE_DIR"/.[!.]* "$SOURCE_DIR"/..?*; do
    [[ -e "$path" ]] || continue
    [[ -d "$path" ]] || continue

    name="$(basename "$path")"
    case "$name" in
      .git|.DS_Store|.system)
        continue
        ;;
    esac
    [[ -f "$path/SKILL.md" ]] || continue
    name_is_only_selected "$name" || continue

    src="$SOURCE_DIR/$name"
    dst="$target_dir/$name"

    pruned_in_pass=0
    if [[ "${#pruned_paths[@]}" -gt 0 ]]; then
      for pruned_path in "${pruned_paths[@]}"; do
        if [[ "$pruned_path" == "$dst" ]]; then
          pruned_in_pass=1
          break
        fi
      done
    fi

    if [[ "$pruned_in_pass" -eq 0 && -L "$dst" ]]; then
      if [[ "$dst" -ef "$src" ]]; then
        echo "skip: $name already linked"
        skipped=$((skipped + 1))
        continue
      fi

      current_target="$(readlink "$dst" || true)"
      if [[ "$FORCE" -eq 1 ]]; then
        run_cmd rm -f "$dst"
        run_cmd ln -s "$src" "$dst"
        echo "relink: $dst -> $src"
        linked=$((linked + 1))
      else
        echo "skip: $dst is symlink to $current_target (use --force to replace)"
        skipped=$((skipped + 1))
      fi
      continue
    fi

    if [[ "$pruned_in_pass" -eq 0 && -e "$dst" ]]; then
      if [[ "$FORCE" -eq 1 ]]; then
        run_cmd rm -rf "$dst"
        run_cmd ln -s "$src" "$dst"
        echo "replace: $dst -> $src"
        linked=$((linked + 1))
      else
        echo "skip: $dst exists (use --force to replace)"
        skipped=$((skipped + 1))
      fi
      continue
    fi

    run_cmd ln -s "$src" "$dst"
    echo "link: $dst -> $src"
    linked=$((linked + 1))
  done

  echo "done: target=$target_dir linked=$linked skipped=$skipped pruned=$removed"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -a|--ai)
      AI="${2:-}"
      shift 2
      ;;
    --project)
      PROJECT_DIR="${2:-}"
      shift 2
      ;;
    -g|--global)
      USE_GLOBAL=1
      shift
      ;;
    -t|--target)
      TARGET_DIR="${2:-}"
      shift 2
      ;;
    -s|--source)
      SOURCE_DIR="${2:-}"
      shift 2
      ;;
    --only)
      ONLY_RAW_ENTRIES+=("${2:-}")
      shift 2
      ;;
    -f|--force)
      FORCE=1
      shift
      ;;
    -p|--prune)
      PRUNE=1
      shift
      ;;
    -n|--dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$AI" ]] || fail "--ai is required"
case "$AI" in
  codex|claude|cursor|antigravity)
    ;;
  *)
    fail "unsupported --ai value: $AI"
    ;;
esac

mode_count=0
[[ -n "$PROJECT_DIR" ]] && mode_count=$((mode_count + 1))
[[ "$USE_GLOBAL" -eq 1 ]] && mode_count=$((mode_count + 1))
[[ -n "$TARGET_DIR" ]] && mode_count=$((mode_count + 1))
[[ "$mode_count" -eq 1 ]] || fail "exactly one of --project, --global, or --target is required"

SOURCE_DIR="$(abs_existing_dir "$SOURCE_DIR")"
[[ -n "$PROJECT_DIR" ]] && PROJECT_DIR="$(abs_existing_dir "$PROJECT_DIR")"

normalize_and_validate_only_entries

resolve_targets

declare -a NORMALIZED_TARGETS=()
for target in "${RESOLVED_TARGETS[@]}"; do
  normalized_target="$(ensure_target_dir "$target")"
  assert_target_safe "$normalized_target"
  NORMALIZED_TARGETS+=("$normalized_target")
done

if [[ "${#TARGET_NOTICES[@]}" -gt 0 ]]; then
  for notice in "${TARGET_NOTICES[@]}"; do
    echo "$notice"
  done
fi

echo "source: $SOURCE_DIR"
if [[ "${#ONLY_NAMES[@]}" -gt 0 ]]; then
  echo "only: ${ONLY_NAMES[*]}"
fi
echo "ai: $AI"
for target in "${NORMALIZED_TARGETS[@]}"; do
  sync_one_target "$target"
done
