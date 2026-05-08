import streamlit as st
import os
import json
import re
from groq import Groq
from docx import Document

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI জ্ঞানভাণ্ডার",
    page_icon="📚",
    layout="wide"
)

# ── Config ────────────────────────────────────────────────────────────────────
KB_FILE = "knowledge_base.json"
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

# ── Knowledge Base ────────────────────────────────────────────────────────────
def load_kb():
    if os.path.exists(KB_FILE):
        with open(KB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_kb(data):
    with open(KB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── DOCX Parser ───────────────────────────────────────────────────────────────
def parse_docx(file_bytes, book_name):
    import io
    doc = Document(io.BytesIO(file_bytes))
    chunks = []
    current_topic = "সাধারণ"
    current_cq_num = None
    current_cq_text = []
    current_parts = {}
    current_part = None

    def save_cq():
        if current_cq_num is not None and current_cq_text:
            full_text = " ".join(current_cq_text)
            chunks.append({
                "book": book_name,
                "topic": current_topic,
                "cq_num": current_cq_num,
                "text": full_text,
                "parts": dict(current_parts),
                "searchable": f"{book_name} {current_topic} {full_text} " + " ".join(current_parts.values())
            })

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        topic_match = re.search(r'Topic\s*[-–]?\s*(\d+)', text, re.IGNORECASE)
        if topic_match:
            save_cq()
            current_topic = f"Topic-{topic_match.group(1)}"
            current_cq_num = None
            current_cq_text = []
            current_parts = {}
            current_part = None
            continue

        cq_match = re.match(r'^([১২৩৪৫৬৭৮৯০1-9]\d*)[।.]', text)
        if cq_match:
            save_cq()
            current_cq_num = cq_match.group(1)
            current_cq_text = [text]
            current_parts = {}
            current_part = None
            continue

        part_match = re.match(r'^([কখগঘ])[।.]\s*(.*)', text)
        if part_match:
            current_part = part_match.group(1)
            current_parts[current_part] = part_match.group(2)
            if current_cq_text:
                current_cq_text.append(text)
            continue

        if current_cq_num:
            if current_part and current_part in current_parts:
                current_parts[current_part] += " " + text
            current_cq_text.append(text)

    save_cq()
    return chunks

# ── Search ────────────────────────────────────────────────────────────────────
def search(query, kb, top_k=5):
    if not kb:
        return []
    query_words = set(re.findall(r'\w+', query.lower()))
    scored = []
    for chunk in kb:
        words = set(re.findall(r'\w+', chunk.get("searchable", "").lower()))
        overlap = len(query_words & words)
        if overlap > 0:
            scored.append((overlap, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]

# ── Groq Answer ───────────────────────────────────────────────────────────────
def get_answer(query, results):
    if not GROQ_API_KEY:
        return "⚠️ Groq API key নেই। Streamlit Secrets-এ GROQ_API_KEY যোগ করুন।"
    if not results:
        return "❌ এই বিষয়ে কোনো তথ্য পাওয়া যায়নি।"

    context_parts = []
    for i, r in enumerate(results, 1):
        parts_text = ""
        if r.get("parts"):
            parts_text = "\n" + "\n".join([f"   {k}. {v}" for k, v in r["parts"].items()])
        context_parts.append(
            f"[{i}] বই: {r['book']} | {r['topic']} | CQ: {r['cq_num']}\n"
            f"উদ্দীপক: {r['text'][:400]}{parts_text}"
        )

    prompt = f"""আপনি একটি স্মার্ট নলেজ রিট্রিভাল সিস্টেম। নিচের তথ্যসূত্র থেকে প্রশ্নের উত্তর দিন।

নিয়ম:
- বাংলায় উত্তর দিন
- প্রতিটি তথ্যের সাথে বইয়ের নাম, Topic নম্বর ও CQ নম্বর উল্লেখ করুন
- ক/খ/গ/ঘ প্রশ্ন জানতে চাইলে সেটা খুঁজে দিন
- তথ্য না থাকলে স্পষ্ট বলুন

তথ্যসূত্র:
{chr(10).join(context_parts)}

প্রশ্ন: {query}
উত্তর:"""

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024
    )
    return response.choices[0].message.content

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📚 AI জ্ঞানভাণ্ডার")
st.caption("Topic ও CQ নম্বর সহ স্মার্ট সার্চ")

kb = load_kb()
books = sorted(set(c["book"] for c in kb)) if kb else []

# Sidebar
with st.sidebar:
    st.header("📊 ডেটাবেজ তথ্য")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("মোট বই", len(books))
    with col2:
        st.metric("মোট CQ", len(kb))

    if books:
        st.divider()
        st.subheader("বইয়ের তালিকা")
        for b in books:
            count = sum(1 for c in kb if c["book"] == b)
            st.markdown(f"📖 **{b}** ({count} CQ)")

    st.divider()
    st.subheader("📤 বই যোগ করুন")
    uploaded_file = st.file_uploader("DOCX ফাইল আপলোড করুন", type=["docx"])
    book_name_input = st.text_input("বইয়ের নাম (ঐচ্ছিক)")

    if uploaded_file and st.button("যোগ করুন", type="primary"):
        book_name = book_name_input or uploaded_file.name.replace(".docx", "")
        with st.spinner(f"প্রসেস করছি..."):
            file_bytes = uploaded_file.read()
            new_chunks = parse_docx(file_bytes, book_name)
            kb_data = load_kb()
            kb_data = [c for c in kb_data if c["book"] != book_name]
            kb_data.extend(new_chunks)
            save_kb(kb_data)
        st.success(f"✅ {len(new_chunks)}টি CQ যোগ হয়েছে!")
        st.rerun()

# Main Search
st.divider()
query = st.text_input(
    "🔍 প্রশ্ন লিখুন",
    placeholder="যেমন: স্লাইড ক্যালিপার্স দিয়ে দৈর্ঘ্য নির্ণয়, অথবা Topic 2 এর CQ গুলো কী?",
    label_visibility="collapsed"
)

if query:
    if not kb:
        st.warning("⚠️ ডেটাবেজ খালি! বাম দিক থেকে বই যোগ করুন।")
    else:
        with st.spinner("🔍 খোঁজা হচ্ছে..."):
            results = search(query, kb, top_k=5)
            answer = get_answer(query, results)

        st.subheader("📝 উত্তর")
        st.markdown(answer)

        if results:
            st.divider()
            st.subheader(f"📄 রেফারেন্স ({len(results)}টি উৎস)")
            for i, r in enumerate(results, 1):
                with st.expander(f"[{i}] 📖 {r['book']} | {r['topic']} | CQ {r['cq_num']}"):
                    st.markdown(f"**উদ্দীপক:** {r['text'][:300]}…")
                    if r.get("parts"):
                        st.markdown("**প্রশ্নসমূহ:**")
                        for k, v in r["parts"].items():
                            st.markdown(f"**{k}.** {v}")
else:
    if not kb:
        st.info("👈 বাম দিক থেকে DOCX ফাইল আপলোড করে শুরু করুন।")
    else:
        st.info("উপরে প্রশ্ন লিখুন — সব বই থেকে Topic ও CQ নম্বর সহ উত্তর পাবেন।")
