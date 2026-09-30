"""
Suraksha Sathi - Mine Worker Safety Drill Voice Assistant
Built with LangChain + Groq (LLM) for answering, and a simple keyword-based
search (TF-IDF from scikit-learn) to find the right drill content for each
question. This avoids heavy AI libraries like torch, which some Windows
security settings (like Smart App Control) can block.

Run:
    1. cp .env.example .env   and put your real GROQ_API_KEY in .env
    2. pip install -r requirements.txt
    3. python app.py
"""

import os
import glob
from langdetect import detect, DetectorFactory
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from system_prompt import (
    SURAKSHA_SATHI_SYSTEM_PROMPT,
    EMERGENCY_TRIGGER_PHRASES,
    EMERGENCY_RESPONSE,
)

DetectorFactory.seed = 0  
load_dotenv()  

DRILL_DATA_DIR = "drill_data"


GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


RELEVANCE_SCORE_THRESHOLD = 0.12


CURRENT_DRILL_NAME = {
    "en": "the safety drill",
    "hi": "सुरक्षा ड्रिल",
}


#making keyword search index data ka
def build_or_load_vectorstore():
    """Reads every .txt file in drill_data/, splits each into paragraph
    sized chunks, and builds a TF-IDF search index over them. TF-IDF is a
    classic, lightweight way to find which chunk of text best matches a
    question, based on shared important words - no heavy AI model needed."""
    chunks = []
    files_found = sorted(glob.glob(os.path.join(DRILL_DATA_DIR, "*.txt")))
    print(f"DEBUG: Found {len(files_found)} .txt files in {DRILL_DATA_DIR}/:")
    for f in files_found:
        print("   -", os.path.basename(f))

    for path in files_found:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks.extend(parts)

    print(f"DEBUG: Built {len(chunks)} searchable text chunks total.")

    if not chunks:
        raise RuntimeError(
            "No drill content found in drill_data/. Add your .txt files there first."
        )

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(chunks)

    return {"chunks": chunks, "vectorizer": vectorizer, "matrix": matrix}


def search_drills(retriever, query: str, k: int = 4):
    """Returns the top k most relevant chunks of drill text for the given
    question, each with a similarity score between 0 and 1 (higher = more
    relevant)."""
    query_vector = retriever["vectorizer"].transform([query])
    scores = cosine_similarity(query_vector, retriever["matrix"])[0]
    top_indices = scores.argsort()[::-1][:k]
    return [(retriever["chunks"][i], float(scores[i])) for i in top_indices]


#language worker using
def detect_language(text: str) -> str:
    """Returns 'hi' for Hindi, 'en' for everything else (including
    English and any language we don't have a Hindi-style reply for)."""
    try:
        code = detect(text)
    except Exception:
        return "en"
    if code == "hi":
        return "hi"
    return "en"

#real emrgngy nt
def is_real_emergency(text: str) -> bool:
    """If the message contains phrases like 'real fire' or 'someone is
    trapped', we skip the AI entirely and tell them to contact a
    supervisor right away."""
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in EMERGENCY_TRIGGER_PHRASES)


#AI model aur prompt
def build_chain(retriever):
    """Sets up the connection to Groq's AI model. `retriever` is just
    passed straight through unchanged, so the rest of the app can use it
    for searching drill text."""
    llm = ChatGroq(
        model=GROQ_MODEL,
        temperature=0.2,  # low = more accurate/consistent, less "creative"
        max_tokens=600,
        api_key=os.environ["GROQ_API_KEY"],
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SURAKSHA_SATHI_SYSTEM_PROMPT),
            ("human", "{question}"),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    return chain, retriever



# BOT kya answer karegaaa
def handle_message(user_text: str, chain, retriever) -> str:
    lang = detect_language(user_text)

    
    if is_real_emergency(user_text):
        return EMERGENCY_RESPONSE["hi" if lang == "hi" else "en"]


    results = search_drills(retriever, user_text, k=4)
    best_score = results[0][1] if results else 0
    print(f"DEBUG: best match score = {best_score:.4f} (threshold = {RELEVANCE_SCORE_THRESHOLD})")

    if best_score < RELEVANCE_SCORE_THRESHOLD:
        if lang == "hi":
            return (
                f"क्षमा करें, मैं केवल सुरक्षा ड्रिल के बारे में बता सकता/सकती हूँ। "
                f"कृपया {CURRENT_DRILL_NAME['hi']} के बारे में पूछें।"
            )
        return (
            f"Sorry, I can only help with the safety drills. "
            f"Please ask about {CURRENT_DRILL_NAME['en']}."
        )


    context = "\n\n---\n\n".join(text for text, score in results)
    return chain.invoke(
        {
            "question": user_text,
            "context": context,
            "current_drill": CURRENT_DRILL_NAME["en"],
        }
    )



# Simple typed chat loop for testing ke liye (voice_app.py adds speech)

def main():
    print("Building/loading knowledge base...")
    retriever = build_or_load_vectorstore()
    chain, retriever = build_chain(retriever)
    print("Suraksha Sathi is ready. Type 'quit' to exit.\n")

    while True:
        user_text = input("Worker: ").strip()
        if user_text.lower() in {"quit", "exit"}:
            break
        if not user_text:
            continue
        reply = handle_message(user_text, chain, retriever)
        print(f"Suraksha Sathi: {reply}\n")


if __name__ == "__main__":
    main()