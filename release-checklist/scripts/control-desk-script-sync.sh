#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  control-desk-script-sync.sh [--base <base-branch>] [--repo <repo-root>]

Description:
  Analyze control-desk script changes between <base-branch>..HEAD and emit a
  Markdown report for the "脚本配置修改" section in a release checklist.

Options:
  --base    Base branch used for git diff. Default: preview
  --repo    Repository root. Default: current working directory
  -h, --help
EOF
}

map_test_to_prod_id() {
  case "$1" in
    103046) echo "106578" ;;
    103007) echo "273" ;;
    103049) echo "166" ;;
    103078) echo "10001" ;;
    *) echo "" ;;
  esac
}

map_prod_to_test_id() {
  case "$1" in
    106578) echo "103046" ;;
    273) echo "103007" ;;
    166) echo "103049" ;;
    10001) echo "103078" ;;
    *) echo "" ;;
  esac
}

tenant_scope_by_id() {
  case "$1" in
    103046|106578) echo "上港长江" ;;
    99969) echo "上港长江生产测试" ;;
    103007|273|2) echo "天津外代" ;;
    103049|166) echo "君隆" ;;
    103078|10001) echo "RELEASE_SPACE_FILLED" ;;
    *) echo "[待确认]" ;;
  esac
}

status_to_cn() {
  case "${1:0:1}" in
    A) echo "新建" ;;
    M) echo "修改" ;;
    D) echo "删除" ;;
    R) echo "重命名" ;;
    C) echo "复制" ;;
    *) echo "$1" ;;
  esac
}

script_feature_name() {
  local filename="${1##*/}"
  local base="${filename%.groovy}"
  case "$base" in
    ENTRUSTED_WORK_ORDER_REVIEW_BEFORE_HOOK_*) echo "工单审核前 Hook" ;;
    ENTRUSTED_WORK_ORDER_ORDER_CREATED_HOOK_*) echo "工单创建后 Hook" ;;
    ENTRUSTED_*_TENANT_POST_CLEAN_*) echo "租户后处理" ;;
    GENERATE_BOOKING_REMARK_*) echo "订舱备注生成" ;;
    SYSTEM_MAIL_SEND_HOOK_*) echo "邮件发送 Hook" ;;
    RELEASE_SPACE_FILLED_*) echo "放舱回填" ;;
    ENTRUSTED_STANDARD_V2_GET_ENTRUSTED_INFO) echo "委托信息获取" ;;
    ENTRUSTED_STANDARD_V2_CLEAN_CONTENT_FIELDS) echo "内容字段清洗" ;;
    ENTRUSTED_STANDARD_V2_CONVERT_BOOKING_PARAM) echo "订舱参数转换" ;;
    ENTRUSTED_STANDARD_V2_CONVERT_TO_SIMILAR_ORDER) echo "相似订单转换" ;;
    BOOKING_REPORT_EMAIL_BODY_CONVERT) echo "订舱报告邮件正文转换" ;;
    EXPORT_ENTRUST_TO_EXCEL) echo "导出委托到 Excel" ;;
    IMPORT_SIMILAR_ORDER_FROM_EXCEL) echo "从 Excel 导入相似订单" ;;
    *) echo "$base" ;;
  esac
}

path_label() {
  if [[ "$1" == "NONE" ]]; then
    echo "[无对应测试脚本]"
  elif [[ "$1" == "UNKNOWN" ]]; then
    echo "[待确认]"
  else
    echo "\`$1\`"
  fi
}

cmp_equal() {
  local left="$1"
  local right="$2"
  [[ -f "$left" && -f "$right" ]] || return 1
  cmp -s "$left" "$right"
}

array_contains() {
  local target="$1"
  shift
  local item=""
  for item in "$@"; do
    [[ "$item" == "$target" ]] && return 0
  done
  return 1
}

status_for_path() {
  local target="$1"
  local i=0
  while [[ $i -lt ${#changed_paths[@]} ]]; do
    if [[ "${changed_paths[$i]}" == "$target" ]]; then
      printf '%s' "${changed_statuses[$i]}"
      return 0
    fi
    i=$((i + 1))
  done
  return 1
}

map_test_path_to_prod() {
  local rel_path="$1"
  local filename="${rel_path##*/}"
  local test_id=""
  local prod_id=""

  if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
    test_id="${BASH_REMATCH[1]}"
    prod_id="$(map_test_to_prod_id "$test_id")"
    if [[ -z "$prod_id" ]]; then
      echo ""
      return
    fi
    echo "$prod_dir_rel/${filename%_${test_id}.groovy}_${prod_id}.groovy"
    return
  fi

  echo "$prod_dir_rel/$filename"
}

scope_for_path_pair() {
  local test_path="$1"
  local prod_path="$2"
  local filename=""
  local tenant_id=""

  if [[ "$test_path" != "NONE" && "$test_path" != "UNKNOWN" ]]; then
    filename="${test_path##*/}"
    if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
      tenant_id="${BASH_REMATCH[1]}"
      tenant_scope_by_id "$tenant_id"
      return
    fi
    echo "全局"
    return
  fi

  if [[ "$prod_path" != "UNKNOWN" ]]; then
    filename="${prod_path##*/}"
    if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
      tenant_id="${BASH_REMATCH[1]}"
      tenant_scope_by_id "$tenant_id"
      return
    fi
  fi

  echo "全局"
}

build_basis_for_test_row() {
  local test_path="$1"
  local test_status_cn="$2"
  local prod_status_cn="$3"
  local sync_status="$4"
  local filename="${test_path##*/}"
  local test_id=""
  local prod_id=""

  if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
    test_id="${BASH_REMATCH[1]}"
    prod_id="$(map_test_to_prod_id "$test_id")"
    if [[ -z "$prod_status_cn" ]]; then
      echo "基于租户映射 ${test_id} -> ${prod_id} 建立对应关系；git diff 仅检测到测试脚本 ${test_status_cn}，生产脚本未出现在本次变更列表。"
    else
      echo "基于租户映射 ${test_id} -> ${prod_id} 建立对应关系；git diff 检测到测试脚本 ${test_status_cn}、生产脚本 ${prod_status_cn}；当前同步状态为 ${sync_status}。"
    fi
    return
  fi

  if [[ -z "$prod_status_cn" ]]; then
    echo "按通用脚本同名映射建立对应关系；git diff 仅检测到测试脚本 ${test_status_cn}，生产脚本未出现在本次变更列表。"
  else
    echo "按通用脚本同名映射建立对应关系；git diff 检测到测试脚本 ${test_status_cn}、生产脚本 ${prod_status_cn}；当前同步状态为 ${sync_status}。"
  fi
}

build_basis_for_prod_only_row() {
  local test_path="$1"
  local prod_path="$2"
  local prod_status_cn="$3"
  local filename="${prod_path##*/}"
  local prod_id=""

  if [[ "$test_path" == "NONE" ]]; then
    if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
      prod_id="${BASH_REMATCH[1]}"
      echo "git diff 仅检测到生产脚本 ${prod_status_cn}；当前租户 ID ${prod_id} 未纳入正式测试->生产同步映射，按生产独有变更处理。"
      return
    fi
    echo "git diff 仅检测到生产脚本 ${prod_status_cn}；未找到稳定的测试侧来源脚本，按生产独有变更处理。"
    return
  fi

  echo "按现有映射可定位到测试脚本 ${test_path}，但 git diff 仅检测到生产脚本 ${prod_status_cn}；需人工确认是否绕过测试环境直接修改。"
}

base_branch="preview"
repo_root=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      [[ $# -ge 2 ]] || { echo "Missing value for --base" >&2; exit 1; }
      base_branch="$2"
      shift 2
      ;;
    --repo)
      [[ $# -ge 2 ]] || { echo "Missing value for --repo" >&2; exit 1; }
      repo_root="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$repo_root" ]]; then
  repo_root="$(pwd)"
fi
repo_root="$(cd "$repo_root" && pwd)"

test_dir_rel="cube-control-desk-biz/src/main/resources/scripts"
prod_dir_rel="cube-control-desk-biz/src/main/resources/scripts-prod"
test_dir_abs="$repo_root/$test_dir_rel"
prod_dir_abs="$repo_root/$prod_dir_rel"

if [[ ! -d "$test_dir_abs" || ! -d "$prod_dir_abs" ]]; then
  echo "Expected control-desk script directories were not found under: $repo_root" >&2
  exit 1
fi

git_output="$(git -C "$repo_root" diff --name-status "${base_branch}..HEAD" -- "$test_dir_rel" "$prod_dir_rel")"

declare -a changed_paths=()
declare -a changed_statuses=()
declare -a test_changed_paths=()
declare -a prod_changed_paths=()

while IFS=$'\t' read -r status first second; do
  [[ -n "${status:-}" ]] || continue
  path="$first"
  if [[ "$status" == R* || "$status" == C* ]]; then
    path="$second"
  fi
  changed_paths+=("$path")
  changed_statuses+=("$status")
  if [[ "$path" == "$test_dir_rel/"* ]]; then
    test_changed_paths+=("$path")
  elif [[ "$path" == "$prod_dir_rel/"* ]]; then
    prod_changed_paths+=("$path")
  fi
done <<< "$git_output"

declare -a covered_prod_paths=()
declare -a table_rows=()
declare -a detail_rows=()
row_no=0

for test_path in "${test_changed_paths[@]}"; do
  test_status_raw="$(status_for_path "$test_path")"
  test_status_cn="$(status_to_cn "$test_status_raw")"
  prod_path="$(map_test_path_to_prod "$test_path")"
  feature_name="$(script_feature_name "$test_path")"

  if [[ -z "$prod_path" ]]; then
    row_no=$((row_no + 1))
    scope="$(scope_for_path_pair "$test_path" "UNKNOWN")"
    summary="${feature_name} 脚本${test_status_cn}，无法根据当前租户映射推导生产脚本"
    table_rows+=("| ${row_no} | $(path_label "$test_path") | $(path_label "UNKNOWN") | ${scope} | [待确认] | ${summary} |")
    detail_rows+=("- **$(path_label "$test_path") -> $(path_label "UNKNOWN")**：
  - 操作类型：${test_status_cn}
  - 差异摘要：${summary}
  - 判断依据：脚本文件名包含未收录的测试租户 ID，当前映射关系无法自动推导生产脚本。")
    continue
  fi

  covered_prod_paths+=("$prod_path")
  prod_status_raw=""
  if prod_status_raw="$(status_for_path "$prod_path" 2>/dev/null)"; then
    :
  else
    prod_status_raw=""
  fi
  prod_status_cn=""
  if [[ -n "$prod_status_raw" ]]; then
    prod_status_cn="$(status_to_cn "$prod_status_raw")"
  fi

  test_abs="$repo_root/$test_path"
  prod_abs="$repo_root/$prod_path"
  scope="$(scope_for_path_pair "$test_path" "$prod_path")"
  sync_status=""
  summary=""

  if [[ "${test_status_raw:0:1}" == "D" ]]; then
    if [[ -n "$prod_status_raw" && "${prod_status_raw:0:1}" == "D" ]]; then
      sync_status="已同步"
      summary="${feature_name} 脚本测试/生产均已删除"
    elif [[ -e "$prod_abs" ]]; then
      sync_status="待同步"
      summary="${feature_name} 脚本测试侧已删除，生产仍保留对应脚本"
    else
      sync_status="已同步"
      summary="${feature_name} 脚本测试侧已删除，生产侧当前也不存在对应脚本"
    fi
  elif [[ ! -e "$prod_abs" ]]; then
    sync_status="生产缺失"
    summary="${feature_name} 脚本测试侧${test_status_cn}，生产缺少对应脚本"
  elif [[ -n "$prod_status_raw" ]]; then
    if cmp_equal "$test_abs" "$prod_abs"; then
      sync_status="已同步"
      summary="${feature_name} 脚本测试/生产均${test_status_cn}，当前内容一致"
    else
      sync_status="待同步"
      summary="${feature_name} 脚本测试/生产均有变更，但当前内容不一致"
    fi
  else
    if cmp_equal "$test_abs" "$prod_abs"; then
      sync_status="已同步"
      summary="${feature_name} 脚本已与生产脚本保持一致"
    else
      sync_status="待同步"
      summary="${feature_name} 脚本测试侧${test_status_cn}，生产未同步本次变更"
    fi
  fi

  row_no=$((row_no + 1))
  table_rows+=("| ${row_no} | $(path_label "$test_path") | $(path_label "$prod_path") | ${scope} | ${sync_status} | ${summary} |")
  detail_rows+=("- **$(path_label "$test_path") -> $(path_label "$prod_path")**：
  - 操作类型：${test_status_cn}
  - 差异摘要：${summary}
  - 判断依据：$(build_basis_for_test_row "$test_path" "$test_status_cn" "$prod_status_cn" "$sync_status")")
done

for prod_path in "${prod_changed_paths[@]}"; do
  if array_contains "$prod_path" "${covered_prod_paths[@]}"; then
    continue
  fi

  prod_status_raw="$(status_for_path "$prod_path")"
  prod_status_cn="$(status_to_cn "$prod_status_raw")"
  filename="${prod_path##*/}"
  feature_name="$(script_feature_name "$prod_path")"
  test_path="NONE"

  if [[ "$filename" =~ _([0-9]+)\.groovy$ ]]; then
    prod_id="${BASH_REMATCH[1]}"
    test_id="$(map_prod_to_test_id "$prod_id")"
    if [[ -n "$test_id" ]]; then
      test_path="$test_dir_rel/${filename%_${prod_id}.groovy}_${test_id}.groovy"
    fi
  else
    candidate="$test_dir_rel/$filename"
    if [[ -f "$repo_root/$candidate" ]]; then
      test_path="$candidate"
    fi
  fi

  scope="$(scope_for_path_pair "$test_path" "$prod_path")"
  summary="${feature_name} 脚本仅生产侧${prod_status_cn}，需确认是否绕过测试环境直接修改"
  row_no=$((row_no + 1))
  table_rows+=("| ${row_no} | $(path_label "$test_path") | $(path_label "$prod_path") | ${scope} | 生产独有变更 | ${summary} |")
  detail_rows+=("- **$(path_label "$test_path") -> $(path_label "$prod_path")**：
  - 操作类型：${prod_status_cn}
  - 差异摘要：${summary}
  - 判断依据：$(build_basis_for_prod_only_row "$test_path" "$prod_path" "$prod_status_cn")")
done

echo "### 脚本配置修改"
echo

if [[ ${#table_rows[@]} -eq 0 ]]; then
  echo "| 序号 | 测试脚本 | 生产脚本 | 租户 / 范围 | 同步状态 | 变更摘要 |"
  echo "|------|----------|----------|-------------|----------|----------|"
  echo "| 1 | [无变更] | [无变更] | 全局 | 已同步 | ${base_branch}..HEAD 范围内未发现 scripts/ 或 scripts-prod/ 变更 |"
  echo
  echo "**详细同步说明**："
  echo "- 当前 diff 范围内未发现 control-desk 脚本变更。"
  exit 0
fi

echo "| 序号 | 测试脚本 | 生产脚本 | 租户 / 范围 | 同步状态 | 变更摘要 |"
echo "|------|----------|----------|-------------|----------|----------|"
printf '%s\n' "${table_rows[@]}"
echo
echo "**详细同步说明**："
printf '%s\n' "${detail_rows[@]}"
