"""Offline source-grounded fresh-family analysis and Vietnamese reports.

This module never generates feedback, runs student code, or infers semantic
verdicts. It joins the frozen inputs to completed reviews and existing evidence.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.task3.fresh_eval import (AXES, SYSTEMS, build_targets, validate_dataset,
    summarize_system, level_safety, screen_v3)
from src.task3.prompt_crossover_analysis import (VERDICTS, paired_analysis,
    semantic_value, successful_feedback)

PAIRS = (('A', 'V2-old'), ('A', 'V3-v3'), ('V2-old', 'V3-v3'))
EXAMPLE_POLICY = {
    'version': 'fresh-examples-before-inference-v1',
    'minimum_examples': 6,
    'order': 'sha256(family_id + / + sample_id + /L + Level), then example_id',
    'diversity': 'Prefer previously unused families, then unused sources; never exclude a required category.',
    'categories': [
        'one improvement and one regression per available directed pair, if present',
        'one explicit taxonomy-feedback contradiction and one invalid, if present',
        'two distinct faulty L3 repair directions if present (required_content pass and repair verdict pass/fail in any system), preferably from different families; otherwise expose missing content on remaining faulty L3 targets',
        'two clean and two faulty targets, then fill to at least six unique targets'],
    'comparison_direction': 'A to V2-old; A to V3-v3; V2-old to V3-v3',
    'improvement_regression': 'Both joint semantic values known and unequal; invalid/uncertain excluded from these two categories and shown separately.',
    'extrema': 'For native V2-old to V3-v3 known joint changes, rank by number of changed essential review axes, then fixed hash; include strongest improvement and largest regression if present.',
    'publication': 'Every selected example shows all available systems, full specification/source, raw/parsed output, gold/evidence and review reasons; all targets in searchable casebook.',
    'missing_categories': 'Explicitly report absence; never fabricate an example or select only favorable cases.',
}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)


def _index(rows, field, label):
    result = {}
    for row in rows:
        key = row.get(field)
        if not isinstance(key, str) or not key or key in result:
            raise ValueError('missing/duplicate '+label)
        result[key] = row
    return result


def _inside(out, name):
    path = Path(name)
    path = (out/path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(out) or not path.is_file():
        raise ValueError('missing or external evidence path: '+str(name))
    return path


def _available(systems):
    a = systems.get('A', {})
    unavailable = (a is None or (isinstance(a, dict) and
        (a.get('available') is False or a.get('status') == 'unavailable')))
    return tuple(s for s in SYSTEMS if s != 'A' or not unavailable)


def _generation_binding(gen, target, source):
    if (gen.get('example_id'), gen.get('sample_id'), gen.get('level')) != (
            target['sample_id'], source['sample_id'], target['input']['target_feedback_level']):
        raise ValueError('generation source/Level binding differs')
    if not isinstance(gen.get('raw'), str) or not isinstance(gen.get('status'), str):
        raise ValueError('missing raw output/status')
    if gen['status'] == 'valid':
        parsed = gen.get('parsed')
        if (not isinstance(parsed, dict) or set(parsed) != {'taxonomy_error', 'feedback'} or
                not isinstance(parsed['taxonomy_error'], list) or
                any(not isinstance(x, str) for x in parsed['taxonomy_error']) or
                not isinstance(parsed['feedback'], str)):
            raise ValueError('valid output lacks official parsed schema')
    elif gen.get('parsed') is not None:
        raise ValueError('invalid output cannot retain a valid parsed payload')


def validate_populations(out):
    """Validate complete input/gold/generation/review/evidence joins before writes."""
    out = Path(out).resolve()
    source_rows = jsonl(out/'dataset.private.jsonl')
    gold_rows = jsonl(out/'gold.private.jsonl')
    # Official label membership was checked by the frozen preparation step;
    # this check binds the exact stored labels and every private source hash.
    labels = {label for g in gold_rows for label in g['taxonomy']}
    validate_dataset(source_rows, gold_rows, labels)
    sources = _index(source_rows, 'sample_id', 'source')
    gold = _index(gold_rows, 'sample_id', 'gold')
    syntax = load(out/'syntax.private.json')
    if set(syntax) != set(sources):
        raise ValueError('syntax population differs')
    targets = _index(jsonl(out/'targets.private.jsonl'), 'sample_id', 'target')
    expected = {t['sample_id']:t for t in build_targets(source_rows, syntax)}
    if targets != expected:
        raise ValueError('target population/input whitelist binding differs')
    cases = _index(load(out/'evidence/cases.private.json'), 'sample_id', 'source case')
    validation = _index(load(out/'evidence/source-validation.private.json'), 'sample_id', 'source validation')
    if set(cases) != set(sources) or set(validation) != set(sources):
        raise ValueError('source evidence population differs')
    full_evidence, gold_witness = {}, {}
    for sid, source in sources.items():
        case, validated, g = cases[sid], validation[sid], gold[sid]
        if (case.get('family_id') != source['family_id'] or case.get('statement') != source['statement'] or
                case.get('source_sha256') != g['source_sha256'] or
                case.get('checker') != source['checker'] or case.get('exam_type') != source['exam_type'] or
                case.get('harness') != '' or case.get('split') != 'fresh'):
            raise ValueError('case/source evidence binding differs')
        if _inside(out, case['code_file']).read_text(encoding='utf-8') != source['code']:
            raise ValueError('case source file differs')
        if (validated.get('family_id') != source['family_id'] or
                validated.get('faulty') != g['faulty'] or validated.get('source_sha256') != g['source_sha256']):
            raise ValueError('validation/gold binding differs')
        witness = load(_inside(out, g['witness_evidence_path']))
        if (witness.get('sample_id') != sid or witness.get('source_sha256') != g['source_sha256']):
            raise ValueError('full witness evidence/source differs')
        full_evidence[sid] = witness
        matched = [test for test in witness.get('tests', []) if test.get('input') == g['witness_input']]
        if not matched:
            raise ValueError('gold witness input missing from full execution evidence: '+sid)
        # Execution order can predate a minimal-witness clarification. Preserve
        # the historical first test and select by exact input, never by position.
        gold_witness[sid] = matched[0]
    system_config = load(out/'systems.json')
    systems = _available(system_config)
    rows = jsonl(out/'reviews.private.jsonl')
    if len(rows) != len(systems)*160 or {r.get('system_id') for r in rows} != set(systems):
        raise ValueError('require complete reviews for every available system')
    code_rows = jsonl(out/'code-evidence.private.jsonl')
    if len(code_rows) != len(systems)*160 or {r.get('system_id') for r in code_rows} != set(systems):
        raise ValueError('require complete code-evidence population')
    generations, by_system, evidence = {}, {}, {}
    review_ids = set()
    for system in systems:
        generation_path = out/'generations'/system/'final.jsonl'
        if not generation_path.is_file():
            raise ValueError('missing final generation: '+system)
        gens = _index(jsonl(generation_path), 'example_id', 'generation')
        reviews = _index([r for r in rows if r['system_id'] == system], 'example_id', 'review')
        code = _index([r for r in code_rows if r['system_id'] == system], 'example_id', 'code evidence')
        if any(set(index) != set(targets) for index in (gens, reviews, code)):
            raise ValueError('missing/foreign target population: '+system)
        for eid, row in reviews.items():
            target = targets[eid]; source = sources[target['source_id']]; g = gold[source['sample_id']]
            gen = gens[eid]; _generation_binding(gen, target, source)
            if (row.get('family_id') != source['family_id'] or row.get('faulty') is not g['faulty'] or
                    row.get('gold_taxonomy') != g['taxonomy']):
                raise ValueError('review/gold source binding differs')
            # Compare all normalized fields, including authentic A acceptance
            # and actual attempt finishes; do not rewrite controller exports.
            if any(row.get(key) != value for key, value in gen.items()):
                raise ValueError('review/generation binding differs: '+system+'/'+eid)
            axes = row.get('axes', {})
            if set(axes) != set(AXES) or any(v not in VERDICTS for v in axes.values()):
                raise ValueError('pending or invalid review axes')
            if row['status'] != 'valid' and any(v != 'not_evaluable' for v in axes.values()):
                raise ValueError('invalid output requires not_evaluable semantic axes')
            if not isinstance(row.get('evidence'), str) or not row['evidence'].strip():
                raise ValueError('missing source-grounded review evidence')
            rid = row.get('review_id')
            if not isinstance(rid, str) or not rid or rid in review_ids:
                raise ValueError('missing/duplicate review ID')
            review_ids.add(rid)
            contradiction = row.get('taxonomy_feedback_contradiction')
            if type(contradiction) is not bool and contradiction != 'uncertain':
                raise ValueError('missing explicit contradiction verdict')
            if row.get('code_verdict') not in ('pass', 'fail', 'absent', 'uncertain', 'not_evaluable'):
                raise ValueError('invalid code verdict')
            if code[eid].get('generation_status') != row['status']:
                raise ValueError('code evidence/generation status differs')
            if code[eid].get('code_verdict') != row['code_verdict']:
                resolution = row.get('code_resolution_evidence')
                if (row.get('mechanical_code_verdict') != code[eid].get('code_verdict') or
                        row['code_verdict'] not in ('pass', 'fail') or
                        not isinstance(resolution, str) or not resolution.strip()):
                    raise ValueError('code evidence/review verdict differs without source-grounded resolution')
            for key in ('compile_calls', 'runtime_calls'):
                if type(code[eid].get(key)) is not int or code[eid][key] < 0:
                    raise ValueError('missing code-evidence cost')
            evidence[(system, eid)] = code[eid]
        generations[system] = gens; by_system[system] = reviews
    first = {}
    if 'A' in systems:
        first = _index(jsonl(out/'generations/A/first-attempts.jsonl'), 'example_id', 'first A attempt')
        if set(first) != set(targets):
            raise ValueError('first A attempt population differs')
        for eid, gen in first.items():
            _generation_binding(gen, targets[eid], sources[targets[eid]['source_id']])
    return dict(out=out, systems=systems, system_config=system_config, rows=rows, sources=sources,
        gold=gold, targets=targets, syntax=syntax, cases=cases, source_validation=validation,
        full_evidence=full_evidence, gold_witness=gold_witness, generations=generations, by_system=by_system,
        code_evidence=evidence, first_A=first)


def _hash_order(row):
    value = f"{row['family_id']}/{row['sample_id']}/L{row['level']}"
    return hashlib.sha256(value.encode()).hexdigest(), row['example_id']


def _extrema(rows, before='V2-old', after='V3-v3'):
    left = {r['example_id']:r for r in rows if r['system_id'] == before and r['level'] <= 3}
    right = {r['example_id']:r for r in rows if r['system_id'] == after and r['level'] <= 3}
    result = {'improvement':None, 'regression':None}
    candidates = defaultdict(list)
    for eid in sorted(left.keys() & right.keys()):
        a, b = left[eid], right[eid]
        av, bv = semantic_value(a, 'successful_feedback'), semantic_value(b, 'successful_feedback')
        if av is None or bv is None or av == bv:
            continue
        direction = 'improvement' if bv else 'regression'
        changed = [k for k in AXES if (a['axes'][k], b['axes'][k]) == (('fail','pass') if bv else ('pass','fail'))]
        candidates[direction].append((len(changed), _hash_order(a), eid, changed))
    for kind, values in candidates.items():
        n, _, eid, axes = sorted(values, key=lambda item:(-item[0], item[1]))[0]
        result[kind] = dict(example_id=eid, before=before, after=after,
            changed_axes=axes, changed_axis_count=n,
            interpretation='Largest observed known joint change ranked by changed rubric axes; descriptive, not an effect-size estimate.')
    return result


def choose_examples(rows):
    """Frozen, symmetric categories; no response length or favorable-ID filtering."""
    available = [s for s in SYSTEMS if any(r['system_id'] == s for r in rows)]
    index = {s:{r['example_id']:r for r in rows if r['system_id'] == s} for s in available}
    representatives = {r['example_id']:r for r in sorted(rows, key=lambda r:r['system_id'])}
    primary = [eid for eid, r in representatives.items() if r['level'] <= 3]
    selected, used_families, used_sources = [], set(), set()
    categories = {}

    def pick(name, ids, count=1):
        ids = set(ids); chosen = []
        for _ in range(count):
            choices = [eid for eid in ids if eid not in chosen]
            if not choices:
                break
            # A selected target can fulfill several categories. Required quotas
            # count distinct IDs within the category, and the final list is unique.
            eid = min(choices, key=lambda e:(e in selected,
                representatives[e]['family_id'] in used_families,
                representatives[e]['sample_id'] in used_sources, _hash_order(representatives[e])))
            chosen.append(eid)
            if eid not in selected:
                selected.append(eid)
                used_families.add(representatives[eid]['family_id'])
                used_sources.add(representatives[eid]['sample_id'])
        categories[name] = chosen
        return chosen

    improvements, regressions = [], []
    for before, after in PAIRS:
        if before not in index or after not in index:
            continue
        wins, losses = [], []
        for eid in primary:
            av = semantic_value(index[before][eid], 'successful_feedback')
            bv = semantic_value(index[after][eid], 'successful_feedback')
            if av is None or bv is None or av == bv:
                continue
            (wins if bv else losses).append(eid)
        improvements.extend(pick(before+'->'+after+':improvement', wins))
        regressions.extend(pick(before+'->'+after+':regression', losses))
    categories['improvements'] = sorted(set(improvements))
    categories['regressions'] = sorted(set(regressions))
    pick('contradiction', [eid for eid in representatives if any(
        index[s][eid].get('taxonomy_feedback_contradiction') is True for s in available)])
    pick('invalid', [eid for eid in representatives if any(index[s][eid]['status'] != 'valid' for s in available)])
    faulty_l3 = [eid for eid in primary if representatives[eid]['faulty'] and representatives[eid]['level'] == 3]
    repair_ids = [eid for eid in faulty_l3 if any(index[s][eid]['status'] == 'valid' and
        index[s][eid]['axes']['required_content'] == 'pass' and
        index[s][eid]['axes']['l3_repair_direction'] in ('pass','fail') for s in available)]
    repairs = pick('faulty_l3_direction', repair_ids, 2)
    remainder = pick('faulty_l3_missing_direction', [eid for eid in faulty_l3 if eid not in repairs], 2-len(repairs))
    categories['faulty_l3'] = repairs+remainder
    pick('clean', [eid for eid in primary if not representatives[eid]['faulty']], 2)
    pick('faulty', [eid for eid in primary if representatives[eid]['faulty']], 2)
    extrema = _extrema(rows)
    for kind, case in extrema.items():
        if case:
            pick('extreme_'+kind, [case['example_id']])
    if len(selected) < EXAMPLE_POLICY['minimum_examples']:
        pick('fill', [eid for eid in primary if eid not in selected], EXAMPLE_POLICY['minimum_examples']-len(selected))
    return dict(policy=EXAMPLE_POLICY, example_ids=selected, categories=categories, extrema=extrema)


def _objective(rows, semantic_reviewed):
    rows = list(rows)
    return dict(targets=len(rows), schema_valid=sum(r['status'] == 'valid' for r in rows),
        invalid=sum(r['status'] != 'valid' for r in rows),
        status_counts=dict(Counter(r['status'] for r in rows)),
        finish_reason_counts=dict(Counter(str(r.get('finish_reason')) for r in rows)),
        semantic_reviewed=semantic_reviewed,
        note='Objective payload/schema result from authentic pipeline; finish_reason and raw attempts preserved. First-attempt semantics are not inferred from final reviews.')


def _group_pairs(before, after, field):
    groups = defaultdict(lambda:([], []))
    for a, b in zip(sorted(before, key=lambda r:r['example_id']), sorted(after, key=lambda r:r['example_id'])):
        groups[a[field]][0].append(a); groups[a[field]][1].append(b)
    counts = Counter(); detail = []
    for key, (left, right) in sorted(groups.items()):
        uncertain = any(semantic_value(r, 'successful_feedback') is None for r in left+right)
        av = sum(successful_feedback(r) for r in left); bv = sum(successful_feedback(r) for r in right)
        outcome = 'uncertain' if uncertain else 'win' if bv > av else 'loss' if bv < av else 'tie'
        counts[outcome] += 1
        detail.append(dict(id=key, primary_targets=len(left), before_success=av, after_success=bv, outcome=outcome))
    return dict(units=len(groups), counts={k:counts[k] for k in ('win','loss','tie','uncertain')}, groups=detail,
        note='Compare primary successes within each source/family. Any unresolved/invalid paired semantic value leaves the unit uncertain; Levels are repeated views.')


def failure_mechanisms(rows, limit=3):
    """Describe rubric failures with linked evidence; do not invent a causal gold."""
    selected = [r for r in rows if r['system_id'] == 'V3-v3' and r['level'] <= 3]
    kinds = {
        'invalid_payload': ('Output không hợp lệ', 'Tạo ví dụ huấn luyện tuân thủ JSON contract trên các đề/source dài và boundary output; giữ raw lỗi để chẩn đoán transport.'),
        'unsupported_diagnosis': ('Chẩn đoán thiếu căn cứ hoặc thiếu điều kiện', 'Tạo cặp clean/faulty cùng đặc tả, buộc chỉ ra đường chạy và điều kiện kích hoạt; thêm phản ví dụ cho khẳng định phụ không có căn cứ.'),
        'wrong_l3_repair': ('Hướng sửa L3 sai hoặc không hữu ích', 'Tạo ví dụ L3 gồm witness tối thiểu, nguyên nhân và sửa cục bộ; đối chiếu hướng sửa sai nhưng có vẻ hợp lý.'),
        'level_contract': ('Thiếu nội dung cần thiết hoặc sai giới hạn Level', 'Tạo bốn phản hồi theo Level cho cùng source; tách cause L2 với hướng sửa L3, giữ khen đúng trên clean.'),
        'taxonomy_contradiction': ('Mâu thuẫn taxonomy và phản hồi', 'Tạo ví dụ nhãn và phản hồi nhất quán với assessment có căn cứ; thêm các cặp nhãn rỗng nhưng văn bản báo lỗi và ngược lại.'),
        'vietnamese': ('Phản hồi chưa tuân thủ tiếng Việt', 'Tạo phản hồi tiếng Việt giữ chính xác tên biến và điều kiện trong source.'),
    }
    buckets = defaultdict(list)
    for r in selected:
        if r['status'] != 'valid':
            buckets['invalid_payload'].append(r); continue
        axes = r['axes']
        if any(axes[k] == 'fail' for k in ('diagnosis_supported','coverage','factual_fidelity','location_and_condition')):
            buckets['unsupported_diagnosis'].append(r)
        if r['faulty'] and r['level'] == 3 and axes['l3_repair_direction'] == 'fail':
            buckets['wrong_l3_repair'].append(r)
        if any(axes[k] == 'fail' for k in ('disclosure_compliance','required_content')):
            buckets['level_contract'].append(r)
        if r.get('taxonomy_feedback_contradiction') is True:
            buckets['taxonomy_contradiction'].append(r)
        if axes['vietnamese_compliance'] == 'fail':
            buckets['vietnamese'].append(r)
    result = []
    for kind in sorted(buckets, key=lambda k:(-len({r['family_id'] for r in buckets[k]}), -len(buckets[k]), k))[:limit]:
        values = sorted(buckets[kind], key=_hash_order)
        result.append(dict(mechanism=kind, description=kinds[kind][0], targets=len(values),
            families=len({r['family_id'] for r in values}), example_ids=[r['example_id'] for r in values],
            source_grounded_evidence=[dict(example_id=r['example_id'], evidence=r['evidence']) for r in values[:3]],
            later_training_proposal=kinds[kind][1], training_executed=False))
    return result


def _analyze(pop):
    rows = pop['rows']; systems = pop['systems']; by_system = pop['by_system']
    metrics = {s:summarize_system(list(by_system[s].values())) for s in systems}
    pairs = {}
    for before, after in PAIRS:
        if before not in systems or after not in systems:
            continue
        left, right = list(by_system[before].values()), list(by_system[after].values())
        lp, rp = [r for r in left if r['level'] <= 3], [r for r in right if r['level'] <= 3]
        pairs[before+'->'+after] = dict(before=before, after=after,
            primary=paired_analysis(lp, rp),
            secondary_l4=paired_analysis([r for r in left if r['level'] == 4], [r for r in right if r['level'] == 4]),
            primary_source_units=_group_pairs(lp, rp, 'sample_id'),
            primary_family_units=_group_pairs(lp, rp, 'family_id'))
    safety = {s:level_safety(list(by_system[s].values()), list(by_system['V3-v3'].values()))
              for s in ('V2-old','A') if s in systems}
    decision = screen_v3(metrics, safety)
    decision['failure_mechanisms'] = [] if decision['passed'] else failure_mechanisms(rows)
    decision['uncertainty_note'] = 'Nếu không có cơ chế thất bại xác nhận, chênh lệch bằng/không rõ vẫn không đạt cổng cải thiện nghiêm ngặt; không suy diễn nguyên nhân.'
    objective = {s:dict(final=_objective(pop['generations'][s].values(), True)) for s in systems}
    if 'A' in systems:
        objective['A']['first'] = _objective(pop['first_A'].values(), False)
    return dict(metrics=metrics, comparison=dict(pairs=pairs, level_safety=safety,
            statistical_unit='40 sources /20 paired families; primary120 repeated source-Level targets; secondary L4 separately40'),
        decision=decision, first_final_objective=objective, examples=choose_examples(rows),
        available_systems=list(systems), populations=dict(sources=40, families=20,
            targets_per_system=160, primary_targets_per_system=120, secondary_l4_targets_per_system=40,
            evaluated_targets=len(rows)), claim='Newly authored, not previously evaluated; agent-authored gold and agent review, not independent human evaluation, pretraining independence, or official Task3 score.')


def analyze(out):
    """Return deterministic analysis without writing artifacts or calling models."""
    return _analyze(validate_populations(out))


def pre(value):
    return '<pre>'+html.escape(value if isinstance(value, str) else dump(value))+'</pre>'


def render_casebook(pop):
    parts = ['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>Task3 — fresh evaluation toàn bộ cặp</title><style>body{font:15px system-ui;margin:24px;background:#f6f7fa}section,article{background:white;border:1px solid #ccd;padding:16px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f2f5;padding:12px}.systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}article{min-width:0}[hidden]{display:none}.state{font-weight:bold}label{display:inline-block;margin:6px}</style>',
        '<h1>Fresh evaluation — toàn bộ 160 targets × '+str(len(pop['systems']))+' systems</h1>',
        '<p>Mới được tác giả agent soạn và đánh giá; không phải gold người độc lập, không chứng minh độc lập với pretraining, không phải điểm chính thức. Gold và tests chỉ thuộc đánh giá riêng tư.</p>',
        '<label>Tìm ID, đề, source, output, lý do <input id="find" type="search"></label>',
        '<label>Level <select id="level"><option value="">Tất cả</option><option>1</option><option>2</option><option>3</option><option>4</option></select></label>',
        '<label>Source <select id="kind"><option value="">Tất cả</option><option value="clean">clean</option><option value="faulty">faulty</option></select></label>',
        '<label><input id="invalid" type="checkbox"> Chỉ targets có output invalid</label>']
    for eid, target in sorted(pop['targets'].items()):
        sid = target['source_id']; source = pop['sources'][sid]; g = pop['gold'][sid]
        level = target['input']['target_feedback_level']; kind = 'faulty' if g['faulty'] else 'clean'
        invalid = any(pop['by_system'][s][eid]['status'] != 'valid' for s in pop['systems'])
        parts += [f'<section class="case" data-level="{level}" data-kind="{kind}" data-invalid="{int(invalid)}">',
            '<h2>'+html.escape(eid)+' — L'+str(level)+' — '+kind+'</h2>',
            '<details><summary>Đặc tả và source đầy đủ</summary><h3>Đặc tả</h3>'+pre(source['statement'])+
            '<h3>C++11 source</h3>'+pre(source['code'])+'<h3>Syntax-only compiler view được phép</h3>'+pre(target['input']['compile_log'])+'</details>',
            '<details><summary>Gold và bằng chứng riêng tư — tách khỏi input model</summary>'+pre(g)+
            '<h3>Witness khớp input trong gold — expected/actual</h3>'+pre(pop['gold_witness'][sid])+
            '<h3>Compile/runtime validation — giữ nguyên tóm tắt và thứ tự kiểm thử gốc</h3>'+pre(pop['source_validation'][sid])+
            '<h3>Bằng chứng execution đầy đủ — thứ tự gốc</h3>'+pre(pop['full_evidence'][sid])+'</details><div class="systems">']
        for system in pop['systems']:
            row = pop['by_system'][system][eid]; gen = pop['generations'][system][eid]
            parts += ['<article class="system-panel"><h3>'+html.escape(system)+'</h3>',
                '<p class="state">Trạng thái: '+html.escape(row['status'])+'</p>',
                '<h4>Raw output — đầy đủ</h4>'+pre(gen['raw']), '<h4>Parsed output</h4>'+pre(gen.get('parsed')),
                '<h4>Verdicts và lý do source-grounded</h4>'+pre({k:row.get(k) for k in (
                    'axes','code_verdict','mechanical_code_verdict','code_resolution_evidence',
                    'taxonomy_feedback_contradiction','evidence','review_id')}),
                '<details><summary>Generation metadata / authentic finish reasons</summary>'+pre({k:v for k,v in gen.items() if k not in ('raw','parsed')})+'</details>',
                '<details><summary>Code evidence và chi phí compiler/runtime</summary>'+pre(pop['code_evidence'][(system,eid)])+'</details>']
            if system == 'A':
                parts += ['<details><summary>A first attempt — chỉ objective/schema, chưa review semantic</summary>'+pre(pop['first_A'][eid])+'</details>']
            parts += ['</article>']
        parts += ['</div></section>']
    parts += ['<script>function filter(){const q=document.getElementById("find").value.toLowerCase(),l=document.getElementById("level").value,k=document.getElementById("kind").value,i=document.getElementById("invalid").checked;document.querySelectorAll(".case").forEach(s=>s.hidden=!(s.textContent.toLowerCase().includes(q)&&(!l||s.dataset.level===l)&&(!k||s.dataset.kind===k)&&(!i||s.dataset.invalid==="1")));}["find","level","kind","invalid"].forEach(id=>document.getElementById(id).addEventListener("input",filter));</script></html>']
    return '\n'.join(parts)


def ratio(n, d):
    return f'{n}/{d} ({100*n/d:.1f}%)' if d else f'{n}/0 (không áp dụng)'


def table(headers, rows):
    def cell(v):
        return html.escape('không đo' if v is None else str(v)).replace('|','&#124;').replace('\n','<br>')
    return '\n'.join(['| '+' | '.join(map(cell, headers))+' |', '| '+' | '.join('---' for _ in headers)+' |']+
        ['| '+' | '.join(map(cell, r))+' |' for r in rows])


def _summary_table(metrics):
    return table(['System','Thành công','Clean alarm','Clean invalid','Faulty miss','Faulty invalid','Miss + invalid','Invalid','Disclosure','Required','Tiếng Việt','Mâu thuẫn'], [
        [s, ratio(m['successful_feedback'],m['targets']), ratio(m['clean_false_alarms'],m['clean_targets']),
         ratio(m['clean_invalids'],m['clean_targets']),ratio(m['faulty_misses'],m['faulty_targets']),
         ratio(m['faulty_invalids'],m['faulty_targets']),ratio(m['faulty_misses_with_invalid'],m['faulty_targets']),
         ratio(m['invalid'],m['targets']),ratio(m['disclosure_compliant'],m['targets']),
         ratio(m['required_content_met'],m['targets']),ratio(m['axes']['vietnamese_compliance']['pass'],m['targets']),
         ratio(m['contradictions'],m['targets'])] for s,m in metrics.items()])


def render_examples(pop, analysis):
    selected = analysis['examples']
    lines = ['# Ví dụ fresh evaluation Task3','',
        'Quy tắc đã đóng băng trước inference. Tất cả ví dụ giữ đầy đủ đề/source, output từng hệ thống và lý do; không cắt đoạn. Mọi target còn lại nằm trong `paired-casebook.html`.','',
        'Dữ liệu newly authored, not previously evaluated; gold và review do agent, không phải human gold độc lập hoặc điểm chính thức.','',
        '## Quy tắc chọn tất định','',pre(EXAMPLE_POLICY),'','## Các nhóm bắt buộc','']
    for name, ids in selected['categories'].items():
        lines += ['- '+html.escape(name)+': '+(', '.join(html.escape(e) for e in ids) if ids else 'Không có trường hợp đáp ứng trong dữ liệu đã review.')]
    lines += ['', '## Mạnh nhất và giảm lớn nhất đã quan sát V2-old → V3-v3','',pre(selected['extrema']),'']
    for eid in selected['example_ids']:
        target = pop['targets'][eid]; sid = target['source_id']; g = pop['gold'][sid]
        lines += ['## '+html.escape(eid)+' — '+('faulty' if g['faulty'] else 'clean'),'',
            '**Đặc tả đầy đủ:**','',pre(pop['sources'][sid]['statement']),'',
            '**Source đầy đủ:**','',pre(pop['sources'][sid]['code']),'',
            '<details><summary>Gold và bằng chứng riêng tư</summary>'+pre(g)+
            '<h4>Witness khớp input trong gold — expected/actual</h4>'+pre(pop['gold_witness'][sid])+
            '<h4>Validation và execution evidence — giữ nguyên thứ tự gốc</h4>'+pre(pop['source_validation'][sid])+pre(pop['full_evidence'][sid])+'</details>','']
        for system in pop['systems']:
            row = pop['by_system'][system][eid]
            lines += ['### '+html.escape(system),'','**Raw output đầy đủ:**','',pre(row['raw']),'',
                '**Parsed / trạng thái / review / source evidence:**','',pre({k:row.get(k) for k in (
                    'parsed','status','finish_reason','actual_attempt_finish_reasons','axes','code_verdict',
                    'mechanical_code_verdict','code_resolution_evidence',
                    'taxonomy_feedback_contradiction','evidence','review_id')}),'',
                '**Code evidence:**','',pre(pop['code_evidence'][(system,eid)]),'']
    return '\n'.join(lines)+'\n'


def render_report(pop, analysis, costs):
    metrics = analysis['metrics']; decision = analysis['decision']; pairs = analysis['comparison']['pairs']
    n = analysis['populations']['evaluated_targets']
    screening = 'ĐẠT' if decision['passed'] else 'KHÔNG ĐẠT'
    baseline = ('V3 đủ điều kiện cho một public inference experiment được cho phép riêng; chưa được phép chạy hoặc submit.'
        if decision['passed'] else 'Giữ A làm submission baseline; không chạy public inference hoặc chọn system theo từng public ID.')
    lines = ['# Task3 — fresh evaluation A / V2-old / V3-v3','',
        f'Đã đánh giá **{n}/{160*len(pop["systems"])} targets**, gồm 160 targets mỗi system khả dụng. **V3 {screening} frozen screening rule.** '+baseline,'',
        '40 source thuộc 20 family, mỗi family gồm clean/faulty chung đặc tả. L1–L3 là primary 120 targets/system (60 clean,60 faulty); L4 là secondary 40 targets/system. Bốn Level của một source không phải bốn chương trình độc lập.','',
        'Đây là dữ liệu newly authored, not previously evaluated và source-grounded agent review; không phải gold người độc lập, không xác lập độc lập với pretraining, không phải điểm chính thức. Finite tests hỗ trợ kết luận theo đặc tả, không chứng minh đúng phổ quát. Không suy ra điểm leaderboard từ local F1.','',
        '## So sánh primary L1–L3','',_summary_table({s:m['primary'] for s,m in metrics.items()}),'',
        table(['System','Supported faulty diagnosis L2–L3','Correct useful faulty L3 repair','Taxonomy precision / recall / F1 (auxiliary)'],[
            [s,ratio(m['faulty_l23']['supported_faulty_diagnosis'],m['faulty_l23']['targets']),
             ratio(m['faulty_l3']['faulty_l3_correct'],m['faulty_l3']['targets']),
             ' / '.join('NA' if v is None else f'{v:.4f}' for v in [m['primary']['taxonomy_auxiliary']['taxonomy']['all_targets_conservative'][k] for k in ('precision','recall','f1')])]
            for s,m in metrics.items()]),'',
        'Invalid giữ nguyên trong mọi mẫu số primary. Faulty miss là valid nhưng taxonomy rỗng; faulty invalid được báo riêng và cộng vào miss+invalid. Taxonomy nonempty không tự chứng minh chẩn đoán có căn cứ. Taxonomy F1 conservative: invalid faulty vẫn góp gold vào false negatives.','',
        'Disclosure chỉ kiểm tra giới hạn tiết lộ; required content và thành công được chấm riêng. False praise trên faulty không thể thành công. L1 không đòi location/cause bị cấm; L2 cause chính xác không tự là leakage; L3 đánh giá hướng sửa thực tế; L4 không bắt buộc có code, nhưng code đã cung cấp cần được kiểm tra.','',
        '## Clean và faulty primary','']
    for kind in ('clean','faulty'):
        lines += ['### '+kind,'',_summary_table({s:m['primary_by_status'][kind] for s,m in metrics.items()}),'']
    lines += ['## L4 secondary — không góp vào screening','',_summary_table({s:m['secondary_l4'] for s,m in metrics.items()}),'',
        '## Mỗi Level và source status','',table(['System','Level','Status','Thành công','Invalid','Disclosure','Required','Mâu thuẫn'],[
            [s,l,kind,ratio(m['successful_feedback'],m['targets']),ratio(m['invalid'],m['targets']),
             ratio(m['disclosure_compliant'],m['targets']),ratio(m['required_content_met'],m['targets']),ratio(m['contradictions'],m['targets'])]
            for s,system in metrics.items() for l in ('1','2','3','4') for kind in ('clean','faulty') for m in [system['by_level_status'][l][kind]]]),'',
        '## Từng cổng screening đã đóng băng','']
    for comparator, checks in decision['comparisons'].items():
        lines += ['### V3-v3 so với '+comparator,'',table(['Điều kiện','V3','Comparator/ngưỡng','Phép so sánh','Đạt'],[
            [name,c['v3'],c['comparator'],c['operator'],'có' if c['passed'] else 'không'] for name,c in checks.items()]),'']
    lines += ['Mỗi baseline phải qua mọi cổng riêng. Có mâu thuẫn primary xác nhận ở ít nhất hai family sẽ chặn; chỉ một disclosure/required-content failure mới so với target hợp lệ đạt của baseline cũng chặn. Semantic dispute không bị biến thành pass. Screening chỉ cho phép cân nhắc thí nghiệm kế tiếp, không chứng minh khả năng tổng quát hóa.','',
        '## Ba so sánh ghép cặp (nếu A khả dụng)','',
        'Win/loss có hướng từ system trước sang sau. Semantic không rõ hoặc invalid ở một vế giữ uncertain. Các tổng nhóm source/family mô tả số success trong 3/6 primary targets, không coi Level là đơn vị độc lập. Không báo confidence interval.','']
    for name, pair in pairs.items():
        lines += ['### '+name,'',table(['Phạm vi / trục','Win','Loss','Tie','Uncertain'],[
            [scope+' / '+axis,*[values[k] for k in ('win','loss','tie','uncertain')]]
            for scope in ('primary','secondary_l4') for axis,values in pair[scope]['overall']['semantic'].items()]),'',
            table(['Đơn vị primary','n','Win','Loss','Tie','Uncertain'],[
                [kind,unit['units'],*[unit['counts'][k] for k in ('win','loss','tie','uncertain')]]
                for kind in ('primary_source_units','primary_family_units') for unit in [pair[kind]]]),'']
    lines += ['## Tóm tắt source/family','',table(['System','40 source: success đủ 3/3 primary','20 family: success đủ 6/6 primary','Source có invalid primary','Family có contradiction primary'],[
        [s,ratio(sum(g['primary_success']==3 for g in m['grouped']['sources'].values()),40),
         ratio(sum(g['primary_success']==6 for g in m['grouped']['families'].values()),20),
         sum(g['primary_invalid']>0 for g in m['grouped']['sources'].values()),
         sum(g['primary_contradictions']>0 for g in m['grouped']['families'].values())] for s,m in metrics.items()]),'',
        'Chi tiết từng source và family nằm trong `metrics.json`; transition taxonomy/validity và từng target nằm trong `comparison.json`.','',
        '## A: first attempt và final tách riêng','',pre(analysis['first_final_objective']),'',
        'First-attempt chỉ báo objective/schema; không gán review semantic final cho first attempt. A dùng pipeline lịch sử đa giai đoạn và recovery/export authentic; finish reason thực của các attempt giữ nguyên. A là system-level comparator; khác biệt model, prompt, parser, recovery, compiler view, dtype và generation có thể gây confound, không phải thí nghiệm chỉ thay adapter.','',
        '## System identity và giới hạn integrity','',pre(pop['system_config']),'']
    if 'A' not in pop['systems']:
        lines += ['A unavailable theo systems audit; không dựng A-like replacement. Hoàn thành so sánh V2-old/V3-v3; không có số liệu A fresh.','']
    lines += ['## Ví dụ thật và extrema','',
        'Quy tắc chọn cố định trước inference, ưu tiên family khác nhau và công bố cả cải thiện/giảm nếu xuất hiện. Các ví dụ bên dưới không cắt raw/source. Toàn bộ targets có trong `paired-casebook.html`.','',
        pre(analysis['examples']['extrema']),'']
    # Include complete examples in the main report as required; the companion
    # file remains a direct, standalone reading view of the same selected IDs.
    lines += [render_examples(pop, analysis).replace('# Ví dụ fresh evaluation Task3', '### Ví dụ đã chọn', 1),'',
        '## Cơ chế thất bại quan sát và đề xuất cho lần huấn luyện sau','']
    if decision['failure_mechanisms']:
        lines += [pre(decision['failure_mechanisms']), '',
            'Tối đa ba nhóm trên được xếp theo số family rồi số target; một target có thể nằm ở nhiều nhóm. Đây là mô tả rubric có bằng chứng, không khẳng định nguyên nhân nội tại của model. Không huấn luyện hoặc sửa tập đánh giá trong task này.','']
    else:
        lines += ['Không có cơ chế thất bại xác nhận cần đề xuất từ các reviews này. '+decision['uncertainty_note'],'']
    lines += ['## Chi phí và runtime thực tế','',pre(costs),'',
        'Target end-to-end khác số model calls: A có nhiều giai đoạn/recovery; không lấy 480 targets thay cho số calls. Token/time/load/VRAM và compiler/runtime costs đọc theo measurement scope đã ghi trong artifact; trường không đo không được coi bằng 0. Phân tích/báo cáo này không gọi model hoặc compiler/runtime.','',
        '## Artifact và tái lập offline','',
        'Run: '+html.escape(str(pop['out']))+'. Các file: `manifest.json`, `systems.json`, `dataset-manifest.json`, `dataset.private.jsonl`, `gold.private.jsonl`, `evidence/`, `frozen-policy.json`, `prompts/`, `generations/`, `reviews.private.jsonl`, `metrics.json`, `comparison.json`, `costs-and-runtime.json`, `decision.json`, `paired-casebook.html`, `EXAMPLES.vi.md`, `REPORT.vi.md`, `reproduction-commands.json`.','',
        '```bash','cd /workspace/llm-final-project-arm-d-plus',
        '/workspace/llm-final-project/.venv-task3/bin/python -m pytest -q tests/test_task3_fresh_eval.py tests/test_task3_fresh_eval_report.py',
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_fresh_eval.py verify --out '+str(pop['out']),
        '/workspace/llm-final-project/.venv-task3/bin/python scripts/task3_fresh_eval_report.py --out '+str(pop['out']), '```','',
        '## Bước tiếp theo','',
        ('Chỉ cân nhắc một public inference experiment sau khi được cho phép riêng, giữ system frozen trong run này.' if decision['passed'] else
         'Giữ A làm submission baseline; dùng tối đa ba nhóm lỗi có bằng chứng trên để thiết kế dữ liệu huấn luyện cho một run được cho phép sau này.')]
    return '\n'.join(lines)+'\n'


def build(out):
    """Verify, analyze and write only artifacts inside this fresh run."""
    from scripts.task3_fresh_eval import verify_frozen
    out = Path(out).resolve()
    verification = verify_frozen(out)
    pop = validate_populations(out)
    analysis = _analyze(pop)
    costs = load(out/'costs-and-runtime.json')
    # Render and validate every artifact before the first write.
    outputs = {
        'metrics.json': dump(analysis['metrics'])+'\n',
        'comparison.json': dump(dict(analysis['comparison'], examples=analysis['examples'],
            first_final_objective=analysis['first_final_objective'], populations=analysis['populations'],
            claim=analysis['claim'], frozen_verification=verification))+'\n',
        'decision.json': dump(analysis['decision'])+'\n',
        'paired-casebook.html': render_casebook(pop),
        'EXAMPLES.vi.md': render_examples(pop, analysis),
        'REPORT.vi.md': render_report(pop, analysis, costs),
    }
    for name, text in outputs.items():
        (out/name).write_text(text, encoding='utf-8')
    return dict(passed=True, systems=list(pop['systems']), panels=len(pop['rows']),
        decision_passed=analysis['decision']['passed'], outputs=[str(out/name) for name in outputs])


report = build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(dump(build(args.out)))


if __name__ == '__main__':
    main()
