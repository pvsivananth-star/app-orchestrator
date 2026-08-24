#!/usr/bin/env python3
# ui.py - Fixed version with queue-based communication

import streamlit as st
import sys
import threading
import traceback
import time
import queue
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app_orchestrator.orchestrator import Orchestrator

st.set_page_config(
    page_title="App Orchestrator",
    page_icon="🚀",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "status" not in st.session_state:
    st.session_state.status = "idle"
if "repo_path" not in st.session_state:
    st.session_state.repo_path = None
if "repo_valid" not in st.session_state:
    st.session_state.repo_valid = False
if "thread_running" not in st.session_state:
    st.session_state.thread_running = False
if "error_log" not in st.session_state:
    st.session_state.error_log = None
if "pending_requirements" not in st.session_state:
    st.session_state.pending_requirements = None
if "suggested_path" not in st.session_state:
    st.session_state.suggested_path = ""
if "result_queue" not in st.session_state:
    st.session_state.result_queue = queue.Queue()

def validate_repo_path(path_str: str) -> tuple[bool, str]:
    try:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            return False, f"Path does not exist: {path}"
        if not path.is_dir():
            return False, f"Path is not a directory: {path}"
        if not (path / ".git").exists():
            return False, f"Not a git repository (no .git folder): {path}"
        return True, str(path)
    except Exception as e:
        return False, f"Invalid path: {e}"

def set_repo_path(path_str: str):
    if not path_str or not path_str.strip():
        st.error("Please enter a path.")
        return
    valid, result = validate_repo_path(path_str.strip())
    if valid:
        st.session_state.repo_path = result
        st.session_state.repo_valid = True
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"✅ Repository set: `{result}`\n\nNow enter your requirements in the chat below."
        })
        st.session_state.status = "idle"
    else:
        st.session_state.repo_valid = False
        st.session_state.repo_path = None
        st.error(f"❌ {result}")

def run_orchestrator_worker(repo_path: str, requirements: str, result_queue: queue.Queue):
    try:
        orch = Orchestrator(Path(repo_path))
        result = orch.run(requirements)
        result_queue.put(("success", result))
    except Exception as e:
        result_queue.put(("error", traceback.format_exc()))

def start_orchestration():
    if not st.session_state.repo_valid:
        st.error("Please set a valid repository path first.")
        return
    if st.session_state.thread_running:
        return
    if not st.session_state.get("pending_requirements"):
        return

    requirements = st.session_state.pending_requirements
    st.session_state.pending_requirements = None
    st.session_state.thread_running = True
    st.session_state.status = "processing"

    st.session_state.messages.append({"role": "user", "content": requirements})
    st.session_state.messages.append({
        "role": "assistant",
        "content": "⏳ **Processing your request...**\n\nThis may take a few moments."
    })

    while not st.session_state.result_queue.empty():
        st.session_state.result_queue.get()

    thread = threading.Thread(
        target=run_orchestrator_worker,
        args=(st.session_state.repo_path, requirements, st.session_state.result_queue),
        daemon=True
    )
    thread.start()

def check_result():
    if st.session_state.thread_running:
        try:
            msg_type, data = st.session_state.result_queue.get_nowait()
            if msg_type == "success":
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"✅ **Done!**\n\n{data.get('message', 'Orchestration completed successfully.')}"
                })
                st.session_state.status = "done"
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"❌ **Error:**\n\n```\n{data}\n```"
                })
                st.session_state.status = "error"
                st.session_state.error_log = data
            st.session_state.thread_running = False
            st.rerun()
        except queue.Empty:
            pass

def get_ox2_files(repo_path: str) -> dict[str, str]:
    if not repo_path:
        return {}
    ox2_path = Path(repo_path) / ".ox2"
    if not ox2_path.exists():
        return {}
    files = {}
    for filepath in ox2_path.iterdir():
        if filepath.is_file():
            try:
                files[filepath.name] = filepath.read_text()
            except:
                files[filepath.name] = "[Error reading file]"
    return files

def commit_changes(repo_path: str):
    import subprocess
    repo = Path(repo_path)
    if not (repo / ".git").exists():
        st.error("Not a git repository.")
        return
    try:
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Orchestrator automated commit"], cwd=repo, check=True)
        st.success("✅ Changes committed successfully!")
        st.rerun()
    except subprocess.CalledProcessError as e:
        st.error(f"Commit failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")

with st.sidebar:
    st.header("📁 Project Directory")
    cwd = str(Path.cwd())
    home = str(Path.home())
    st.caption("Quick paths:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📂 Current", use_container_width=True):
            st.session_state.suggested_path = cwd
    with col2:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.suggested_path = home
    with col3:
        if st.button("📁 Test", use_container_width=True):
            st.session_state.suggested_path = "../test-ox2"
    
    repo_input = st.text_input(
        "Repository Path",
        value=st.session_state.suggested_path if st.session_state.suggested_path else "",
        placeholder="./path/to/your/repo",
        key="repo_input"
    )
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("✅ Set Path", use_container_width=True, type="primary"):
            if repo_input.strip():
                set_repo_path(repo_input.strip())
            else:
                st.error("Please enter a path.")
    with col_btn2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    if st.session_state.repo_valid:
        st.success(f"✅ {st.session_state.repo_path}")
        try:
            repo = Path(st.session_state.repo_path)
            if (repo / ".git").exists():
                py_files = len(list(repo.glob("**/*.py")))
                st.caption(f"📊 Git repo: {py_files} Python files")
        except:
            pass
    else:
        st.warning("⚠️ No valid repository set")
    
    st.divider()
    st.header("📁 Artifacts (.ox2)")
    if st.session_state.repo_valid:
        files = get_ox2_files(st.session_state.repo_path)
        if files:
            for fname, content in files.items():
                with st.expander(f"📄 {fname}"):
                    st.code(content, language="text")
        else:
            st.info("No .ox2 artifacts yet. Run the orchestrator first.")
    else:
        st.info("Set a repository path to see artifacts.")
    
    st.divider()
    if st.button("💾 Commit Changes", disabled=(st.session_state.status != "done" or not st.session_state.repo_valid)):
        if st.session_state.repo_valid:
            commit_changes(st.session_state.repo_path)
    
    if st.session_state.error_log:
        with st.expander("❌ Error Log"):
            st.code(st.session_state.error_log, language="python")

check_result()

col_chat, col_questions = st.columns([2, 1])

with col_chat:
    st.header("💬 Chat")
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    chat_disabled = not st.session_state.repo_valid or st.session_state.thread_running
    if chat_disabled:
        if not st.session_state.repo_valid:
            placeholder = "⚠️ Please set a valid repository path in the sidebar first."
        else:
            placeholder = "Processing... please wait"
    else:
        placeholder = "Enter your requirements..."
    
    prompt = st.chat_input(placeholder, disabled=chat_disabled)
    if prompt and not chat_disabled:
        st.session_state.pending_requirements = prompt
        start_orchestration()
        st.rerun()
    
    if st.session_state.status == "processing":
        with st.spinner("Orchestrator is running..."):
            st.empty()

with col_questions:
    st.header("📋 Status")
    status_map = {
        "idle": "🟢 Ready",
        "processing": "🟡 Processing...",
        "done": "✅ Complete",
        "error": "❌ Error",
    }
    st.info(f"**Status:** {status_map.get(st.session_state.status, 'Unknown')}")
    if st.session_state.repo_valid:
        st.caption(f"📂 {st.session_state.repo_path}")
    
    st.divider()
    st.header("📋 Instructions")
    st.markdown("""
    1. **Set project directory** in the sidebar
    2. **Enter requirements** in the chat input
    3. **Wait** for the orchestrator to process
    4. **Review** generated artifacts in the sidebar
    5. **Commit** changes when satisfied
    """)

st.divider()
st.caption("🚀 App Orchestrator v0.1.0")
