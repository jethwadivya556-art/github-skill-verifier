import html
import re
from collections import Counter

import requests
import streamlit as st

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

# Different names people use for the same skill
ALIASES = {
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "javascript": ["javascript", "js"],
    "node.js": ["node.js", "nodejs", "node"],
    "react.js": ["react.js", "react", "reactjs"],
    "tensorflow": ["tensorflow"],
    "machine learning": ["machine learning", "ml", "scikit-learn", "sklearn"],
    "deep learning": ["deep learning", "cnn", "tensorflow", "keras", "pytorch"],
}


# ---------------------------------------------------------------- GitHub data
def gh_get(url, token=None, **kwargs):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(url, headers=headers, timeout=10, **kwargs)


@st.cache_data(show_spinner=False, ttl=600)
def fetch_profile(username, token):
    resp = gh_get(f"{API}/users/{username}", token=token or None)
    return resp.json() if resp.status_code == 200 else {}


@st.cache_data(show_spinner=False, ttl=600)
def fetch_repos(username, include_forks, token):
    """Return (repos, error_message). Looks at up to 30 most recently pushed repos."""
    resp = gh_get(
        f"{API}/users/{username}/repos",
        token=token or None,
        params={"per_page": 100, "sort": "pushed"},
    )
    if resp.status_code == 404:
        return [], "GitHub user not found. Check the username."
    if resp.status_code == 403:
        return (
            [],
            "GitHub rate limit reached. Add a token below or try again in an hour.",
        )
    if resp.status_code != 200:
        return [], f"GitHub returned an error ({resp.status_code})."
    repos = resp.json()
    if not include_forks:
        repos = [r for r in repos if not r["fork"]]
    return repos[:30], ""


def fetch_requirements(username, repo, token=None):
    """Read requirements.txt from the repo (empty string if missing)."""
    url = f"{RAW}/{username}/{repo['name']}/{repo.get('default_branch', 'main')}/requirements.txt"
    try:
        resp = requests.get(url, timeout=5)
        return resp.text.lower() if resp.status_code == 200 else ""
    except requests.RequestException:
        return ""


def build_evidence(username, repos, token=None):
    """For every repo, collect text that can prove a skill (language, topics, description, libraries)."""
    evidence = []
    for repo in repos:
        parts = [
            repo["name"],
            repo.get("description") or "",
            repo.get("language") or "",
        ]
        parts += repo.get("topics", [])
        if repo.get("language") in (None, "Python", "Jupyter Notebook"):
            parts.append(fetch_requirements(username, repo, token))
        evidence.append({"repo": repo["name"], "text": " ".join(parts).lower()})
    return evidence


def find_skill(skill, evidence):
    """Return the repos whose evidence mentions this skill (whole-word match)."""
    key = skill.strip().lower()
    names = ALIASES.get(key) or next((v for v in ALIASES.values() if key in v), [key])
    found = []
    for item in evidence:
        for name in names:
            pattern = r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])"
            if re.search(pattern, item["text"]):
                found.append(item["repo"])
                break
    return found


# --------------------------------------------------------------------- Styling
CSS = """
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1.5rem; max-width: 820px;}
.hero {background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white;
       padding: 2rem 1.8rem; border-radius: 18px; margin-bottom: 1.2rem;
       box-shadow: 0 10px 30px rgba(79,70,229,0.25);}
.hero h1 {margin: 0; font-size: 2rem; color: white; padding: 0;}
.hero p {margin: .4rem 0 0 0; opacity: .92; font-size: 1.02rem;}
.card {background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.1rem 1.3rem;
       box-shadow: 0 2px 8px rgba(15,23,42,0.05); height: 100%;}
.ring {width: 120px; height: 120px; border-radius: 50%; margin: 0 auto;
       display: flex; align-items: center; justify-content: center;}
.ring-inner {width: 90px; height: 90px; border-radius: 50%; background: white;
             display: flex; align-items: center; justify-content: center;
             font-size: 1.6rem; font-weight: 700; color: #0f172a;}
.ring-label {text-align: center; margin-top: .6rem; color: #475569; font-size: .9rem;}
.profile {display: flex; align-items: center; gap: 1rem;}
.profile img {width: 72px; height: 72px; border-radius: 50%; border: 3px solid #e0e7ff;}
.profile .name {font-size: 1.25rem; font-weight: 700; color: #0f172a;}
.profile .user {color: #64748b; font-size: .92rem;}
.profile .bio {color: #334155; font-size: .93rem; margin-top: .3rem;}
.stats {display: flex; gap: 1.4rem; margin-top: .8rem;}
.stat b {display: block; font-size: 1.15rem; color: #4f46e5;}
.stat span {font-size: .8rem; color: #64748b;}
.section {font-size: 1.1rem; font-weight: 700; color: #0f172a; margin: 1.4rem 0 .6rem 0;}
.chip {display: inline-block; padding: .38rem .85rem; margin: 0 .4rem .5rem 0;
       border-radius: 999px; font-size: .9rem; font-weight: 600;}
.chip-ok {background: #dcfce7; color: #166534; border: 1px solid #bbf7d0;}
.chip-no {background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0;}
.note {color: #64748b; font-size: .85rem; margin-top: .4rem;}
div.stButton > button {width: 100%; border-radius: 12px; padding: .65rem 1rem; font-weight: 700;}
.footer {text-align: center; color: #94a3b8; font-size: .82rem; margin: 2rem 0 .5rem 0;}
</style>
"""


def card(inner):
    return f'<div class="card">{inner}</div>'


def ring_card(percent):
    inner = (
        f'<div class="ring" style="background: conic-gradient(#4f46e5 {percent}%, #e5e7eb 0);">'
        f'<div class="ring-inner">{percent}%</div></div>'
        '<div class="ring-label">Skills backed by code</div>'
    )
    return card(inner)


def profile_card(profile, username, repo_count):
    name = html.escape(profile.get("name") or username)
    bio = html.escape(profile.get("bio") or "")
    avatar = html.escape(profile.get("avatar_url") or "")
    followers = profile.get("followers", 0)
    public_repos = profile.get("public_repos", repo_count)
    inner = (
        '<div class="profile">'
        f'<img src="{avatar}" alt="avatar">'
        f'<div><div class="name">{name}</div><div class="user">@{html.escape(username)}</div>'
        f'<div class="bio">{bio}</div></div></div>'
        '<div class="stats">'
        f'<div class="stat"><b>{public_repos}</b><span>Public repos</span></div>'
        f'<div class="stat"><b>{followers}</b><span>Followers</span></div>'
        f'<div class="stat"><b>{repo_count}</b><span>Analyzed</span></div></div>'
    )
    return card(inner)


# -------------------------------------------------------------------------- UI
st.set_page_config(page_title="GitHub Skill Verifier", page_icon="✅")
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><h1>✅ GitHub Skill Verifier</h1>'
    "<p>Check which skills on a resume are backed by real code on GitHub.</p></div>",
    unsafe_allow_html=True,
)

col_a, col_b = st.columns([1, 2])
with col_a:
    username = st.text_input("GitHub username", placeholder="e.g. octocat")
with col_b:
    skills_text = st.text_input(
        "Skills from the resume (comma separated)",
        value="Python, SQL, HTML, TensorFlow, Keras, scikit-learn, Streamlit, Power BI, Excel",
    )
include_forks = st.checkbox("Include forked repositories", value=False)
with st.expander("Optional: GitHub token (only if you hit the rate limit)"):
    token = st.text_input("Personal access token", type="password")

if st.button("Verify skills", type="primary"):
    skills = [s.strip() for s in skills_text.split(",") if s.strip()]
    if not username.strip() or not skills:
        st.warning("Please enter a GitHub username and at least one skill.")
        st.stop()

    username = username.strip()
    with st.spinner("Reading repositories..."):
        repos, error = fetch_repos(username, include_forks, token)
        if error:
            st.error(error)
            st.stop()
        if not repos:
            st.info("No public repositories found (forks are excluded by default).")
            st.stop()
        profile = fetch_profile(username, token)
        evidence = build_evidence(username, repos, token or None)

    results = [(skill, find_skill(skill, evidence)) for skill in skills]
    verified = sum(1 for _, hits in results if hits)
    percent = round(100 * verified / len(skills))

    left, right = st.columns([1, 2])
    with left:
        st.markdown(ring_card(percent), unsafe_allow_html=True)
    with right:
        st.markdown(profile_card(profile, username, len(repos)), unsafe_allow_html=True)

    st.markdown(
        f'<div class="section">Skill check ({verified} of {len(skills)} verified)</div>',
        unsafe_allow_html=True,
    )
    chips = "".join(
        f'<span class="chip {"chip-ok" if hits else "chip-no"}">'
        f"{'✓' if hits else '?'} {html.escape(skill)}</span>"
        for skill, hits in results
    )
    st.markdown(chips, unsafe_allow_html=True)
    st.markdown(
        '<div class="note">Skills like Excel or Power BI rarely appear on GitHub, so '
        '"?" does not mean the skill is fake.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section">Evidence</div>', unsafe_allow_html=True)
    rows = [
        {
            "Skill": skill,
            "Status": "Found in code" if hits else "Not found",
            "Repositories": ", ".join(hits[:4]) if hits else "-",
        }
        for skill, hits in results
    ]
    st.dataframe(rows, hide_index=True)

    langs = Counter(r["language"] for r in repos if r.get("language"))
    if langs:
        st.markdown('<div class="section">Main languages</div>', unsafe_allow_html=True)
        st.bar_chart(dict(langs))

st.markdown(
    '<div class="footer">Built with Python, Streamlit and the GitHub API</div>',
    unsafe_allow_html=True,
)
