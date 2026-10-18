"""AF Server 입력 JSON 생성 (후보 1개마다 '타겟 구성 단백질 전체 + 후보 1개' 잡)."""
import copy
import json
import re
from dataclasses import dataclass

from protinteract.core.uniprot import ProteinInfo, sequence_error, validate_info

TOKEN_LIMIT = 5000  # AF Server 잡 하나의 입력 한도 (설정으로 바꿀 수 있게 인자로 받는다)
DIALECT = "alphafoldserver"
VERSION = 1
USABLE = ("ok", "merged")


@dataclass
class TargetChain:
    info: ProteinInfo
    count: int = 1


@dataclass
class JobPlan:
    candidate: ProteinInfo
    name: str
    tokens: int
    included: bool
    note: str = ""


def safe_name(text: str) -> str:
    """잡 이름에 쓸 수 있도록 영문, 숫자, 밑줄, 하이픈만 남긴다."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")[:100]


def parse_target_lines(text: str) -> tuple[list[tuple[str, int]], list[str]]:
    """한 줄에 'UniProt ID 복제수'를 적은 텍스트를 (ID, 복제수) 목록으로 바꾼다.

    복제수를 생략하면 1이다. 같은 ID가 여러 줄이면 복제수를 합친다.
    """
    entries: dict[str, int] = {}
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        parts = [p for p in re.split(r"[\s,;]+", line.strip()) if p]
        if not parts:
            continue
        if len(parts) > 2:
            errors.append(f"{number}번째 줄 '{line.strip()}': 'UniProt ID 복제수' 형식으로 입력해 주세요")
            continue
        count = 1
        if len(parts) == 2:
            if not re.fullmatch(r"[0-9]{1,6}", parts[1]) or int(parts[1]) < 1:
                errors.append(f"{number}번째 줄 '{line.strip()}': 복제수는 1 이상의 정수여야 합니다")
                continue
            count = int(parts[1])
        key = parts[0].upper()
        entries[key] = entries.get(key, 0) + count
    return list(entries.items()), errors


def merge_targets(target: list[TargetChain]) -> tuple[list[TargetChain], list[str]]:
    """동일하게 조회된 accession만 합산한다. isoform ID는 유지한다."""
    merged: dict[str, TargetChain] = {}
    warnings = []
    for chain in target:
        accession = chain.info.accession
        if accession in merged:
            previous = merged[accession]
            if previous.info.sequence != chain.info.sequence:
                raise ValueError(f"{accession}: 같은 ID의 서열이 다릅니다. 다시 조회해 주세요")
            warnings.append(f"{chain.info.query} → {accession}: 타겟 복제수 {chain.count}개 합산")
            previous.count += chain.count
        else:
            merged[accession] = TargetChain(chain.info, chain.count)
    return list(merged.values()), warnings


def default_target_label(target: list[TargetChain]) -> str:
    """타겟 이름은 UniProt ID. 복합체이면 구성 단백질의 ID를 하이픈으로 잇는다."""
    return safe_name("-".join(chain.info.accession for chain in target))


def target_tokens(target: list[TargetChain]) -> int:
    return sum(chain.info.length * chain.count for chain in target)


def plan_jobs(
    target: list[TargetChain],
    candidates: list[ProteinInfo],
    label: str,
    token_limit: int = TOKEN_LIMIT,
) -> list[JobPlan]:
    """후보마다 잡 하나를 계획하고, 만들 수 없는 후보는 사유와 함께 제외로 표시한다."""
    base_tokens = target_tokens(target)
    target_ids = {chain.info.accession for chain in target}
    seen: set[str] = set()
    plans: list[JobPlan] = []
    names: set[str] = set()
    for cand in candidates:
        name = safe_name(f"{label[:70]}_vs_{cand.accession or cand.query}")
        if name in names:
            name = f"{name[:90]}_{len(plans) + 1}"
        names.add(name)
        if cand.status not in USABLE:
            plans.append(JobPlan(cand, name, 0, False, f"{cand.status_label}: {cand.message}"))
            continue
        problem = validate_info(cand)
        if problem:
            plans.append(JobPlan(cand, name, 0, False, problem))
            continue
        tokens = base_tokens + cand.length
        if cand.accession in seen:
            plans.append(JobPlan(cand, name, tokens, False, "중복: 같은 ID가 이미 목록에 있습니다"))
            continue
        seen.add(cand.accession)
        if tokens > token_limit:
            plans.append(JobPlan(cand, name, tokens, False, f"한도 초과: {tokens} > {token_limit}"))
            continue
        copies = sum(c.count for c in target if c.info.accession == cand.accession)
        note = f"타겟과 같은 ID: 기존 {copies}개 + 후보 1개 = 최종 {copies + 1}개" if cand.accession in target_ids else ""
        note = "; ".join(part for part in (cand.message, note) if part)
        plans.append(JobPlan(cand, name, tokens, True, note))
    return plans


def build_job(name: str, chains: list[tuple[str, int]]) -> dict:
    """AF Server 잡 하나. chains는 (서열, 복제수) 목록이다."""
    if not name or name != safe_name(name) or not chains:
        raise ValueError("잡 이름 또는 구성이 올바르지 않습니다")
    for seq, count in chains:
        problem = sequence_error(seq)
        if problem or type(count) is not int or count < 1:
            raise ValueError(problem or "복제수는 1 이상의 정수여야 합니다")
    if sum(len(seq) * count for seq, count in chains) > TOKEN_LIMIT:
        raise ValueError(f"Server 입력 한도 {TOKEN_LIMIT} 토큰을 초과합니다")
    return {
        "name": name,
        "modelSeeds": [],
        "sequences": [{"proteinChain": {"sequence": seq, "count": count}} for seq, count in chains],
        "dialect": DIALECT,
        "version": VERSION,
    }


def build_jobs(plans: list[JobPlan], target: list[TargetChain]) -> list[dict]:
    jobs = []
    for plan in plans:
        if not plan.included:
            continue
        chains = [(c.info.sequence, c.count + (c.info.accession == plan.candidate.accession)) for c in target]
        if not any(c.info.accession == plan.candidate.accession for c in target):
            chains.append((plan.candidate.sequence, 1))
        jobs.append(build_job(plan.name, chains))
    if len({job["name"] for job in jobs}) != len(jobs):
        raise ValueError("잡 이름이 중복됩니다")
    return jobs


def to_json_text(jobs: list[dict]) -> str:
    return json.dumps(jobs, indent=2, ensure_ascii=False)


def shorten_for_preview(job: dict, keep: int = 24) -> dict:
    """화면 미리보기용으로 서열을 줄여 보여준다."""
    preview = copy.deepcopy(job)
    for entry in preview["sequences"]:
        chain = entry["proteinChain"]
        if len(chain["sequence"]) > keep:
            chain["sequence"] = chain["sequence"][:keep] + f"... ({len(chain['sequence'])} aa)"
    return preview
