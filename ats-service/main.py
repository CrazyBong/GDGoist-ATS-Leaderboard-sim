from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
import io
import re
import traceback

from pdfminer.high_level import extract_text as extract_text_from_pdf
import docx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# ==============================
# ATS with TF-IDF (SBERT disabled on Windows)
# ==============================
import nltk
from nltk.corpus import stopwords

app = FastAPI(title="ATS Service with TF-IDF")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize SBERT model and stopwords
try:
    # Download stopwords if not already present
    nltk.download('stopwords', quiet=True)
    STOP_WORDS = set(stopwords.words('english'))
    
    # Load SBERT model - disabled on Windows due to Numpy compatibility issues
    print("SBERT model loading disabled on Windows (Numpy compatibility)")
    sbert_model = None
    SBERT_ENABLED = False
except Exception as e:
    print(f"Warning: Could not initialize SBERT model: {e}")
    print("Falling back to TF-IDF similarity")
    STOP_WORDS = set()
    sbert_model = None
    SBERT_ENABLED = False


@app.get('/health')
def health():
    return {
        'status': 'ok',
        'sbert_enabled': SBERT_ENABLED,
        'model': 'all-MiniLM-L6-v2' if SBERT_ENABLED else 'TF-IDF'
    }


# ==============================
# Enhanced Text Processing with SBERT
# ==============================

def clean_text(text: str) -> str:
    """Enhanced text cleaning function for SBERT processing"""
    if not text:
        return ""
    
    text = text.lower()
    text = re.sub(r'[^a-z\s]', ' ', text)      # Remove special characters
    text = re.sub(r'\s+', ' ', text).strip()   # Remove extra spaces
    
    if STOP_WORDS:
        text = " ".join(word for word in text.split() if word not in STOP_WORDS)
    
    return text


def ats_similarity_score_sbert(resume_text: str, jd_text: str) -> float:
    """
    Enhanced ATS similarity scoring using SBERT
    Returns similarity score between 0 and 1
    """
    if not SBERT_ENABLED or not sbert_model:
        # Fallback to TF-IDF
        return compute_relevance_tfidf(resume_text, jd_text)
    
    try:
        # Clean inputs
        resume_clean = clean_text(resume_text)
        jd_clean = clean_text(jd_text)
        
        if not resume_clean or not jd_clean:
            return 0.0
        
        # Generate embeddings
        resume_embedding = sbert_model.encode([resume_clean])
        jd_embedding = sbert_model.encode([jd_clean])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(resume_embedding, jd_embedding)[0][0]
        
        # Ensure similarity is between 0 and 1
        similarity = max(0.0, min(1.0, float(similarity)))
        
        return similarity
        
    except Exception as e:
        print(f"SBERT similarity calculation failed: {e}")
        # Fallback to TF-IDF
        return compute_relevance_tfidf(resume_text, jd_text)


def compute_relevance_tfidf(resume_text: str, job_text: str) -> float:
    """Original TF-IDF based relevance computation (fallback)"""
    try:
        vect = TfidfVectorizer(stop_words='english')
        tfidf = vect.fit_transform([job_text or '', resume_text or ''])
        if tfidf.shape[0] < 2:
            return 0.0
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0, 0]
        if np.isnan(sim):
            return 0.0
        return float(sim)
    except Exception:
        return 0.0


def extract_text_from_docx_bytes(data: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(data))
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception:
        raise


def safe_extract_text(file_bytes: bytes, filename: str) -> (str, list):
    errors = []
    text = ''
    lower = filename.lower()
    try:
        if lower.endswith('.pdf'):
            # pdfminer expects a file-like; write to BytesIO
            try:
                text = extract_text_from_pdf(io.BytesIO(file_bytes))
            except Exception as e:
                errors.append(f'PDF parsing error: {str(e)}')
        elif lower.endswith('.docx') or lower.endswith('.doc'):
            try:
                text = extract_text_from_docx_bytes(file_bytes)
            except Exception as e:
                errors.append(f'DOCX parsing error: {str(e)}')
        else:
            errors.append('Unsupported file extension')
    except Exception as e:
        errors.append(f'Unexpected parsing error: {str(e)}')
    text = text or ''
    return text, errors


def find_section(text: str, section_names) -> Optional[str]:
    # naive section detection: look for lines starting with section name
    lines = text.splitlines()
    idx = None
    for i, ln in enumerate(lines):
        l = ln.strip().lower()
        for name in section_names:
            if l.startswith(name):
                idx = i
                break
        if idx is not None:
            break
    if idx is None:
        return None
    # collect lines until next blank line or next header (all caps or ends with ':')
    collected = []
    for ln in lines[idx + 1:]:
        if not ln.strip():
            if collected:
                break
            else:
                continue
        # simple header heuristic
        if re.match(r'^[A-Z\s]{3,}$', ln.strip()) or ln.strip().endswith(':'):
            break
        collected.append(ln.strip())
    return '\n'.join(collected).strip() if collected else None


def extract_contact_info(text: str) -> Dict[str, Optional[str]]:
    email_re = re.compile(r'[\w\.-]+@[\w\.-]+')
    phone_re = re.compile(r'(\+?\d[\d\s\-()]{6,}\d)')
    email = email_re.search(text)
    phone = phone_re.search(text)
    return {'email': email.group(0) if email else None, 'phone': phone.group(0) if phone else None}


def extract_skills_from_section(section_text: Optional[str]) -> list:
    if not section_text:
        return []
    # split by commas or newlines and filter short tokens
    tokens = re.split(r'[\n,;•\u2022]+', section_text)
    skills = []
    for t in tokens:
        s = t.strip()
        if 2 <= len(s) <= 60:
            skills.append(s)
    return skills


def detect_formatting_risks(text: str) -> list:
    risks = []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        risks.append('Empty or unreadable document')
        return risks
    long_line_ratio = sum(1 for ln in lines if len(ln) > 300) / max(1, len(lines))
    if long_line_ratio > 0.2:
        risks.append('Many very long lines (possible formatting/encoding issues)')
    all_caps_ratio = sum(1 for ln in lines if ln.strip().isupper()) / max(1, len(lines))
    if all_caps_ratio > 0.1:
        risks.append('Excessive ALL-CAPS lines')
    return risks


def compute_heuristics(text: str, parsed_sections: dict, parsing_errors: list) -> (float, list, dict):
    # Heuristic scoring (0-50). We'll return score and feedback items and breakdown
    score = 0.0
    feedback = []
    breakdown = {'education': 0, 'experience': 0, 'skills': 0, 'contact': 0, 'formattingPenalty': 0, 'parsingPenalty': 0}

    # Education
    if parsed_sections.get('education'):
        breakdown['education'] = 12
        score += 12
    else:
        feedback.append('Missing Education section')

    # Experience
    if parsed_sections.get('experience'):
        breakdown['experience'] = 18
        score += 18
    else:
        feedback.append('Missing Experience section')

    # Skills
    if parsed_sections.get('skills'):
        breakdown['skills'] = 10
        score += 10
    else:
        feedback.append('Missing Skills section')

    # Contact
    contact = extract_contact_info(text)
    if contact.get('email') or contact.get('phone'):
        breakdown['contact'] = 10
        score += 10
    else:
        feedback.append('Missing or invalid contact information')

    # Formatting risks
    risks = detect_formatting_risks(text)
    if risks:
        breakdown['formattingPenalty'] = -10
        score -= 10
        feedback.extend(['Formatting risk: ' + r for r in risks])

    # Parsing errors penalty
    if parsing_errors:
        breakdown['parsingPenalty'] = -20
        score -= 20
        feedback.append('Parsing issues detected: ' + '; '.join(parsing_errors))

    # Clamp
    score = max(0.0, min(50.0, score))
    return score, feedback, breakdown


def compute_relevance(resume_text: str, job_text: str) -> float:
    """
    Enhanced relevance computation using SBERT or TF-IDF fallback
    """
    return ats_similarity_score_sbert(resume_text, job_text)


def normalize_score(heuristics_score: float, relevance: Optional[float]) -> (float, dict):
    # heuristics_score in [0,50]
    # relevance in [0,1] or None
    if relevance is None or relevance == 0.0:
        total = heuristics_score * 2.0
        breakdown = {'heuristics': heuristics_score * 2.0, 'relevance': 0.0}
    else:
        relevance_component = relevance * 50.0
        total = heuristics_score + relevance_component
        breakdown = {'heuristics': heuristics_score, 'relevance': relevance_component}
    total = max(0.0, min(100.0, total))
    return round(total, 2), breakdown


def generate_white_box_feedback(feedback_items: list, relevance: float, parsed_sections: dict, contact: dict, breakdown_components: dict) -> list:
    fb = []
    fb.extend(feedback_items)
    
    # Add relevance interpretation with SBERT context
    if relevance is not None:
        similarity_method = "SBERT" if SBERT_ENABLED else "TF-IDF"
        fb.append(f'Relevance ({similarity_method}) = {round(relevance,3)}')
        
        if relevance < 0.3:
            fb.append('Low semantic match to job description - consider adding more relevant keywords and skills')
        elif relevance < 0.6:
            fb.append('Moderate semantic match to job description - good alignment with some improvement opportunities')
        else:
            fb.append('Excellent semantic match to job description - strong alignment with requirements')

    # Section summary
    for sec in ['education', 'experience', 'skills']:
        if parsed_sections.get(sec):
            fb.append(f'{sec.title()} section detected')
        else:
            fb.append(f'{sec.title()} section NOT detected - consider adding this section')

    if contact.get('email'):
        fb.append(f"Email found: {contact.get('email')}")
    else:
        fb.append('Email not found - add professional email address')
    if contact.get('phone'):
        fb.append(f"Phone found: {contact.get('phone')}")
    else:
        fb.append('Phone not found - add contact phone number')

    # Append breakdown summary
    fb.append('Score breakdown: ' + ', '.join([f"{k}:{v}" for k, v in breakdown_components.items()]))
    
    # Add SBERT-specific recommendations
    if SBERT_ENABLED and relevance is not None:
        if relevance < 0.4:
            fb.append('Recommendation: Use more specific technical terms and industry keywords from the job description')
            fb.append('Recommendation: Align your experience descriptions with the job requirements more closely')
    
    return fb


@app.post('/parse')
async def parse_resume(file: UploadFile = File(...), job_description: Optional[str] = Form(None)) -> Dict[str, Any]:
    """
    Enhanced resume parsing and scoring with SBERT-based semantic matching.
    Parse and score a resume file (PDF or DOCX).
    Optional `job_description` form field may be provided to compute semantic relevance using SBERT.
    Returns rawText, parsed sections, parsingErrors, atsScore (0-100), breakdown, and feedback.
    """
    try:
        data = await file.read()
        raw_text, parsing_errors = safe_extract_text(data, file.filename)

        # Extract sections
        parsed = {}
        parsed['skills'] = extract_skills_from_section(find_section(raw_text, ['skills', 'technical skills', 'skills & technologies']))
        parsed['education'] = find_section(raw_text, ['education', 'academic', 'qualifications'])
        parsed['experience'] = find_section(raw_text, ['experience', 'work experience', 'professional experience', 'employment'])

        heur_score, heur_feedback, heur_breakdown = compute_heuristics(raw_text, parsed, parsing_errors)

        relevance = None
        if job_description:
            relevance = compute_relevance(raw_text, job_description)

        final_score, norm_breakdown = normalize_score(heur_score, relevance)

        contact = extract_contact_info(raw_text)
        feedback = generate_white_box_feedback(heur_feedback, relevance if relevance is not None else 0.0, parsed, contact, {**heur_breakdown, **norm_breakdown})

        result = {
            'rawText': raw_text,
            'parsedSkills': parsed['skills'],
            'parsingErrors': parsing_errors,
            'atsScore': final_score,
            'breakdown': {**heur_breakdown, **norm_breakdown},
            'feedback': feedback,
            'contact': contact,
            'similarity_method': 'SBERT' if SBERT_ENABLED else 'TF-IDF',
            'model_info': {
                'sbert_enabled': SBERT_ENABLED,
                'model_name': 'all-MiniLM-L6-v2' if SBERT_ENABLED else 'TF-IDF'
            }
        }
        return result
    except Exception as e:
        traceback.print_exc()
        return {'error': 'Failed to parse', 'detail': str(e)}


@app.post('/semantic-similarity')
async def semantic_similarity(text1: str = Form(...), text2: str = Form(...)) -> Dict[str, Any]:
    """
    Calculate semantic similarity between two texts using SBERT or TF-IDF.
    Returns similarity score between 0 and 1.
    """
    try:
        similarity_score = ats_similarity_score_sbert(text1, text2)
        
        return {
            'similarity': similarity_score,
            'method': 'SBERT' if SBERT_ENABLED else 'TF-IDF',
            'model': 'all-MiniLM-L6-v2' if SBERT_ENABLED else 'TF-IDF'
        }
    except Exception as e:
        traceback.print_exc()
        return {'error': 'Failed to calculate similarity', 'detail': str(e), 'similarity': 0.0}


@app.post('/similarity')
async def calculate_similarity(resume_text: str = Form(...), job_description: str = Form(...)) -> Dict[str, Any]:
    """
    Direct similarity calculation endpoint using SBERT.
    Useful for testing and debugging similarity calculations.
    """
    try:
        similarity_score = ats_similarity_score_sbert(resume_text, job_description)
        
        return {
            'similarity_score': similarity_score,
            'method': 'SBERT' if SBERT_ENABLED else 'TF-IDF',
            'model': 'all-MiniLM-L6-v2' if SBERT_ENABLED else 'TF-IDF',
            'resume_length': len(resume_text),
            'jd_length': len(job_description)
        }
    except Exception as e:
        traceback.print_exc()
        return {'error': 'Failed to calculate similarity', 'detail': str(e)}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
