"""
F1 Agent built with LangChain + LangGraph.

Graph Flow:
  1. receive_question  → Clean and normalize input.
  2. rephrase_question → Rewrite query using chat history.
  3. validate_intent   → Ensure the query is F1-related.
  4. retrieve_context  → Fetch relevant docs from PGVector.
  5. generate_answer   → Generate grounded response.
  6. reject_question   → Out-of-scope or missing info fallback.

Anti-hallucination measures:
  ① Minimum similarity threshold in vector search — low-score chunks never reach the LLM
  ② Answer prompt forces explicit quote extraction before answering (chain-of-thought)
  ③ Post-generation validation — long answers with no topic overlap with context are flagged
"""
import logging
import re
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from src.backend.config.settings import get_settings
from src.backend.vectorstore.pg_vector import similarity_search

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── State ───────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    question: str
    normalized_question: str
    standalone_question: str
    chat_history: list[BaseMessage]
    is_f1_related: bool
    retrieved_docs: list[tuple]
    context_text: str
    source_names: list[str]
    has_sufficient_context: bool
    answer: str


# ─── LLM ─────────────────────────────────────────────────────────────────────

def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        num_predict=20,
    )


def _get_rephrase_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        num_predict=60,
    )


def _get_answer_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        num_predict=1024,
    )


# ─── System prompts ──────────────────────────────────────────────────────────

SYSTEM_PROMPT_INTENT = """You are a binary intent classifier for a Formula 1 assistant.
Your only job is to decide if a question is related to Formula 1 or not.
Reply with a single word: YES or NO. Nothing else — no punctuation, no explanation.

YES — question is about any of these:
- F1 drivers (past or present): Hamilton, Verstappen, Senna, Schumacher, Alonso, etc.
- F1 teams / constructors: Ferrari, Mercedes, Red Bull, McLaren, Williams, etc.
- F1 races, grand prix, circuits: Monaco, Silverstone, Monza, Spa, etc.
- Championships, seasons, standings, points
- F1 regulations, technical rules, DRS, pit stops, safety car
- F1 history, records, statistics
- General questions about what Formula 1 is
- F1 business, finances, budgets, revenue, costs, sponsorships, cost cap
- F1 technology, car design, engines, aerodynamics, tyres
- F1 broadcasting, media rights, viewership
- F1 governance, FIA, regulations, Concorde Agreement


NO — question is about anything else:
- Other sports (football, basketball, MotoGP, NASCAR, etc.)
- Politics, science, cooking, weather, technology, etc.

Examples:
Q: "What is Formula One?" → YES
Q: "When was F1 founded?" → YES
Q: "Who is Lewis Hamilton?" → YES
Q: "How does DRS work?" → YES
Q: "What is the fastest lap record at Monza?" → YES
Q: "Who won the 2021 Abu Dhabi Grand Prix?" → YES
Q: "What is the weather today?" → NO
Q: "Who is the president of the US?" → NO
Q: "How do I cook pasta?" → NO
Q: "Tell me about MotoGP" → NO

User question: {question}"""

SYSTEM_PROMPT_REPHRASE = """Rewrite the user's question as a standalone question using the conversation history.
Output ONLY the rewritten question. No explanations, no answers, no extra text.
If the question is already standalone, output it exactly as-is.

History: [Q: "Who is Verstappen?", A: "Max Verstappen is a Dutch F1 driver"]
Question: "How many championships does he have?"
Output: How many championships does Max Verstappen have?

History: [Q: "Tell me about Ferrari", A: "Ferrari is an Italian F1 team"]
Question: "When did they last win?"
Output: When did Ferrari last win a constructor championship?

History: [Q: "What is F1?", A: "Formula 1 is a motorsport series"]
Question: "Who is Lewis Hamilton?"
Output: Who is Lewis Hamilton?"""

SYSTEM_PROMPT_ANSWER = """You are an F1 analyst. Use ONLY the context below to answer.

Follow this format EXACTLY. Do not use any other format or labels:

EVIDENCE: [copy the exact sentence(s) from the context that answer the question. If none found, write the word: none]
ANSWER: [your answer based only on the evidence above. If evidence is none, write: I don't have that information in my knowledge base.]

Rules:
- NEVER use knowledge from your training.
- NEVER add information not present in the EVIDENCE.
- NEVER use labels like STEP 1, STEP 2, or any other format.
- ANSWER must be in the same language as the question.
- Do not mention filenames, scores, or UUIDs.

Example 1:
Question: Why was traction control banned in 1994?
EVIDENCE: "The FIA, due to complaints that technology was determining races' outcomes more than driver skill, banned many such aids for the 1994 season."
ANSWER: Traction control was banned in 1994 because the FIA responded to complaints that technology was determining race outcomes more than driver skill.

Example 2:
Question: How many titles did Kimi Raikkonen win?
EVIDENCE: none
ANSWER: I don't have that information in my knowledge base.

CONTEXT:
{context}"""

# ─── Hallucination guard ─────────────────────────────────────────────────────

_STOP_WORDS = {
    "what", "does", "the", "how", "who", "is", "are", "was", "were",
    "did", "when", "where", "which", "have", "has", "been", "will",
    "about", "tell", "me", "in", "of", "a", "an", "and", "or", "for",
    "formula", "one", "f1", "role", "purpose", "explain", "describe", "difference", "between",
    "main", "what", "give", "make", "does", "work",
}

_REFUSAL_PHRASES = [
    "i don't have that information",
    "no tengo esa información",
    "not in my knowledge base",
    "no está en mi base de conocimiento",
]

def _extract_final_answer(raw: str) -> str:
    match = re.search(r"ANSWER\s*:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        answer = match.group(1).strip()
        answer = re.split(r"\nEVIDENCE\s*:", answer, flags=re.IGNORECASE)[0].strip()
        if answer:
            return answer

    cleaned = re.sub(
        r"EVIDENCE\s*:.*?(?=\n[A-Z]|\Z)",
        "",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    if cleaned:
        return cleaned

    return raw.strip()

def _is_grounded(answer: str, question: str, context: str) -> bool:
    if len(answer) < 200:
        return True
    if any(phrase in answer.lower() for phrase in _REFUSAL_PHRASES):
        return True

    topic_words = [
        word.strip("?.,!") for word in question.lower().split()
        if len(word) > 4 and word.lower() not in _STOP_WORDS
    ]

    if not topic_words:
        return True

    context_lower = context.lower()
    matches = [word for word in topic_words if word in context_lower]
    match_ratio = len(matches) / len(topic_words)

    logger.debug(
        "Grounding check: %d/%d topic words found in context (%.0f%%): %s",
        len(matches),
        len(topic_words),
        match_ratio * 100,
        topic_words,
    )

    return match_ratio >= 0.30


# ─── Nodes ───────────────────────────────────────────────────────────────────

def node_receive_question(state: AgentState) -> AgentState:
    q = state["question"].strip()
    state["normalized_question"] = q.lower()
    logger.info("[Node 1] Question received: %s", q)
    return state


def node_rephrase_question(state: AgentState) -> AgentState:
    chat_history = state.get("chat_history", [])

    if not chat_history:
        state["standalone_question"] = state["question"]
        logger.info("[Node 2] No history, using original question")
        return state

    llm = _get_rephrase_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_REPHRASE),
        MessagesPlaceholder("chat_history"),
        ("human", "Question: {input}\nOutput:"),
    ])
    chain = prompt | llm | StrOutputParser()
    standalone = chain.invoke({
        "input": state["question"],
        "chat_history": chat_history,
    })
    standalone = standalone.strip().splitlines()[0].strip()
    state["standalone_question"] = standalone
    logger.info("[Node 2] Rephrased: %s", state["standalone_question"])
    return state


def node_validate_intent(state: AgentState) -> AgentState:
    # Validate using the rephrased standalone question so context is preserved
    question_to_check = state.get("standalone_question") or state["normalized_question"]
    llm = _get_llm()
    messages = [
        HumanMessage(content=SYSTEM_PROMPT_INTENT.format(
            question=question_to_check
        )),
    ]
    response = llm.invoke(messages)
    answer_text = response.content.strip().upper()
    is_f1 = "YES" in answer_text[:50]
    state["is_f1_related"] = is_f1
    logger.info("[Node 3] Is F1 related? %s (raw: %s)", is_f1, answer_text)
    return state


def node_retrieve_context(state: AgentState) -> AgentState:
    original_query = state.get("standalone_question") or state["question"]

    # Primera búsqueda sin expansión
    docs_with_scores = similarity_search(query=original_query, k=10)

    best_score = docs_with_scores[0][1] if docs_with_scores else 0
    logger.info("[Node 4] Best score without expansion: %.4f", best_score)

    # Solo expandir si el mejor score es bajo
    if best_score < 0.65:
        llm = _get_rephrase_llm()
        keyword_response = llm.invoke([HumanMessage(
            content=f"""Write 5 short phrases in English that would appear in a document answering this question.
Always include the exact name of any person or team mentioned in the question.
Only the phrases, no explanation, no numbers.
Question: {original_query}
Example output for 'Who is Lewis Hamilton?': Lewis Hamilton driver, Hamilton Mercedes, Hamilton championships, British F1 driver, Hamilton career"""
        )]).content.strip()

        logger.info("[Node 4] Score too low, expanding query. Keywords: %s", keyword_response)
        query = f"{original_query} {keyword_response}"
        docs_with_scores = similarity_search(query=query, k=5)
    else:
        logger.info("[Node 4] Score sufficient, skipping expansion")

    state["retrieved_docs"] = docs_with_scores

    context_parts: list[str] = []
    sources: list[str] = []
    for doc, score in docs_with_scores:
        src = doc.metadata.get("source", "unknown")
        if src not in sources:
            sources.append(src)
        context_parts.append(f"[Score: {score:.2f}]\n{doc.page_content}")
        logger.info("[Node 4] Chunk (score=%.2f):\n%s", score, doc.page_content[:300])

    state["context_text"] = "\n\n---\n\n".join(context_parts)
    state["source_names"] = sources
    state["has_sufficient_context"] = len(docs_with_scores) > 0

    logger.info("[Node 4] Retrieved chunks: %d", len(docs_with_scores))
    return state


def node_generate_answer(state: AgentState) -> AgentState:
    llm = _get_answer_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_ANSWER),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    raw_output = chain.invoke({
        "input": state["question"],
        "context": state["context_text"],
        "chat_history": state.get("chat_history", []),
    })

    logger.debug("[Node 5] Raw model output:\n%s", raw_output)

    answer = _extract_final_answer(raw_output.strip())

    if not answer or answer.lower().strip() == "none":
        answer = "I don't have that information in my knowledge base."

    if not _is_grounded(answer, state["question"], state["context_text"]):
        logger.warning(
            "[Node 5] Hallucination detected — topic words not found in context. "
            "Original answer (%d chars) replaced with refusal.",
            len(answer),
        )
        answer = "I don't have that information in my knowledge base."

    state["answer"] = answer
    logger.info(
        "[Node 5] Answer generated (%d chars): %s",
        len(answer),
        answer[:100],
    )
    return state


def node_reject_question(state: AgentState) -> AgentState:
    if not state.get("is_f1_related", True):
        state["answer"] = (
            "This question is not related to Formula 1. "
            "I can only answer questions about F1: drivers, teams, circuits, "
            "seasons, races, and regulations."
        )
    else:
        state["answer"] = (
            "I don't have enough information in my knowledge base to answer that.\n\n"
            "You can expand it by uploading relevant documents "
            "(PDFs, articles, stats, etc.)."
        )
    state["has_sufficient_context"] = False
    logger.info("[Node 6] Question rejected")
    return state


# ─── Conditional edges ────────────────────────────────────────────────────────

def route_after_rephrase(state: AgentState) -> Literal["validate_intent"]:
    return "validate_intent"


def route_after_intent(state: AgentState) -> Literal["retrieve_context", "reject_question"]:
    return "retrieve_context" if state["is_f1_related"] else "reject_question"


def route_after_retrieval(state: AgentState) -> Literal["generate_answer", "reject_question"]:
    return "generate_answer" if state["has_sufficient_context"] else "reject_question"


# ─── Graph ───────────────────────────────────────────────────────────────────

def build_f1_agent():
    graph = StateGraph(AgentState)

    graph.add_node("receive_question", node_receive_question)
    graph.add_node("rephrase_question", node_rephrase_question)
    graph.add_node("validate_intent", node_validate_intent)
    graph.add_node("retrieve_context", node_retrieve_context)
    graph.add_node("generate_answer", node_generate_answer)
    graph.add_node("reject_question", node_reject_question)

    graph.add_edge(START, "receive_question")
    graph.add_edge("receive_question", "rephrase_question")
    graph.add_edge("rephrase_question", "validate_intent")

    graph.add_conditional_edges(
        "validate_intent",
        route_after_intent,
        {
            "retrieve_context": "retrieve_context",
            "reject_question": "reject_question",
        },
    )

    graph.add_conditional_edges(
        "retrieve_context",
        route_after_retrieval,
        {
            "generate_answer": "generate_answer",
            "reject_question": "reject_question",
        },
    )

    graph.add_edge("generate_answer", END)
    graph.add_edge("reject_question", END)

    return graph.compile()


# ─── Session management ──────────────────────────────────────────────────────

_session_store: dict[str, list[BaseMessage]] = {}
_agent = None
_MAX_HISTORY_MESSAGES = 10


def get_agent():
    global _agent
    if _agent is None:
        logger.info("Compiling F1 LangGraph agent...")
        _agent = build_f1_agent()
        logger.info("Agent compiled and ready.")
    return _agent


def get_session_history(session_id: str) -> list[BaseMessage]:
    if session_id not in _session_store:
        _session_store[session_id] = []
    return _session_store[session_id]


def delete_session(session_id: str) -> bool:
    if session_id in _session_store:
        del _session_store[session_id]
        return True
    return False


def run_agent(question: str, session_id: str = "default") -> dict:
    agent = get_agent()
    history = get_session_history(session_id)

    initial_state: AgentState = {
        "question": question,
        "normalized_question": "",
        "standalone_question": "",
        "chat_history": history,
        "is_f1_related": False,
        "retrieved_docs": [],
        "context_text": "",
        "source_names": [],
        "has_sufficient_context": False,
        "answer": "",
    }

    final_state: AgentState = agent.invoke(initial_state)

    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=final_state["answer"]))

    if len(history) > _MAX_HISTORY_MESSAGES:
        _session_store[session_id] = history[-_MAX_HISTORY_MESSAGES:]

    return {
        "answer": final_state["answer"],
        "sources": final_state["source_names"],
        "has_context": final_state["has_sufficient_context"],
    }