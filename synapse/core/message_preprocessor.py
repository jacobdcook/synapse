"""Preprocess long user messages so the model sees the question first."""
LONG_MESSAGE_THRESHOLD = 3000
CONTEXT_CAP = 6000

def preprocess_long_message(content, threshold=None):
    """Restructure long messages so the question appears first.
    If content is None, empty, or <= threshold chars, return unchanged.
    """
    if content is None:
        return ""
    if not isinstance(content, str):
        content = str(content)
    threshold = threshold if threshold is not None else LONG_MESSAGE_THRESHOLD
    if len(content) <= threshold:
        return content
    tail = content[-500:].strip()
    question = None
    for sep in ["\n\n", "\n"]:
        parts = tail.rsplit(sep, 1)
        if len(parts) == 2:
            candidate = parts[-1].strip()
            if "?" in candidate or len(candidate) < 300:
                question = candidate
                break
    if not question:
        question = tail[-400:] if len(tail) > 400 else tail
    ctx = content[:CONTEXT_CAP] + ("..." if len(content) > CONTEXT_CAP else "")
    return f"USER QUESTION:\n{question}\n\nCONTEXT (for reference):\n{ctx}"
