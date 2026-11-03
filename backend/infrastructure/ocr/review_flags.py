def apply_review_flags(canonical, flags):
    """Retain OCR review evidence without replacing values or adding confidence."""
    lines = {line["lineNumber"]: line for line in canonical["lineItems"]}
    for flag in flags or []:
        if not isinstance(flag, dict):
            continue
        name = flag.get("field")
        if "lineNumber" in flag:
            target = lines.get(flag["lineNumber"], {}).get(name)
        else:
            target = canonical["fields"].get(name)
        if not isinstance(target, dict):
            continue  # Product-code flags remain in the full raw OCR result.
        target.setdefault("reviewEvidence", []).append(flag)
        if not target["unresolved"] and flag.get("code") == "LOW_CONFIDENCE":
            target["quality"] = "LOW_CONFIDENCE"
    return canonical
