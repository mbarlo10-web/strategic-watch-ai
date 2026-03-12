import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv


load_dotenv()


def _id_for_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return hashlib.sha256(os.urandom(16)).hexdigest()[:32]
    return hashlib.sha256(u.encode("utf-8")).hexdigest()[:32]


def _default_persist_dir() -> str:
    # Keep it inside the repo so it's portable.
    return os.path.join(os.getcwd(), "data", "chroma")


def get_collection(
    name: str = "strategic_watch_analyses",
    persist_dir: Optional[str] = None,
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not found. Please set it in your .env file.")

    persist_dir = persist_dir or _default_persist_dir()
    os.makedirs(persist_dir, exist_ok=True)

    client = chromadb.PersistentClient(path=persist_dir)
    embed_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )
    return client.get_or_create_collection(name=name, embedding_function=embed_fn)


def analysis_to_document(a: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    headline = (a.get("headline") or "").strip()
    summary = (a.get("summary") or "").strip()
    why = (a.get("why_it_matters") or "").strip()
    topic = (a.get("topic") or "").strip()
    event_type = (a.get("event_type") or "").strip()
    actors = a.get("key_actors") or []
    if isinstance(actors, str):
        actors = [actors]
    regions = a.get("country_or_region") or []
    if isinstance(regions, str):
        regions = [regions]

    doc = "\n".join(
        s
        for s in [
            headline,
            f"Theater: {topic}" if topic else "",
            f"Event: {event_type}" if event_type else "",
            f"Actors: {', '.join([str(x) for x in actors if x])}" if actors else "",
            f"Locations: {', '.join([str(x) for x in regions if x])}" if regions else "",
            f"Summary: {summary}" if summary else "",
            f"Why it matters: {why}" if why else "",
        ]
        if s
    )

    meta = {
        "url": a.get("url") or "",
        "source": a.get("source") or "",
        "topic": topic,
        "risk_level": (a.get("risk_level") or "").strip(),
        "confidence": (a.get("confidence") or "").strip(),
        "published_at": a.get("published_at") or "",
        "event_type": event_type,
    }
    return doc, meta


def upsert_analyses(analyses: List[Dict[str, Any]]) -> int:
    if not analyses:
        return 0
    col = get_collection()

    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []

    for a in analyses:
        doc, meta = analysis_to_document(a)
        if not doc.strip():
            continue
        ids.append(_id_for_url(meta.get("url", "")))
        docs.append(doc)
        metas.append(meta)

    if not ids:
        return 0

    col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def query_analyses(
    query: str,
    n_results: int = 5,
) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    col = get_collection()
    res = col.query(query_texts=[q], n_results=n_results)

    out: List[Dict[str, Any]] = []
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    for i in range(len(ids)):
        out.append(
            {
                "id": ids[i],
                "distance": dists[i] if i < len(dists) else None,
                "document": docs[i] if i < len(docs) else "",
                **(metas[i] if i < len(metas) and metas[i] else {}),
            }
        )
    return out

