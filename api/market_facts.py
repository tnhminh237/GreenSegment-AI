"""Python-owned report facts and scoped numeric bindings. No model or network calls."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

VALIDATOR_VERSION = "verified-facts-v5"


class FactValidationError(ValueError):
    def __init__(self, **details):
        super().__init__(details["rule"])
        self.details = details


def _ascii(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold().replace("đ", "d")) if not unicodedata.combining(c))


def build_verified_facts(result: dict) -> dict:
    """Values retain source precision. Displays use one explicit ROUND_HALF_UP policy."""
    facts = {}
    source = "data/processed/greensegment_clusters_2024.csv"
    def add(key, value, kind, scope, origin):
        decimals = 2 if kind in {"percentage", "percentage_points", "ghg"} else 0
        number = Decimal(str(value)).quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP)
        display = format(abs(number) if kind == "percentage_points" else number, f".{decimals}f").replace(".", ",")
        if kind == "count":
            display = format(number, ",.0f").replace(",", ".")
        if kind == "percentage":
            display += "%"
        if kind == "percentage_points":
            display = ("−" if number < 0 else "+") + display + " điểm phần trăm"
        facts[key] = {"value": value, "display": display, "kind": kind, "scope": scope,
                      "decimals": decimals, "rounding": "ROUND_HALF_UP", "source": origin}
    add("dataset.year", result["year"], "year", "dataset", source + ":year")
    add("dataset.city_count", result["source_city_count"], "count", "dataset", source + ":all_rows")
    add("model.k", 3, "count", "model", "models/kmeans_metadata.json:k")
    for cid in range(3):
        add(f"model.cluster_ids.{cid}", cid, "cluster_id", "model", source + ":cluster_id")
    add("top.limit", result["query"]["limit"], "count", "top", "confirmed_query.limit")
    for field in ("min_sector_share_percent", "max_sector_share_percent"):
        if result["query"][field] is not None:
            add(f"filters.{field}", result["query"][field], "percentage", "filters", "confirmed_query." + field)
    for scope, summary in (("matching", result["matching_summary"]), ("top", result["top_summary"])):
        for field in ("city_count", "country_count"):
            add(f"{scope}.{field}", summary[field], "count", scope, source + f":{scope}.{field}")
        if summary["mean_sector_share_percent"] is not None:
            add(f"{scope}.mean_sector_share_percent", summary["mean_sector_share_percent"], "percentage", scope,
                source + f":mean(share_{result['query']['sector']}_2024*100),{scope}")
        for cid, count in summary["cluster_counts"].items():
            add(f"{scope}.clusters.{cid}.city_count", count, "count", scope, source + f":{scope},cluster_id={cid}")
            add(f"{scope}.clusters.{cid}.city_percentage", count * 100 / summary["city_count"], "percentage", scope,
                source + f":{scope},cluster_id={cid},count/scope_count*100")
    items = result["items"]
    indices = sorted({0, len(items) // 2, len(items) - 1})
    representatives = [items[i] for i in indices]
    for i in indices:
        city = items[i]
        prefix = f"cities.{city['city_id']}"
        origin = source + ":city_id=" + city["city_id"]
        for field, kind in (("sector_share_percent", "percentage"), ("sector_emissions", "ghg"),
                            ("ghg_total_2024", "ghg"), ("cluster_id", "cluster_id")):
            if city[field] is not None:
                add(f"{prefix}.{field}", city[field], kind, "city", origin + ":" + field)
        add(f"{prefix}.rank", i + 1, "rank", "city", origin + ":rank_in_confirmed_sort")
        for scope, summary in (("matching", result["matching_summary"]), ("top", result["top_summary"])):
            if city["sector_share_percent"] is not None:
                add(f"{prefix}.share_gap_{scope}_pp", city["sector_share_percent"] - summary["mean_sector_share_percent"],
                    "percentage_points", scope, origin + f":share-minus-{scope}-mean")
    for a in representatives:
        for b in representatives:
            if a["city_id"] != b["city_id"] and a["sector_share_percent"] is not None:
                add(f"comparisons.{a['city_id']}.{b['city_id']}.share_gap_pp", a["sector_share_percent"] - b["sector_share_percent"],
                    "percentage_points", "comparison", source + f":share({a['city_id']})-share({b['city_id']})")
    return facts


# Accept VI and international separators, including nonbreaking thousands spaces.
_TOKEN = r"(?<![\w.,])[-+−]?(?:\d{1,3}(?:[.\u00a0\u202f ]\d{3})+(?:,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)(?!\w|[.,]\d)"
_REFERENCE = r"\{\{([^{}]{1,160})\}\}"
_RANK_PREFIX = r"\b(?:thu hang|xep hang|dung thu|xep thu|hang|rank|vi tri(?: thu)?)\s*[:=]?\s*$"


def _reference_key(value, facts):
    """Normalize template syntax only; never evaluate a model-supplied path."""
    key = value.strip()
    if key in facts:
        return key
    if key.startswith("verified_facts."):
        key = key[len("verified_facts."):]
    if key in facts:
        return key
    for suffix in (".display", ".value"):
        if key.endswith(suffix) and key[:-len(suffix)] in facts:
            return key[:-len(suffix)]
    return None


def _fail(path, rule, fact_id=None, fact=None, observed=None):
    details = {"field_path": path, "rule": rule}
    if fact is not None:
        details.update(fact_id=fact_id, scope=fact["scope"], expected=fact["display"], source=fact["source"])
    if observed is not None:
        # Only bounded, parsed numeric scalars; never copy arbitrary prose or unknown IDs.
        value = str(observed)
        details["observed"] = value if len(value) <= 24 else "<redacted-number>"
    raise FactValidationError(**details)


def _scope(prefix, path):
    scope = "city" if path.startswith("city_comparisons.") else "matching" if path.split(".")[0] in {
        "research_request", "emissions_profile", "cluster_distribution"} else None
    patterns = {"dataset": r"toan bo (?:bo )?du lieu|bo du lieu goc",
                "matching": r"(?:toan bo )?tap (?:phu hop|dap ung|thoa)|toan bo ket qua",
                "top": r"\btop\b|dang hien thi|danh sach hien thi"}
    markers = [(m.start(), candidate) for candidate, pattern in patterns.items() for m in re.finditer(pattern, prefix)]
    return max(markers)[1] if markers else scope


def _model_cluster_count(prefix, suffix):
    return re.match(r"\s*cum\b", suffix) and (
        re.search(r"\bk[- ]means\b|\bmo hinh\b|\bphan cum\b", prefix)
        or re.match(r"\s*cum\s+k[- ]means\b", suffix))


def _fact_in_context(text, start, end, path, city_id, context, hint=None):
    prior = re.sub(_REFERENCE, lambda m: context["verified_facts"].get(_reference_key(m[1], context["verified_facts"]), {}).get("display", ""), text[:start])
    prefix = _ascii(re.split(r"[!?;\n]|\.(?=\s|$)", prior)[-1])
    suffix = _ascii(text[end:end + 75])
    scope = _scope(prefix, path)
    facts = context["verified_facts"]
    # A city may be identified by the structured comparison, or an unambiguous supplied name.
    names = [(prefix.rfind(_ascii(c["city_name"])), c["city_id"]) for c in context["representative_cities"]
             if _ascii(c["city_name"]) in prefix]
    if names:
        city_id = max(names)[1]
    if re.search(r"(?:\bnam|\byear)\s*$", prefix):
        return "dataset.year"
    if re.search(r"\bk\s*=\s*$", prefix) or _model_cluster_count(prefix, suffix):
        return "model.k"
    if re.search(r"\bcum(?:\s+so)?\s*$", prefix):
        return "@cluster_id" if city_id is None else f"cities.{city_id}.cluster_id"
    if re.search(_RANK_PREFIX, prefix):
        return f"cities.{city_id}.rank" if city_id else None
    if re.search(r"\btop\s*$", prefix):
        return "top.limit" if re.search(r"gioi han|toi da|yeu cau", prefix) else "top.city_count"
    clusters = re.findall(r"\bcum\s+(?:so\s+)?([012])\b", prefix)
    if city_id and re.search(r"ghg|luong phat thai", prefix) and not re.search(r"ty trong|ti trong|trung binh|chenh lech", prefix):
        return f"cities.{city_id}.ghg_total_2024" if re.search(r"tong ghg|tong phat thai", prefix) else f"cities.{city_id}.sector_emissions"
    is_percent = re.match(r"\s*(?:%|phan\s+tram)", suffix) or (hint or {}).get("kind") == "percentage" or re.search(r"trung binh|\bmean\b", prefix)
    is_pp = re.match(r"\s*(?:diem\s+(?:phan\s+tram|%)|dpt)", suffix) or (hint or {}).get("kind") == "percentage_points"
    if is_pp:
        if city_id and scope in {"matching", "top"}:
            return f"cities.{city_id}.share_gap_{scope}_pp"
        return None
    if is_percent:
        if re.search(r"toi thieu|nguong duoi|tu\s*$", prefix):
            return "filters.min_sector_share_percent" if "filters.min_sector_share_percent" in facts else None
        if re.search(r"toi da|nguong tren", prefix):
            return "filters.max_sector_share_percent" if "filters.max_sector_share_percent" in facts else None
        # A city's sector share is not the percentage of cities in its cluster.
        # Recognize a new local share predicate after the preceding cluster label.
        last_cluster = list(re.finditer(r"\bcum\s+(?:so\s+)?[012]\b", prefix))
        local = prefix[last_cluster[-1].end():] if last_cluster else prefix
        if city_id and re.search(r"ty trong|ti trong", local) and not re.search(r"trung binh|mean", local):
            return f"cities.{city_id}.sector_share_percent"
        if clusters and scope in {"matching", "top"}:
            return f"{scope}.clusters.{clusters[-1]}.city_percentage"
        if city_id and not re.search(r"trung binh|mean", prefix):
            return f"cities.{city_id}.sector_share_percent"
        if scope in {"matching", "top"} and re.search(r"trung binh|mean", prefix):
            return f"{scope}.mean_sector_share_percent"
        return None
    if re.match(r"\s*(?:do thi|thanh pho|cities)\b", suffix):
        if clusters and scope in {"matching", "top"}:
            return f"{scope}.clusters.{clusters[-1]}.city_count"
        return f"{scope}.city_count" if scope in {"dataset", "matching", "top"} else None
    if re.match(r"\s*(?:quoc gia|nuoc|countries)\b", suffix):
        return f"{scope}.country_count" if scope in {"matching", "top"} else None
    if city_id and re.search(r"ghg|phat thai", prefix):
        return f"cities.{city_id}.ghg_total_2024" if re.search(r"tong ghg|tong phat thai", prefix) else f"cities.{city_id}.sector_emissions"
    return None


def _parse(token, kind):
    token = token.replace("−", "-").replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    if "," in token and "." in token:
        decimal = "," if token.rfind(",") > token.rfind(".") else "."
        grouping = "." if decimal == "," else ","
        token = token.replace(grouping, "").replace(decimal, ".")
    elif any(c in token for c in (".", ",")):
        separator = "," if "," in token else "."
        grouped = re.fullmatch(r"[-+]?\d{1,3}(?:" + re.escape(separator) + r"\d{3})+", token)
        token = token.replace(separator, "") if grouped and kind not in {"percentage", "percentage_points"} else token.replace(separator, ".")
    precision = len(token.rsplit(".", 1)[1]) if "." in token else 0
    return Decimal(token), precision


def _check_reference(text, start, end, path, city_id, context, key):
    """Typed IDs supply context. Reject direct contradictions, not remote keywords.

    Inferring a different metric from an earlier clause was rejecting perfectly
    valid city-share references after a cluster ID. Only explicit local labels
    can contradict an already typed, Python-owned reference.
    """
    facts, fact = context["verified_facts"], context["verified_facts"][key]
    prior = re.sub(_REFERENCE, lambda m: facts.get(_reference_key(m[1], facts), {}).get("display", ""), text[:start])
    prefix = _ascii(re.split(r"[!?;\n]|\.(?=\s|$)", prior)[-1]).replace("*", "").replace("`", "").strip()
    named = [(m.start(), c["city_id"]) for c in context["representative_cities"]
             for m in re.finditer(r"(?<!\w)" + re.escape(_ascii(c["city_name"])) + r"(?!\w)", prefix)]
    active_city = max(named)[1] if named else city_id
    expected = None
    direct_scope = re.search(r"(\btop(?:\s*(?:n|\d+))?|(?:toan bo )?tap (?:phu hop|dap ung)|dang hien thi)\s*(?:(?:co|gom|bao gom|hien thi|la|voi|ty trong|trung binh|quoc gia|do thi|:)\s*)*$", prefix)
    scope = None
    if direct_scope:
        label = direct_scope[1]
        scope = "top" if re.match(r"top|dang hien thi", label) else "matching"
        if fact["scope"] in {"matching", "top"} and fact["scope"] != scope:
            expected = key.replace(fact["scope"] + ".", scope + ".", 1)
    if re.search(r"(?:\bnam|\byear)\s*[:=]?\s*$", prefix):
        expected = "dataset.year"
    elif re.search(r"\bk\s*=\s*$", prefix) or _model_cluster_count(prefix, _ascii(text[end:end + 75])):
        expected = "model.k"
    elif re.search(r"\bcum(?:\s+so)?\s*$", prefix):
        if fact["kind"] != "cluster_id":
            _fail(path, "wrong_fact_kind", key, fact)
        if active_city and (named or re.search(r"thuoc\s+cum(?:\s+so)?\s*$", prefix)):
            target = f"cities.{active_city}.cluster_id"
            if fact["value"] != facts[target]["value"]:
                expected = target
    elif re.search(r"trung binh\s*$", prefix):
        expected = f"{scope or (fact['scope'] if fact['scope'] in {'matching', 'top'} else 'matching')}.mean_sector_share_percent"
    elif re.search(_RANK_PREFIX, prefix) and active_city:
        expected = f"cities.{active_city}.rank"
    if expected in facts and expected != key:
        target = facts[expected]
        raise FactValidationError(field_path=path, rule="wrong_fact_context", fact_id=expected,
                                  referenced_fact_id=key, expected=target["display"], observed=fact["display"],
                                  scope=target["scope"], source=target["source"])
    if key.startswith("cities.") and city_id and key.split(".")[1] != city_id:
        peer = next((c for c in context["representative_cities"] if c["city_id"] == key.split(".")[1]), None)
        if peer is None or re.search(r"(?<!\w)" + re.escape(_ascii(peer["city_name"])) + r"(?!\w)", prefix) is None:
            _fail(path, "wrong_city_context", key, fact)
    if key.startswith("comparisons.") and city_id and city_id not in key.split(".")[1:3]:
        _fail(path, "wrong_city_context", key, fact)


def render_verified_text(text: str, path: str, context: dict, city_id=None) -> tuple[str, list[dict]]:
    """Bind every numeric occurrence to a typed fact, then render the Python display.

    Unclear prose fails closed with a field path; Gemini can repair with an explicit
    fact reference. A flat set of values is never used to justify a numeric claim.
    """
    text = re.sub(r"\bTop(?=\d)", "Top ", text, flags=re.I)
    facts = context["verified_facts"]
    references = []
    replacements = []
    covered = []
    for match in re.finditer(_REFERENCE, text):
        key = _reference_key(match[1], facts)
        fact = facts.get(key)
        if fact is None:
            _fail(path, "unknown_fact_reference")
        _check_reference(text, match.start(), match.end(), path, city_id, context, key)
        references.append({"field_path": path, "fact_id": key})
        end = match.end()
        if fact["kind"] in {"percentage", "percentage_points"}:
            unit = re.match(r"\s*(?:điểm\s+(?:phần\s+trăm|%)|đpt|%|phần\s+trăm)", text[end:], re.I)
            if unit:
                end += unit.end()
        replacements.append((match.start(), end, fact["display"]))
        covered.append((match.start(), end))
    # Digits in trusted place names or standard chemical notation are not statistics.
    for city in context["representative_cities"]:
        if re.search(r"\d", city["city_name"]):
            covered.extend((m.start(), m.end()) for m in re.finditer(re.escape(city["city_name"]), text, re.I))
    covered.extend((m.start(), m.end()) for m in re.finditer(r"\b(?:t?CO[2₂]e?|CH[4₄]|N[2₂]O)\b", text, re.I))
    # B2B is the business-model term used in REPORT_RULES, not a numeric claim.
    # Match the complete term so embedded digits in other identifiers still fail.
    covered.extend((m.start(), m.end()) for m in re.finditer(r"\bB2B\b", text, re.I))
    # "Cụm 0, 1 và 2" is a list of labels, not the decimal 0.1 or a city count.
    for group in re.finditer(r"\b(?:các\s+)?(?:cụm|cum|clusters?)\s+(\d+(?:\s*(?:,|/|và)\s*\d+)+)\b(?!\s*%)", text, re.I):
        for label in re.finditer(r"\d+", group[1]):
            cid = int(label[0])
            if cid not in {0, 1, 2}:
                observed = label[0] if len(label[0]) <= 24 else "<redacted-number>"
                raise FactValidationError(field_path=path, rule="invalid_cluster_id", observed=observed, expected=[0, 1, 2])
            start, end = group.start(1) + label.start(), group.start(1) + label.end()
            covered.append((start, end))
            references.append({"field_path": path, "fact_id": f"model.cluster_ids.{cid}"})
    # Ignore only actual list numbering; never ignore an arbitrary bare statistic.
    ordinals = {m.start(1) for m in re.finditer(r"(?:^|[\n;:])\s*([1-7])[.)]\s+", text)}
    for match in re.finditer(_TOKEN, text):
        if any(a <= match.start() < b for a, b in covered):
            continue
        if match.start() in ordinals:
            covered.append((match.start(), match.end()))
            continue
        key = _fact_in_context(text, match.start(), match.end(), path, city_id, context)
        if key == "@cluster_id":
            cluster_id, _ = _parse(match[0], "cluster_id")
            if cluster_id not in {Decimal(0), Decimal(1), Decimal(2)}:
                observed = str(cluster_id) if len(str(cluster_id)) <= 24 else "<redacted-number>"
                raise FactValidationError(field_path=path, rule="invalid_cluster_id", observed=observed, expected=[0, 1, 2])
            key = f"model.cluster_ids.{int(cluster_id)}"
        fact = facts.get(key)
        if fact is None:
            try:
                observed, _ = _parse(match[0], "number")
            except InvalidOperation:
                observed = None
            _fail(path, "ambiguous_or_unsupported_numeric_context", observed=observed)
        try:
            observed, precision = _parse(match[0], fact["kind"])
            expected = Decimal(str(fact["value"]))
            if fact["kind"] in {"count", "year", "cluster_id", "rank"}:
                valid = observed == expected
            else:
                unit = Decimal(10) ** -min(precision, 2)
                valid = observed.quantize(unit, rounding=ROUND_HALF_UP) == expected.quantize(unit, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            _fail(path, "invalid_number_format", key, fact)
        if not valid:
            _fail(path, "value_mismatch", key, fact, observed)
        end = match.end()
        if fact["kind"] in {"percentage", "percentage_points"}:
            unit = re.match(r"\s*(?:điểm\s+(?:phần\s+trăm|%)|đpt|%|phần\s+trăm)", text[end:], re.I)
            if unit:
                end += unit.end()
        replacements.append((match.start(), end, fact["display"]))
        covered.append((match.start(), end))
        references.append({"field_path": path, "fact_id": key})
    # No scientific notation, malformed separators or digits hidden in an unbound field name.
    remaining = text
    for start, end in sorted(covered, reverse=True):
        remaining = remaining[:start] + " " * (end - start) + remaining[end:]
    if re.search(r"\d|\{\{|\}\}", remaining):
        _fail(path, "unbound_numeric_or_fact_token")
    rendered = text
    for start, end, display in sorted(replacements, reverse=True):
        rendered = rendered[:start] + display + rendered[end:]
    return rendered, references
